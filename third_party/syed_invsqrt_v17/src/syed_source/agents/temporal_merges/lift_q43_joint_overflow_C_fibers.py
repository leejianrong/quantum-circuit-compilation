# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Lift every supplied necessary C survivor to its complete product fiber.

Each completed C certificate is written atomically. A decomposable witness
is only a two-product prefix; remaining outputs, phases and width are owed.
"""
import argparse
import gzip
import json
import sys
import time
from collections import Counter
from itertools import combinations
from pathlib import Path
from temporal_core import NOTICE,Program,Span,captures,mul,comb,bits,sha,affine_preimage
from synthesize_q43_joint_overflow_prefix import component,SOLVER
from explore_q43_implicit_A7_read import NATIVE,NATIVE_SHA

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(SOLVER.parent))
from fixed_factor_plucker import affine_forms,complete_bivector


def atomic(path,data):
    temp=path.with_suffix(path.suffix+'.tmp')
    raw=(json.dumps(data,sort_keys=True,separators=(',',':'))+'\n').encode()
    if path.suffix=='.gz':
        with temp.open('wb') as f:
            with gzip.GzipFile(fileobj=f,mode='wb',mtime=0,filename='') as z:z.write(raw)
    else:temp.write_bytes(raw)
    temp.replace(path)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prefix-report',type=Path,required=True)
    ap.add_argument('--domain',choices=['component','native'],required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--maximum-fiber-dimension',type=int,default=160)
    ap.add_argument('--max-seconds',type=float,default=480)
    args=ap.parse_args();args.out.mkdir(exist_ok=False);started=time.monotonic()
    parent=json.loads(args.prefix_report.read_text());frame=parent[args.domain]
    source=next(r for r in frame['records'] if r['output_mask']==12)
    candidates=[r for r in source['result']['C_cases'] if r['image_pass']]
    if args.domain=='component':
        xs,full,val,E,F,G0,G1,G2=component()
    else:
        witness=HERE/'fusion_gpu_jobs_v1/original_witness_inputs.json.gz'
        with gzip.open(witness,'rt') as f:xs=json.load(f)['xs']
        full=(1<<len(xs))-1;assert sha(NATIVE)==NATIVE_SHA
        p=Program(NATIVE.read_text());caps=captures(p,{26939,26942,26953,26957,27008},xs,formal=True)
        E=Span();E.add(full,'constant')
        for q in range(44):
            if q!=35:E.add(caps[26939][f'q{q}'].get(0,0),f'q{q}')
        E.add(caps[27008]['q28'].get(0,0),'S6_retained_product')
        F=caps[26939]['q35'].get(0,0);Gs=[]
        for cut in [26942,26953,26957]:
            o=p.operations[cut];v=mul(caps[cut][o.arguments[0]],caps[cut][o.arguments[1]])
            assert set(v)<={0};Gs.append(v.get(0,0))
        G0,G1,G2=Gs
    assert E.descriptors==source['result']['affine_basis']
    Z=G1^G2;records=[]
    for index,case in enumerate(candidates):
        if time.monotonic()-started>args.max_seconds:break
        cm=int(case['C_mask'],16);C=comb(E.columns,cm)
        assert [E.descriptors[j] for j in bits(cm)]==case['C_terms']
        pivot=next(j for j in bits(cm) if j)
        controls=[v for j,v in enumerate(E.columns) if j and j!=pivot]
        names=[n for j,n in enumerate(E.descriptors) if j and j!=pivot]
        free=Span()
        for j,v in enumerate(E.columns):free.add(v,('E',j))
        for j,v in enumerate(E.columns):free.add(C&v,('D',j))
        pairs=list(combinations(range(len(controls)),2));weighted=[C&controls[i]&controls[j] for i,j in pairs]
        point,kernel,rank=affine_preimage([free.normal(v) for v in weighted],free.normal(Z));assert point is not None
        row=dict(notice=NOTICE,index=index,domain=args.domain,original_rows=len(xs),
            parameter_mask=case['parameter_mask'],C_mask=case['C_mask'],C_terms=case['C_terms'],
            free_affine_basis=E.descriptors,gauged_controls=names,correction_rank=len(free.columns),
            weighted_image_rank=rank,complete_product_fiber_dimension=len(kernel),
            point_hex=hex(point),kernel_hex=list(map(hex,kernel)))
        if len(kernel)>args.maximum_fiber_dimension:
            result=dict(status='OPEN_ABOVE_DECLARED_FIBER_LIMIT')
        else:
            result=complete_bivector(len(controls),affine_forms(point,kernel,len(pairs)),len(kernel),max_enumerate=16)
        row['result']=result
        if result['status']=='DECOMPOSABLE_WITNESS':
            am,bm=result['factor_masks'];A=comb(controls,am);B=comb(controls,bm);H=A&B
            correction=free.solve(Z^(C&H));assert correction is not None
            dt=[];et=[];D=EE=0
            for j in bits(correction):
                kind,k=free.descriptors[j]
                if kind=='D':D^=E.columns[k];dt.append(E.descriptors[k])
                else:EE^=E.columns[k];et.append(E.descriptors[k])
            assert Z==(C&(H^D))^EE
            row['actual_two_product_prefix']=dict(A=[names[j] for j in bits(am)],B=[names[j] for j in bits(bm)],C=case['C_terms'],D=dt,E=et)
            row['joint_remaining_three_products_unproved']=True
        path=args.out/f'C_{case["parameter_mask"]:05d}.json.gz';atomic(path,row)
        records.append(dict(index=index,parameter_mask=case['parameter_mask'],C_mask=case['C_mask'],
            C_terms=case['C_terms'],status=result['status'],fiber_dimension=len(kernel),
            certificate=path.name,certificate_sha256=sha(path)))
        report=dict(notice=NOTICE,status='COMPLETE_DECLARED_SURVIVOR_FIBER_LIFT' if len(records)==len(candidates) else 'ACTIVE_OR_CAPPED_SURVIVOR_FIBER_LIFT',
            numerical_verification='AGENT_VERIFIED_ROOT_REPLAY_PENDING',qualified=False,
            source_sha256=sha(__file__),factor_solver_sha256=sha(SOLVER),prefix_report_sha256=sha(args.prefix_report),
            domain=args.domain,original_rows=len(xs),native_reference_sha256=NATIVE_SHA,
            output_parity=['G1','G2'],declared_C_survivors=len(candidates),completed_C_fibers=len(records),
            status_counts=dict(Counter(r['status'] for r in records)),records=records,
            complete_scalar_two_product_negative=len(records)==len(candidates) and all(r['status']=='COMPLETE_NEGATIVE_FIXED_FACTOR' for r in records),
            actual_joint_five_product_circuit_qualified=False,seconds=time.monotonic()-started)
        atomic(args.out/'REPORT.json',report)
        if index%10==0 or result['status']=='DECOMPOSABLE_WITNESS':print(json.dumps(dict(index=index,status=result['status'],fiber=len(kernel),seconds=time.monotonic()-started)),flush=True)
    if records:print(json.dumps({k:v for k,v in report.items() if k!='records'}),flush=True)


if __name__=='__main__':main()
