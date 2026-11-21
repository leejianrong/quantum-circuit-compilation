# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Try literal carry-factor two-product realizations of G1+G2.

The two declared serial factors are D9+v5 and its complement. This is a
bounded constructive factor attempt, outside the fixed wrap scalar scope.
No negative of the unrestricted joint five-product route is inferred.
"""
import argparse
import gzip
import json
import sys
from itertools import combinations
from pathlib import Path
from temporal_core import NOTICE,Span,bits,comb,sha,affine_preimage
from explore_q43_implicit_A7_read import NATIVE_SHA,TABLE,quadratic
from search_q43_v9_retained_bits_prefix import quadratic_tail

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SOLVER=ROOT/'restored/research_v9/second_seed_and_phases/fixed_factor_plucker.py'
sys.path.insert(0,str(SOLVER.parent))
from fixed_factor_plucker import affine_forms,complete_bivector


def component():
    d=json.loads(TABLE.read_text());vs=list(range(4096));full=(1<<4096)-1
    truth=lambda seq,j:sum(((int(v)>>j)&1)<<i for i,v in enumerate(seq))
    val={f'D{i}':truth(d['D'],i) for i in range(13)}
    val.update({f'S{i}':truth([d['S'][v>>6] for v in vs],i) for i in range(7)})
    val.update({f'v{i}':truth(vs,i) for i in range(6)})
    F=truth([d['A'][v>>6] for v in vs],7);s=val['v5']
    G0=(F^s)&(val['D7']^s^full);G1=G0&(val['D8']^s^full);G2=G1&(val['D9']^s^full)
    E=Span();E.add(full,'constant')
    for n in [f'D{i}' for i in range(13)]+[f'S{i}' for i in range(7)]+[f'v{i}' for i in range(6)]:E.add(val[n],n)
    return vs,full,val,E,F,G0,G1,G2


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--maximum-fiber-dimension',type=int,default=160)
    args=ap.parse_args();args.out.mkdir(exist_ok=False)
    vs,full,val,E,F,G0,G1,G2=component();Z=G1^G2;records=[]
    for offset in [0,1]:
        cm=(1<<E.descriptors.index('D9'))^(1<<E.descriptors.index('v5'))^offset
        C=comb(E.columns,cm);pivot=next(j for j in bits(cm) if j)
        controls=[v for j,v in enumerate(E.columns) if j and j!=pivot]
        names=[n for j,n in enumerate(E.descriptors) if j and j!=pivot]
        free=Span()
        for j,v in enumerate(E.columns):free.add(v,('E',j))
        for j,v in enumerate(E.columns):free.add(C&v,('D',j))
        pairs=list(combinations(range(len(controls)),2))
        weighted=[C&controls[i]&controls[j] for i,j in pairs]
        point,kernel,rank=affine_preimage([free.normal(v) for v in weighted],free.normal(Z))
        r=dict(case=offset,C_terms=[E.descriptors[j] for j in bits(cm)],
            correction_rank=len(free.columns),weighted_image_rank=rank,complete_bivector_fiber_dimension=len(kernel))
        if point is None:r['status']='NEGATIVE_DECLARED_C_LINEAR_IMAGE'
        elif len(kernel)>args.maximum_fiber_dimension:r['status']='OPEN_ABOVE_DECLARED_FIBER_LIMIT'
        else:
            result=complete_bivector(len(controls),affine_forms(point,kernel,len(pairs)),len(kernel),max_enumerate=16)
            record=dict(notice=NOTICE,control_names=names,point_hex=hex(point),kernel_hex=list(map(hex,kernel)),result=result)
            path=args.out/f'CASE_{offset}_PLUCKER.json.gz'
            with gzip.open(path,'wt') as f:json.dump(record,f,sort_keys=True)
            r.update(status=result['status'],fiber_certificate=path.name,fiber_certificate_sha256=sha(path))
            if result['status']=='DECOMPOSABLE_WITNESS':
                am,bm=result['factor_masks'];A=comb(controls,am);B=comb(controls,bm);H=A&B
                correction=free.solve(Z^(C&H));assert correction is not None
                D=EE=0;dt=[];et=[]
                for j in bits(correction):
                    kind,k=free.descriptors[j]
                    if kind=='D':D^=E.columns[k];dt.append(E.descriptors[k])
                    else:EE^=E.columns[k];et.append(E.descriptors[k])
                assert Z==(C&(H^D))^EE
                r['actual_two_product_prefix']=dict(A=[names[j] for j in bits(am)],B=[names[j] for j in bits(bm)],C=r['C_terms'],D=dt,E=et)
                available=E.copy();available.add(H,'H');available.add(Z,'Z_G1_plus_G2')
                Q=quadratic(available);checks=[]
                for mask in range(1,8):
                    target=comb([F,G0,G1],mask);member=Q.solve(target) is not None
                    rr=dict(output_mask=mask,target_quadratic=member)
                    if member:rr['constructive_quadratic_result']=quadratic_tail(available,target,full,vs)
                    checks.append(rr)
                r['next_saturated_product_checks']=checks
        records.append(r);print(json.dumps({k:v for k,v in r.items() if k not in ['next_saturated_product_checks']}),flush=True)
        (args.out/'REPORT.json').write_text(json.dumps(dict(notice=NOTICE,status='BOUNDED_ACTUAL_JOINT_OVERFLOW_PREFIX_ATTEMPTS',
            numerical_verification='AGENT_VERIFIED_ROOT_REPLAY_PENDING',qualified=False,
            source_sha256=sha(__file__),solver_sha256=sha(SOLVER),native_reference_sha256=NATIVE_SHA,table_sha256=sha(TABLE),
            component_rows=4096,initial_basis=E.descriptors,target='G1+G2',records=records,
            actual_joint_five_product_plan=None,modelled_cost_delta_if_completed='2',
            outside_scope='Every other serial factor C, other helper-fiber representatives after a first witness, and other joint overflow chronologies.'),indent=2,sort_keys=True)+'\n')


if __name__=='__main__':main()
