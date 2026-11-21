# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Complete two-product prefix obstruction for three products/two outputs.

Modulo the initial affine space, three product values span at most three
directions. If two independent final directions are recovered, some nonzero
final parity is already in the initial-plus-first-two-product span. Every one
of the three final parities is therefore tested for scalar two-product
realizability. For nonquadratic F, all serial factors C lie in 1+ker(v -> vF
mod Q(initial)); parallel two-product sums are excluded by nonquadraticity.
The small complete multiplier kernels are enumerated without support bounds.
"""
from pathlib import Path
from itertools import combinations
from collections import Counter
import argparse
import gzip
import json
import pickle
import sys
import time
from temporal_core import (NOTICE, Program, Span, bits, captures, comb,
                           separating_dual, sha)
from screen_initial_cubic_outputs import dual_from_basis

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'restored/research_v9/second_seed_and_phases'))
from fixed_factor_plucker import affine_preimage, affine_forms, complete_bivector

NATIVE_SHA='9a4e6a824f6ed5c3deb5eb6b8627db9d7f08dc0830ffa39d8db3c949d95ee809'
OWNERS=tuple(f'q{i}' for i in range(44))


def scalar_test(initial,quadratic,target,xs,full,out,max_kernel):
    qdual=dual_from_basis(quadratic,target)
    products=[target&v for v in initial.columns]
    columns=[quadratic.normal(v) for v in products]
    point,kernel,rank=affine_preimage(columns,0)
    assert point==0
    proof=quadratic.copy()
    rank_characters=[]
    for j,value in enumerate(products):
        if proof.solve(value) is not None:
            continue
        dual=dual_from_basis(proof,value)
        rank_characters.append(dict(multiplier_basis_index=j,
                                    multiplier_owner=initial.descriptors[j],
                                    original_input_values=[int(xs[k]) for k in bits(dual)],
                                    target_pairing=1,all_initial_quadratic_and_previous_multiplier_pairings=0))
        proof.add(value)
    assert len(rank_characters)==rank
    assert rank+len(kernel)==len(initial.columns)
    for mask in kernel:
        assert quadratic.solve(target&comb(initial.columns,mask)) is not None
    record=dict(nonquadratic_original_input_character=[int(xs[k]) for k in bits(qdual)],
                multiplier_quotient_rank=rank,complete_multiplier_kernel_dimension=len(kernel),
                complete_multiplier_kernel_masks_hex=list(map(hex,kernel)),
                complete_multiplier_kernel_owner_parities=[
                    [initial.descriptors[j] for j in bits(k)] for k in kernel],
                multiplier_rank_characters=rank_characters,
                parallel_two_product_sum_excluded=True,
                trivial_C_one_excluded_by_nonquadraticity=True,C_cases=[])
    if len(kernel)>8:
        record['status']='OPEN_MULTIPLIER_FAMILY_ABOVE_DECLARED_ENUMERATION_LIMIT'
        return record
    for mask in range(1,1<<len(kernel)):
        hmask=comb(kernel,mask)
        cmask=hmask^1
        c=comb(initial.columns,cmask)
        assert c not in (0,full)
        pivot=((cmask>>1)&-(cmask>>1)).bit_length()-1
        controls=[v for j,v in enumerate(initial.columns[1:]) if j!=pivot]
        owners=[q for j,q in enumerate(initial.descriptors[1:]) if j!=pivot]
        free=Span()
        for v,q in zip(initial.columns,initial.descriptors):
            free.add(v,['E',q])
        for v,q in zip(initial.columns,initial.descriptors):
            free.add(c&v,['D',q])
        pairs=list(combinations(range(len(controls)),2))
        weighted=[c&controls[i]&controls[j] for i,j in pairs]
        reduced=[free.normal(v) for v in weighted]
        point,inner_kernel,inner_rank=affine_preimage(reduced,free.normal(target))
        case=dict(multiplier_parameter_mask=mask,C_initial_affine_mask_hex=hex(cmask),
                  C_owner_parity=[initial.descriptors[j] for j in bits(cmask)],
                  gauged_control_owners=owners,correction_rank=len(free.columns),
                  weighted_quadratic_image_rank=inner_rank,
                  complete_product_fiber_dimension=len(inner_kernel))
        if point is None:
            dual=separating_dual(free.columns+weighted,target)
            case.update(status='COMPLETE_NEGATIVE_FIXED_C_QUADRATIC_IMAGE',
                        original_input_values=[int(xs[j]) for j in bits(dual)],
                        target_pairing=1,all_affine_and_weighted_quadratic_pairings=0)
        elif len(inner_kernel)>max_kernel:
            case['status']='OPEN_COMPLETE_PRODUCT_FIBER_ABOVE_LIMIT'
        else:
            forms=affine_forms(point,inner_kernel,len(pairs))
            result=complete_bivector(len(controls),forms,len(inner_kernel),max_enumerate=16)
            cp=out/f'C_{mask:03d}_PLUCKER.json.gz'
            with gzip.open(cp,'wt',compresslevel=6) as f:
                json.dump(dict(notice=NOTICE,owners=owners,point_hex=hex(point),
                               kernel_hex=list(map(hex,inner_kernel)),result=result),f)
            case.update(status=result['status'],certificate=cp.name,certificate_sha256=sha(cp))
            if result['status']=='DECOMPOSABLE_WITNESS':
                amask,bmask=result['factor_masks']
                a,b=comb(controls,amask),comb(controls,bmask)
                correction=free.solve(target^(c&a&b))
                assert correction is not None
                d=e=0
                d_terms=[]
                e_terms=[]
                for j in bits(correction):
                    kind,q=free.descriptors[j]
                    value=full if q=='constant' else initial.columns[initial.descriptors.index(q)]
                    if kind=='D':
                        d^=value
                        d_terms.append(q)
                    else:
                        e^=value
                        e_terms.append(q)
                assert target==((c&((a&b)^d))^e)
                case['abstract_two_product_witness']=dict(
                    A=[owners[j] for j in bits(amask)],B=[owners[j] for j in bits(bmask)],
                    C=[initial.descriptors[j] for j in bits(cmask)],D=d_terms,E=e_terms,
                    phase_and_physical_lifetimes_unproved=True)
        record['C_cases'].append(case)
    closed=all(c['status'] in ('COMPLETE_NEGATIVE_FIXED_C_QUADRATIC_IMAGE',
                              'COMPLETE_NEGATIVE_FIXED_FACTOR') for c in record['C_cases'])
    record['status']='COMPLETE_NEGATIVE_SCALAR_TWO_PRODUCTS' if closed else 'SCALAR_TWO_PRODUCT_PREFIX_REMAINS_POSSIBLE'
    return record


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--native',type=Path,required=True)
    ap.add_argument('--witness-source',type=Path,required=True)
    ap.add_argument('--census',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--windows',type=int,nargs='*',default=[1717,1902,1919,2080])
    ap.add_argument('--max-kernel',type=int,default=160)
    args=ap.parse_args()
    started=time.monotonic()
    assert sha(args.native)==NATIVE_SHA
    census=json.loads(args.census.read_text())
    by={r['window_id']:r for r in census['windows']}
    rows=[by[i] for i in args.windows]
    assert all(r['proposed_products']==3 and not r['retained_nonlinear_value_gates']
               and r['fixed_branch_screen']['final_over_initial_quotient_rank']==2 for r in rows)
    with gzip.open(args.witness_source,'rb') as f:
        xs=list(pickle.load(f)['xs'])
    full=(1<<len(xs))-1
    program=Program(args.native.read_text())
    cap=captures(program,{i for r in rows for i in [r['first'],r['end']]},xs,formal=True)
    assert all(set(v)<={0} for frame in cap.values() for v in frame.values())
    args.out.mkdir(parents=True,exist_ok=False)
    records=[]
    for row in rows:
        case_start=time.monotonic()
        initial=Span()
        initial.add(full,'constant')
        for q in OWNERS:
            initial.add(cap[row['first']][q].get(0,0),q)
        quadratic=initial.copy()
        for i,j in combinations(range(1,len(initial.columns)),2):
            quadratic.add(initial.columns[i]&initial.columns[j])
        total=initial.copy()
        outputs=[]
        owners=[]
        for q in OWNERS:
            value=cap[row['end']][q].get(0,0)
            if total.add(value,q):
                outputs.append(value)
                owners.append(q)
        assert len(outputs)==2
        scalars=[]
        for mask in (1,2,3):
            target=comb(outputs,mask)
            out=args.out/f"WINDOW_{row['window_id']}/SCALAR_{mask}"
            out.mkdir(parents=True,exist_ok=False)
            if quadratic.solve(target) is not None:
                scalar=dict(status='OPEN_QUADRATIC_SCALAR_NOT_COVERED_BY_THIS_BATCH')
            else:
                scalar=scalar_test(initial,quadratic,target,xs,full,out,args.max_kernel)
            scalar.update(output_direction_mask=mask,
                          final_owner_parity=[owners[j] for j in bits(mask)])
            (out/'REPORT.json').write_text(json.dumps(dict(notice=NOTICE,**scalar),indent=2)+'\n')
            scalars.append(scalar)
            print(json.dumps(dict(window_id=row['window_id'],scalar=mask,status=scalar['status'],
                                  multiplier_kernel=scalar.get('complete_multiplier_kernel_dimension'),
                                  C_cases=[r['status'] for r in scalar.get('C_cases',[])])),flush=True)
        negative=all(s['status']=='COMPLETE_NEGATIVE_SCALAR_TWO_PRODUCTS' for s in scalars)
        rec=dict(window_id=row['window_id'],first=row['first'],end=row['end'],
                 selected_operations=row['selected_operations'],initial_affine_rank=len(initial.columns),
                 initial_affine_basis_owners=initial.descriptors,
                 complete_initial_quadratic_rank=len(quadratic.columns),
                 native_final_quotient_basis_owners=owners,scalars=scalars,
                 native_HMR=row['HMR'],native_rotations=row['rotations'],
                 status='COMPLETE_NEGATIVE_THREE_PRODUCTS_TWO_OUTPUTS_PREFIX' if negative
                        else 'THREE_PRODUCT_PREFIX_NECESSARY_SCREEN_PASSES_NO_NATIVE_SYNTHESIS',
                 modelled_expected_Toffolis='11417/8=1427.125',qualified=False,
                 seconds=time.monotonic()-case_start)
        records.append(rec)
        report=dict(notice=NOTICE,status='COMPLETE_DECLARED_THREE_PRODUCT_PREFIX_BATCH'
                    if len(records)==len(rows) else 'ACTIVE',
                    native_sha256=sha(args.native),source_sha256=sha(__file__),
                    factor_solver_sha256=sha(ROOT/'restored/research_v9/second_seed_and_phases/fixed_factor_plucker.py'),
                    witness_source_sha256=sha(args.witness_source),census_sha256=sha(args.census),
                    original_witness_inputs=len(xs),native_HMR_captures_symbolic=True,
                    theorem=__doc__,records=records,counts=dict(Counter(r['status'] for r in records)),
                    scope=('Exact five-write/three-product intervals with no retained nonlinear value gate '
                           'and two independent final directions modulo the initial affine frame. All three '
                           'nonzero final parities are tested against every scalar two-product circuit. '
                           'For nonquadratic targets, the complete multiplier kernel covers every final '
                           'serial factor C; all stated C fibers are exact. Arbitrary times, affine '
                           'frames and resets are overgranted. Additional value products or extended '
                           'intervals are outside. Positive prefixes owe the third product, width and phases.'),
                    qualified=False,seconds=time.monotonic()-started)
        (args.out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    main()
