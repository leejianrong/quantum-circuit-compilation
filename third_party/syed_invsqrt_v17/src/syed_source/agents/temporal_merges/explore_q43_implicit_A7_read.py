# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Bound the actual first nonlinear A7 read and its later reconstruction.

Indices stay on the 501f parent. This does not rescan any first-helper plane
domain. A complete two-product necessary image test is applied to the new
wrap target, followed by exact quadratic membership for later A7 frames.
"""
import argparse
import gzip
import json
from itertools import combinations
from pathlib import Path
from temporal_core import NOTICE,Program,Span,captures,sha,bits,comb,affine_preimage,mul,xor
from screen_initial_cubic_outputs import dual_from_basis
from screen_q43_deferred_idle_recompute import restore

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
NATIVE=ROOT/'root/q43_phase_and_late_width_v1/candidate_text.kmx'
NATIVE_SHA='501f1d90c3a82c45c6a60d6ec478bd89c91ebc3f72e847cc56f8d4182a014e43'
TABLE=ROOT/'incumbent_sources/frozen_source/fusion64/numeric/lattice_d13_half38sel.json'
PHYSICAL={'D0':16,'D1':17,'D2':18,'D3':19,'D4':43,'D5':29,'D6':27,'D7':9,
    'D8':20,'D9':31,'D10':33,'D11':8,'D12':28,'S0':32,'S1':30,'S2':0,'S3':11,
    'S4':13,'S5':34,'v0':39,'v1':37,'v2':12,'v3':38,'v4':14,'v5':15,'A7':35}


def quadratic(initial):
    Q=initial.copy()
    for a,b in combinations(initial.columns[1:],2):Q.add(a&b)
    return Q


def necessary_two(initial,F,xs):
    Q=quadratic(initial);inQ=Q.solve(F) is not None
    result=dict(affine_rank=len(initial.columns),affine_basis=initial.descriptors,
                quadratic_rank=len(Q.columns),target_quadratic=inQ)
    if inQ:return dict(result,status='NECESSARY_QUADRATIC_PASS')
    chi=dual_from_basis(Q,F)
    _,kernel,rank=affine_preimage([Q.normal(F&v) for v in initial.columns],0)
    result.update(nonquadratic_character=[int(xs[j]) for j in bits(chi)],
        multiplier_rank=rank,complete_multiplier_kernel=list(map(hex,kernel)),C_cases=[])
    for m in range(1,1<<len(kernel)):
        cm=1^comb(kernel,m);C=comb(initial.columns,cm);W=initial.copy()
        for q in Q.columns:W.add(C&q)
        point=W.solve(F)
        row=dict(parameter_mask=m,C_mask=hex(cm),C_terms=[initial.descriptors[j] for j in bits(cm)],
                 image_rank=len(W.columns),image_pass=point is not None)
        if point is None:
            chi=dual_from_basis(W,F);row['separating_character']=[int(xs[j]) for j in bits(chi)]
        result['C_cases'].append(row)
    result['status']='NECESSARY_TWO_PRODUCT_PASS' if any(r['image_pass'] for r in result['C_cases']) else 'COMPLETE_TWO_PRODUCT_VALUE_NEGATIVE'
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();args.out.mkdir(exist_ok=False);assert sha(NATIVE)==NATIVE_SHA
    table=json.loads(TABLE.read_text());full=(1<<4096)-1;vs=list(range(4096))
    truth=lambda seq,j:sum(((int(v)>>j)&1)<<i for i,v in enumerate(seq))
    vals={f'D{i}':truth(table['D'],i) for i in range(13)}
    vals.update({f'S{i}':truth([table['S'][v>>6] for v in vs],i) for i in range(7)})
    vals.update({f'v{i}':truth(vs,i) for i in range(6)})
    F=truth([table['A'][v>>6] for v in vs],7)
    G=(F^vals['v5'])&(vals['D7']^vals['v5']^full)
    records=[]
    for name,names in [('informative16',[f'D{i}' for i in range(5,13)]+[f'S{i}' for i in range(6)]+['v4','v5']),
                       ('full_component25',[f'D{i}' for i in range(13)]+[f'S{i}' for i in range(6)]+[f'v{i}' for i in range(6)])]:
        initial=Span();initial.add(full,'constant')
        for n in names:initial.add(vals[n],n)
        r=necessary_two(initial,G,vs);r.update(frame=name,target='wrap_g',domain='component_v_0_to4095')
        records.append(r);print(json.dumps(dict(frame=name,status=r['status'],kernel=len(r.get('complete_multiplier_kernel',[])),image_passes=sum(c['image_pass'] for c in r.get('C_cases',[])))),flush=True)
    witness=HERE/'fusion_gpu_jobs_v1/original_witness_inputs.json.gz'
    with gzip.open(witness,'rt') as f:xs=json.load(f)['xs']
    p=Program(NATIVE.read_text());cuts=[26939,26942,26981,26994,26995,26998,27008]
    cap=captures(p,set(cuts),xs,formal=True,include_classical=True);nf=(1<<len(xs))-1
    g=mul(cap[26942]['q35'],cap[26942]['q9']);assert set(g)<={0}
    assert cap[26939]['q40']=={}
    native=Span();native.add(nf,'constant')
    for q in range(44):
        if q!=35:
            assert set(cap[26939][f'q{q}'])<={0}
            native.add(cap[26939][f'q{q}'].get(0,0),f'q{q}')
    r=necessary_two(native,g.get(0,0),xs);r.update(frame='all_native_owners_except_q35_at26939',target='wrap_g',domain='original35184_inputs_zero_HMR_branch')
    records.append(r);print(json.dumps(dict(frame=r['frame'],status=r['status'],kernel=len(r.get('complete_multiplier_kernel',[])),image_passes=sum(c['image_pass'] for c in r.get('C_cases',[])))),flush=True)
    late=[]
    for cut in [26981,26994,26995,26998,27008]:
        frame={f'q{q}':cap[cut][f'q{q}'] for q in range(44)}
        # q35 is the unavailable logical value. Restore its pre-first-read A7,
        # granting all other unchanged native owners only.
        frame['q35']=cap[26939]['q35'];r=restore(frame,'q35',nf,xs)
        late.append(dict(cut=cut,result=r,scope='All other unchanged native owners; zero-HMR necessary chart.'))
        print(json.dumps(dict(cut=cut,status=r['status'],products=r.get('paid_products'))),flush=True)
    result=dict(notice=NOTICE,status='IMPLICIT_A7_FIRST_READ_AND_LATE_ENDPOINT_SCREEN',
        numerical_verification='AGENT_VERIFIED_ROOT_REPLAY_PENDING',qualified=False,
        source_sha256=sha(__file__),native_sha256=NATIVE_SHA,table_sha256=sha(TABLE),
        original_witness_sha256=sha(witness),component_rows=4096,original_witness_rows=len(xs),
        initial_retire_cut=24294,original_first_read=26939,original_wrap_product=26942,
        native_wrap_formula='(A7+v5)*(D7+v5+1)',native_wrap_target='q40',
        native_wrap_retirement=26981,native_wrap_feedback=26994,
        late_A7_required_before=27008,wrap_tests=records,late_A7_tests=late,
        no_actual_replacement_emitted=True,no_phase_or_global_width_sufficiency_claim=True,
        model_target_new_products=3,old_wrap_products_removed=1,modelled_cost_delta='2',
        outside_scope='Changed retained overflow products, additional retained history, and different mixed implicit-owner representations.')
    (args.out/'REPORT.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')


if __name__=='__main__':main()
