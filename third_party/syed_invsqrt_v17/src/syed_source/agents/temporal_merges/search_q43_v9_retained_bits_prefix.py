# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Construct v9 from retained coefficient bits with a declared first helper.

The first helper is the product of two parities of at most the declared
weight. All offsets are free in the initial affine space. Equal first-helper
spaces are deduplicated, then the remaining two-product scalar problem is
solved without support restrictions. A quadratic remainder is handled by a
constructive alternating-rank factorization; failure to find rank<=4 there
is OPEN, not a negative. The complete owned4096-row component is the domain.
"""
from pathlib import Path
from itertools import combinations
from collections import Counter
import argparse
import gzip
import json
import time
from temporal_core import NOTICE, Span, affine_preimage, bits, comb, sha
from screen_three_product_two_output_prefix import scalar_test
from screen_initial_cubic_outputs import dual_from_basis
from screen_q43_deferred_idle_recompute import restore

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def component(held,root_bits):
    table=ROOT/'incumbent_sources/frozen_source/fusion64/numeric/lattice_d13_half38sel.json'
    D=json.loads(table.read_text())['D'];assert len(D)==4096
    full=(1<<4096)-1;xs=list(range(4096))
    def truth(values,bit):return sum(((int(v)>>bit)&1)<<i for i,v in enumerate(values))
    functions={f'D{i}':truth(D,i) for i in range(13)}
    functions.update({f'v{i}':truth(xs,i) for i in range(12)})
    functions['g_A5']=(functions['D9']^functions['D10']^functions['D11'])&functions['D12']
    names=[f'v{i}' for i in root_bits]+[f'D{i}' for i in held+list(range(9,13))]+['g_A5']
    initial=Span();initial.add(full,'constant')
    for name in names:assert initial.add(functions[name],name)
    return table,xs,full,functions,initial


def first_helpers(initial,weight):
    n=len(initial.columns)-1
    masks=[sum(1<<i for i in inds) for w in range(1,min(weight,n)+1)
           for inds in combinations(range(n),w)]
    forms={m:comb(initial.columns[1:],m) for m in masks}
    planes=sorted({tuple(sorted((a,b,a^b))) for a,b in combinations(masks,2)})
    seen=set();cases=[];affine=0;duplicate=0
    for label,plane in enumerate(planes):
        a,b=next((a,b) for a,b in combinations(plane,2) if a in forms and b in forms)
        H=forms[a]&forms[b];residual=initial.normal(H)
        if not residual:affine+=1;continue
        if residual in seen:duplicate+=1;continue
        seen.add(residual)
        cases.append(dict(plane_label=label,A_mask=a,B_mask=b,H=H))
    return cases,dict(factor_parity_count=len(masks),factor_plane_count=len(planes),
                      affine_first_products=affine,duplicate_first_product_spaces=duplicate,
                      distinct_first_product_spaces=len(cases))


def quadratic_tail(initial,F,full,xs):
    frame={f'q{i}':{} for i in range(44)}
    for j,v in enumerate(initial.columns[1:]):frame[f'q{j}']={0:v}
    frame['q43']={0:F}
    r=restore(frame,'q43',full,xs)
    def name(q):return 'constant' if q=='constant' else initial.descriptors[int(q[1:])+1]
    for p in r.get('products',[]):
        for side in ('A','B'):p[side]=list(map(name,p[side]))
    if 'affine_offset' in r:r['affine_offset']=list(map(name,r['affine_offset']))
    return r


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--held',type=int,nargs='+',default=[7,8])
    ap.add_argument('--root-bits',type=int,nargs='+',default=[7,8])
    ap.add_argument('--factor-weight',type=int,default=2)
    ap.add_argument('--max-seconds',type=float,default=480)
    args=ap.parse_args();began=time.monotonic()
    assert args.held==sorted(set(args.held)) and all(0<=j<9 for j in args.held)
    assert args.root_bits==sorted(set(args.root_bits)) and all(0<=j<9 for j in args.root_bits)
    table,xs,full,functions,initial=component(args.held,args.root_bits)
    F=functions['v9'];cases,domain=first_helpers(initial,args.factor_weight)
    args.out.mkdir(exist_ok=False);records=[];winner=None
    with gzip.open(args.out/'CASE_CERTIFICATES.jsonl.gz','wt',compresslevel=6) as stream:
        for index,case in enumerate(cases):
            if time.monotonic()-began>args.max_seconds:break
            extended=initial.copy();assert extended.add(case['H'],'new_H')
            Q=extended.copy()
            for i,j in combinations(range(1,len(extended.columns)),2):
                Q.add(extended.columns[i]&extended.columns[j])
            row={k:v for k,v in case.items() if k!='H'}
            row.update(case_id=index,initial_rank=len(extended.columns),quadratic_rank=len(Q.columns))
            if Q.solve(F) is not None:
                result=quadratic_tail(extended,F,full,xs)
                row['result']=result
                if result.get('paid_products',100)<=2:
                    row['status']='ACTUAL_QUADRATIC_TWO_PRODUCT_TAIL'
                    winner=dict(first_product={side:[initial.descriptors[j+1] for j in bits(case[side+'_mask'])]
                                                for side in ('A','B')},quadratic_tail=result,
                                total_new_products=1+result['paid_products'])
                else:row['status']='OPEN_QUADRATIC_TAIL_ABOVE_TWO_PRODUCTS'
            else:
                products=[F&v for v in extended.columns]
                _,kernel,rank=affine_preimage([Q.normal(v) for v in products],0)
                row.update(multiplier_rank=rank,kernel_dimension=len(kernel),kernel_masks_hex=list(map(hex,kernel)))
                if not kernel:
                    proof=Q.copy();characters=[]
                    for j,v in enumerate(products):
                        assert proof.solve(v) is None
                        d=dual_from_basis(proof,v);characters.append(dict(index=j,character_hex=hex(d)))
                        proof.add(v)
                    row.update(status='COMPLETE_NEGATIVE_TWO_PRODUCT_MULTIPLIER_AFTER_FIRST_HELPER',
                               rank_characters=characters)
                else:
                    sub=args.out/f'CASE_{index:05d}';sub.mkdir()
                    result=scalar_test(extended,Q,F,xs,full,sub,160)
                    row.update(status=result['status'],result=result)
                    witnesses=[c['abstract_two_product_witness'] for c in result.get('C_cases',[])
                               if 'abstract_two_product_witness' in c]
                    if witnesses:
                        winner=dict(first_product={side:[initial.descriptors[j+1] for j in bits(case[side+'_mask'])]
                                                    for side in ('A','B')},
                                    remaining_two_products=witnesses[0],total_new_products=3)
            stream.write(json.dumps(dict(notice=NOTICE,**row))+'\n');stream.flush()
            records.append({k:v for k,v in row.items() if k not in ('rank_characters','result')})
            if index%100==0 or winner:
                print(json.dumps(dict(case=index,status=row['status'],kernel=row.get('kernel_dimension'),
                                      seconds=time.monotonic()-began)),flush=True)
            if winner:break
    closed=(len(records)==len(cases) and all(r['status'] in
        ('COMPLETE_NEGATIVE_TWO_PRODUCT_MULTIPLIER_AFTER_FIRST_HELPER','COMPLETE_NEGATIVE_SCALAR_TWO_PRODUCTS')
        for r in records))
    report=dict(notice=NOTICE,status=('ACTUAL_COMPONENT_AT_MOST_THREE_PRODUCT_WITNESS' if winner else
        'COMPLETE_NEGATIVE_DECLARED_FIRST_HELPER_FAMILY' if closed else 'PARTIAL_OR_OPEN_FIRST_HELPER_FAMILY'),
        numerical_verification='AGENT_VERIFIED_ROOT_REPLAY_PENDING',qualified=False,
        source_sha256=sha(__file__),table_sha256=sha(table),component_rows=4096,
        component_domain='Root v=0..4095; these are not original full-circuit input x values.',
        initial_basis=initial.descriptors,retained_coefficient_bits=args.held,
        retained_root_bits=args.root_bits,first_factor_weight_bound=args.factor_weight,
        domain=domain,completed_cases=len(records),cases=records,
        counts=dict(Counter(r['status'] for r in records)),actual_component_witness=winner,
        modelled_extra_products='at most3',modelled_max_total_on_501f_base='11597/8',
        native_all_domain_binding_and_actual_width_and_phase_emission_pending=True,
        certificates_sha256=sha(args.out/'CASE_CERTIFICATES.jsonl.gz'),
        seconds=time.monotonic()-began,scope=__doc__)
    (args.out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('cases','scope')},indent=2))


if __name__=='__main__':main()
