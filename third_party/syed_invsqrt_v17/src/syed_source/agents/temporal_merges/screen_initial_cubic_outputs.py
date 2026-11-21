# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Exact complete initial-frame cubic grant for two-product windows."""
from pathlib import Path
from itertools import combinations
import argparse
import gzip
import json
import pickle
import time
from temporal_core import NOTICE, Program, Span, bits, captures, sha

NATIVE_SHA='9a4e6a824f6ed5c3deb5eb6b8627db9d7f08dc0830ffa39d8db3c949d95ee809'
OWNERS=tuple(f'q{i}' for i in range(44))


def dual_from_basis(space,target):
    residual=space.normal(target)
    assert residual
    dual=1<<(residual.bit_length()-1)
    for pivot,(row,_) in sorted(space.rows.items()):
        if (dual&row).bit_count()&1:
            dual^=1<<pivot
    assert (dual&target).bit_count()&1
    assert all(not ((dual&v).bit_count()&1) for v in space.columns)
    return dual


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--native',type=Path,required=True)
    ap.add_argument('--witness-source',type=Path,required=True)
    ap.add_argument('--census',type=Path,required=True)
    ap.add_argument('--window-id',type=int,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    started=time.monotonic()
    assert sha(args.native)==NATIVE_SHA
    row=next(r for r in json.loads(args.census.read_text())['windows']
             if r['window_id']==args.window_id)
    assert not row['retained_nonlinear_value_gates'] and row['proposed_products']==2
    with gzip.open(args.witness_source,'rb') as f:
        xs=list(pickle.load(f)['xs'])
    full=(1<<len(xs))-1
    program=Program(args.native.read_text())
    cap=captures(program,[row['first'],row['end']],xs,formal=True)
    assert all(set(v)<={0} for frame in cap.values() for v in frame.values())
    initial=Span()
    initial.add(full,'constant')
    for q in OWNERS:
        initial.add(cap[row['first']][q].get(0,0),q)
    space=initial.copy()
    columns=initial.columns[1:]
    descriptors=initial.descriptors[1:]
    counts={1:len(initial.columns)}
    rank_at_degree={1:len(space.columns)}
    for degree in (2,3):
        count=0
        for indices in combinations(range(len(columns)),degree):
            value=full
            for j in indices:
                value&=columns[j]
            space.add(value,[descriptors[j] for j in indices])
            count+=1
            if count%2000==0:
                print(json.dumps(dict(stage='degree_image',degree=degree,columns=count,
                                      rank=len(space.columns),seconds=time.monotonic()-started)),flush=True)
        counts[degree]=count
        rank_at_degree[degree]=len(space.columns)
    targets=[]
    for owner in row['fixed_branch_screen']['independent_final_owners']:
        target=cap[row['end']][owner].get(0,0)
        member=space.solve(target) is not None
        item=dict(owner=owner,inside_complete_cubic_image=member)
        if not member:
            dual=dual_from_basis(space,target)
            item.update(original_input_values=[int(xs[j]) for j in bits(dual)],
                        target_pairing=1,all_initial_degree_at_most_three_pairings=0)
        targets.append(item)
    report=dict(notice=NOTICE,status='COMPLETE_NEGATIVE_INITIAL_CUBIC_OUTPUT_IMAGE'
                if any(not r['inside_complete_cubic_image'] for r in targets)
                else 'NECESSARY_CUBIC_IMAGE_PASSES_NO_PRODUCT_SYNTHESIS',
                native_sha256=sha(args.native),source_sha256=sha(__file__),
                witness_source_sha256=sha(args.witness_source),census_sha256=sha(args.census),
                window_id=row['window_id'],first=row['first'],end=row['end'],
                selected_operations=row['selected_operations'],
                initial_affine_rank=len(initial.columns),initial_nonconstant_owners=descriptors,
                original_witness_inputs=len(xs),native_capture_HMR_symbolic=True,
                column_counts_by_degree=counts,image_ranks_by_degree=rank_at_degree,
                targets=targets,modelled_expected_Toffolis='11417/8=1427.125',
                scope=('Exact interval with no retained nonlinear value gate. On fixed all-zero HMR '
                       'outcomes, two parity products with arbitrary intermediate affine gates and '
                       'resets give outputs of degree at most three in the initial live affine frame. '
                       'If both second controls contain the first product, Boolean idempotence reduces '
                       'its square. Every initial cubic sum is overgranted. Literal original-input '
                       'characters refute the complete image; no phase assumption is needed for a '
                       'negative value result. A positive still owes actual factors and all phases.'),
                qualified=False,seconds=time.monotonic()-started)
    args.out.mkdir(parents=True,exist_ok=False)
    (args.out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('status','initial_affine_rank','image_ranks_by_degree','seconds')}),flush=True)


if __name__=='__main__':
    main()
