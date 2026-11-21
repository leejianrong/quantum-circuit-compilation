# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
"""Port the owner's two-lane joint inverse shift to the source-built 12-bit generator."""
import numpy as np
import kickmix as km
from normalizer import Basis, route, linear

DATA=((42,2,4,6,8,39,12,14,35,41,10),(1,3,5,36,11,37,38,15,40,26,27))

def optimize(text):
    ops=text.splitlines()
    i=ops.index('CSWAP q19 q4 q10')
    j=ops.index('HMR q23 b1193',i)
    old=ops[i:j]
    assert sum(g.startswith('CSWAP') for g in old)==34
    assert all(g.startswith(('CX ','CSWAP ')) for g in old)
    assert all(f'b{bit}' not in text for bit in (26000,26001))
    # Eleven exponent classes and boundary checks make the physical thermometer map explicit.
    xs=[]; groups=[];rng=np.random.default_rng(773)
    for k in range(11):
        lo=1<<(20-2*k);hi=min(3133452,4*lo-1)
        vals=np.r_[lo,hi,rng.integers(lo,hi+1,62)]
        xs.extend(vals);groups.extend([k]*len(vals))
    xs=np.array(xs,dtype=np.uint64);groups=np.array(groups)
    w=[km.q(t) for t in range(43)];sim=km.Simulator(len(xs),seed=723)
    sim.write_across_shots(w,(xs[None,:]>>np.arange(43,dtype=np.uint64)[:,None]&1).astype(bool))
    sim.do(km.Circuit('\n'.join(ops[:i])));state=sim.read_across_shots(w)
    chart=Basis();chart.insert(2047,1<<43)
    for h,row in enumerate(state):
        if h in DATA[0]+DATA[1]:continue
        vals=[np.unique(row[groups==k]) for k in range(11)]
        if all(len(v)==1 for v in vals):
            chart.insert(sum(int(v[0])<<k for k,v in enumerate(vals)),1<<h)
    assert all(not state[t].any() for t in (7,9,13,16))
    def pieces(v,target):
        mask=chart.express(v)
        assert mask is not None,(target,v)
        return [f'CX q{t} q{target}' for t in range(43) if mask>>t&1]+([f'X q{target}'] if mask>>43&1 else [])
    # The returned exponent alphabet spans 8 dimensions. This one product completes the selectors.
    src1=pieces(510,13);src2=pieces(1920,16)
    pro=src1+src2+['CCX q13 q16 q7'];epi=['HMR q7 b26000','CZ q13 q16 if b26000']+src2[::-1]+src1[::-1]
    chart.insert(510&1920,1<<7)
    L,G=route();p=G[-1][1]
    enc=[f'{gate} q{q[a]} q{q[b]}' for q in DATA for gate,a,b in L];out=enc.copy()
    sel=pieces(1,9);out+=sel
    high0,high1=[q[10] for q in DATA]
    out.extend([f'CX q{high0} q{high1}',f'HMR q{high1} b26001','PUSH_CONDITION if b26001','Z q9'])
    for q in DATA:
        for a in range(10):
            if p>>a&1:out+= [f'Z q{q[a]}',f'CZ q9 q{q[a]}']
    out+=['POP_CONDITION']
    data=[DATA[0][a] for a in range(10) if p>>a&1]
    parity=[f'CX q{w} q{data[0]}' for w in data[1:]]
    out+=parity+['X q9',f'CCX q9 q{data[0]} q{high0}','X q9']+parity[::-1]
    out+=[f'CX q{high0} q{high1}',f'CX q9 q{high1}']+sel[::-1]
    for q in DATA:
        walk=[]
        for gate,a,b,v in G[:12]:
            c=pieces(v,9);walk+=c+[f'{gate} q9 q{q[a]} q{q[b]}']+c[::-1]
        for a,b,v in ((8,9,438),(9,8,877),(8,9,1316)):
            c=pieces(v,9);walk+=c+[f'CCX q9 q{q[a]} q{q[b]}']+c[::-1]
        for gate,a,b in linear([3,2]):
            walk.append(f'{gate} q{q[8+a]} q{q[8+b]}')
        out+=walk[::-1]
    out+=enc[::-1];tail=[g for g in old if g.startswith('CX ')]
    block=pro+out+epi+tail
    assert sum(g.startswith(('CCX ','CSWAP '))for g in block)==32
    return '\n'.join(ops[:i]+block+ops[j:])+'\n'
