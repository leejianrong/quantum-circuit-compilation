# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Exact full-domain accuracy sensitivity of coarser divider/product integer models.
No circuit equivalence or resource-saving claim is made by this screen.
"""
from pathlib import Path
import argparse,hashlib,json,sys,time
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'runtime/tools'))
import refit_angles as ra


def coarse_word(v,U,exponent,extra_k=0,round_product=0,last_row=35,up_rows=(),extra_start=25,k_overrides=None,
                product_k_rows=None,product_rounding='nearest',D=None,seed=None,h=None):
    d=2*(v+4096)+1
    if product_k_rows:
        from product_precision import product_word,signed_u
        assert D is not None and seed is not None and h is not None
        U=signed_u(product_word(D,seed,h,product_k_rows,product_rounding))
    if round_product:
        U=((U+(1<<(round_product-1)))>>round_product)<<round_product
    product=U&32767;r=4096-d
    phase=np.full(len(v),-((1<<37)-(1<<29)),dtype=np.int64)
    for j in range(9,last_row+1):
        sign=(r<0).astype(np.int64);phase-=sign<<(37-j)
        if j<=23:
            bit=(product>>(23-j))&1
            if j==9:bit=-bit
            raw=2*r+(2*sign-1)*d+bit
        elif j==24:raw=2*r+(2*sign-1)*d
        else:
            k=min(11,max(0,j-26)+extra_k) if extra_k and j>=extra_start else (j-26 if j>=28 else 0)
            if k_overrides is not None:k=int(k_overrides.get(j,k_overrides.get(str(j),k)))
            V=d//2
            A=((V>>(k+1))+((V>>k)&1))<<(k+1)
            if k:A-=V&1
            else:A=V
            if j in up_rows:A=(((V>>(k+1))+1)<<(k+1))-(V&1)
            u=(r-1)//2;raw=2*(2*u+sign+(2*sign-1)*A)+1
        nextu=((raw//2+8192)&16383)-8192;r=2*nextu+(raw&1)
    phase-=(r<0).astype(np.int64)<<(36-last_row)
    # Retain the original fixed midpoint. A best global shift is screened below.
    p=(phase-1)&((1<<37)-1)
    return ((p<<exponent)+(p>>(27-exponent)))&((1<<37)-1)


def fitted_phase(word,k,angles):
    z=word&((1<<27)-1);P=((z>>k)|(z<<(27-k)))&((1<<27)-1)
    W=P>>1;r=((W<<k)|(W>>(26-k)))&((1<<26)-1)
    phase=np.full(len(r),angles[33],dtype=np.int64)
    for i in range(26):phase+=((r>>i)&1)*angles[i]
    for j in range(7):phase+=((r>>j)&1)*(k>j)*angles[26+j]
    for j in (7,8,9):phase+=((r>>j)&1)*(k>j)*(1<<(40+j))
    return phase&((1<<50)-1)


def screen(phase,target,tol):
    error=((phase.astype(np.uint64)<<np.uint64(14))-target).view(np.int64)
    margin=tol.astype(np.int64)-np.abs(error)
    lower=int(np.max(-tol.astype(np.int64)-error));upper=int(np.min(tol.astype(np.int64)-error))
    shift50=int(round((lower+upper)/2/16384));shift=shift50*16384
    shifted=tol.astype(np.int64)-np.abs(error+shift)
    worst=int(np.argmin(margin));worst2=int(np.argmin(shifted))
    return {'full_domain_inputs':len(phase),'fixed_angles_failures':int(np.sum(margin<0)),'fixed_angles_minimum_margin_units64':int(margin[worst]),'fixed_angles_worst_x':worst+1,'best_global_shift_units50':shift50,'best_global_shift_failures':int(np.sum(shifted<0)),'best_global_shift_minimum_margin_units64':int(shifted[worst2]),'best_global_shift_worst_x':worst2+1,'global_feasible_interval_units64':[lower,upper],'phase50_sha256':hashlib.sha256(phase.astype('<u8').tobytes()).hexdigest()}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--cases',default='baseline,k1,k2,k3,k4,u1,u2,u3,j34,j33,j32');ap.add_argument('--chunk',type=int,default=65536);a=ap.parse_args();began=time.monotonic()
    _,_,oracle=ra.load_everything();angles=list(map(int,oracle.ANGLES));records=[];hashes=[]
    for case in a.cases.split(','):
        params={'extra_k':0,'round_product':0,'last_row':35}
        if case.startswith('k'):
            base,_,up=case.partition('up');base,_,start=base.partition('from');params['extra_k']=int(base[1:])
            if start:params['extra_start']=int(start)
            if up:params['up_rows']=list(range(25,36)) if up=='all' else [int(x) for x in up.split('_')]
        elif case.startswith('u'):params['round_product']=int(case[1:])
        elif case.startswith('j'):params['last_row']=int(case[1:])
        records.append({'case':case,'parameters':params,'fixed_angles_failures':0,'fixed_angles_minimum_margin_units64':2**63-1,'fixed_angles_worst_x':None,'lower':-2**63+1,'upper':2**63-1});hashes.append(hashlib.sha256())
    a.out.parent.mkdir(parents=True,exist_ok=True)
    for first in range(1,ra.MAX_X+1,a.chunk):
        stop=min(first+a.chunk,ra.MAX_X+1);xs=np.arange(first,stop,dtype=np.uint64)
        original,chart=oracle._model.phase_units(xs,return_chart=True);v=np.asarray(chart['v'],dtype=np.int64);U=np.asarray(chart['U'],dtype=np.int64);k=np.asarray(chart['flags'],dtype=np.int64)
        target,tol=ra.reference(xs)
        for row,digest in zip(records,hashes):
            word=coarse_word(v,U,k,**row['parameters'])
            if row['case']=='baseline':assert np.array_equal(word.astype(np.uint64),np.asarray(original,dtype=np.uint64))
            phase=fitted_phase(word,k,angles)
            if row['case']=='baseline':assert np.array_equal(phase.astype(np.uint64),oracle.phase_units50(xs))
            digest.update(phase.astype('<u8').tobytes());error=((phase.astype(np.uint64)<<np.uint64(14))-target).view(np.int64);margin=tol.astype(np.int64)-np.abs(error)
            row['fixed_angles_failures']+=int(np.sum(margin<0));worst=int(np.argmin(margin))
            if int(margin[worst])<row['fixed_angles_minimum_margin_units64']:
                row['fixed_angles_minimum_margin_units64']=int(margin[worst]);row['fixed_angles_worst_x']=first+worst
            row['lower']=max(row['lower'],int(np.max(-tol.astype(np.int64)-error)));row['upper']=min(row['upper'],int(np.min(tol.astype(np.int64)-error)))
            shift50=int(round((row['lower']+row['upper'])/2/16384));shift=shift50*16384
            row['best_global_shift_units50']=shift50;row['best_global_shift_minimum_margin_units64']=min(row['upper']-shift,shift-row['lower']);row['best_global_shift_feasible']=row['best_global_shift_minimum_margin_units64']>=0
            row['inputs_checked']=stop-1;row['phase50_prefix_sha256']=digest.hexdigest()
        full=stop==ra.MAX_X+1
        status='EXACT_INTEGER_ACCURACY_SENSITIVITY_NOT_CIRCUIT_PROOF' if full else 'PARTIAL_EXACT_INTEGER_SCREEN_NOT_CIRCUIT_PROOF'
        a.out.write_text(json.dumps({'status':status,'official_verifier':False,'no_submission':True,'elapsed_seconds':time.monotonic()-began,'chunk_inputs':a.chunk,'records':records},indent=2)+'\n')
        print(json.dumps({'checked_inputs':stop-1,'seconds':time.monotonic()-began,'fixed_failures':{r['case']:r['fixed_angles_failures'] for r in records}}),flush=True)
    print(json.dumps(records),flush=True)
if __name__=='__main__':main()
