# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
"""Shift a supported degree-ten binary polynomial by x**k using residues of periods 8 and 3."""
import re
import kickmix as km
import numpy as np

def matrix_rows():
    f=[]
    for i in range(11):
        ch=1<<(i%8);p=[1,2,3][i%3]
        f.append(ch|(p<<8)|((i==10)<<10))
    return [sum((f[i]>>j&1)<<i for i in range(11))for j in range(11)]

def linear(rows):
    n=len(rows);r=rows.copy();op=[]
    for j in range(n):
        p=next(i for i in range(j,n)if r[i]>>j&1)
        if p!=j:r[j],r[p]=r[p],r[j];op.append(('SWAP',j,p))
        for i in range(n):
            if i!=j and r[i]>>j&1:r[i]^=r[j];op.append(('CX',j,i))
    assert r==[1<<i for i in range(n)]
    return list(reversed(op))

def vector(u,ops):
    for kind,a,b in ops:
        if kind=='CX':u^=((u>>a)&1)<<b
        elif ((u>>a)^(u>>b))&1:u^=(1<<a)|(1<<b)
    return u

def route():
    g=[]
    for j in range(3):
        d=1<<j
        for i in range(8):
            if i&d:continue
            f=sum((((k>>j)&1)^int((i%d)<k%d))<<k for k in range(11));g.append(('CSWAP',i,i+d,f))
    mask=lambda fn:sum(int(fn(k))<<k for k in range(11))
    g.extend([('CCX',1+8,0+8,mask(lambda k:k%3==2)),('CCX',0+8,1+8,mask(lambda k:k%3!=0)),('CCX',1+8,0+8,mask(lambda k:k%3==1))])
    l=linear(matrix_rows())
    # Constant coefficient of (P mod Q) from transformed coordinates with degree-10 coordinate cleared.
    r0=sum((vector(1<<j,list(reversed(l)))&1)<<j for j in range(10))
    g.append(('ADD',r0,10,mask(lambda k:k>0)))
    return l,g

def shift(x,k):
    l,g=route();w=vector(x,l)
    for typ,a,b,f in g:
        if f>>k&1:
            if typ=='ADD':w^=((w&a).bit_count()&1)<<b
            else:w=vector(w,[('SWAP' if typ=='CSWAP'else 'CX',a,b)])
    return vector(w,list(reversed(l)))

def emit(q,ctrl,spare,kchart,back=False,override=None):
    l,g=route();l0=[]
    for op,a,b in l:l0.append(f'{op} q{q[a]} q{q[b]}')
    gs=[];lines=[]
    for idx,(op,a,b,tt) in enumerate(g):
        if override is not None:tt=override[idx]
        s=kchart.express(tt)
        if s is None:raise ValueError(hex(tt))
        pref=[f'CX q{j} q{ctrl}' for j in range(43)if s>>j&1]
        if s>>43&1:pref.append(f'X q{ctrl}')
        if op=='ADD':
            src=[j for j in range(10)if a>>j&1]
            add=[f'CX q{q[j]} q{q[src[0]]}'for j in src[1:]]
            blk=add+[f'CCX q{ctrl} q{q[src[0]]} q{q[b]}']+add[::-1]
        else:blk=[f'{op} q{ctrl} q{q[a]} q{q[b]}']
        gs.extend(pref+blk+pref[::-1])
    lines=l0+gs+l0[::-1]
    return (lines[::-1] if back else lines)
class Basis:
    def __init__(self):self.piv={}
    def insert(self,x,t):
        while x:
            i=x.bit_length()-1
            if i not in self.piv:self.piv[i]=(x,t);return
            y,u=self.piv[i];x^=y;t^=u
    def express(self,x):
        v=0
        while x:
            i=x.bit_length()-1
            if i not in self.piv:return None
            y,u=self.piv[i];x^=y;v^=u
        return v

def exponent_samples():
    samples=[]
    for exponent in range(11):
        lo=1<<(20-2*exponent);hi=min(3133452,4*lo-1)
        edges=np.arange(max(lo,2*lo-4),min(hi+1,2*lo+5))
        random=np.random.default_rng(exponent+22)
        samples.extend(np.r_[lo,hi,np.resize(edges,10),random.integers(lo,hi+1,244)])
    return np.asarray(samples,dtype=np.uint64),np.repeat(np.arange(11),256)

def optimize(text):
    lines=text.splitlines()
    xs,k=exponent_samples()
    start=lines.index('CSWAP q26 q0 q2')-9
    sim=km.Simulator(len(xs),seed=479);qs=[km.q(j)for j in range(43)]
    sim.write_across_shots(qs,((xs[None,:]>>np.arange(43,dtype=np.uint64)[:,None])&1).astype(bool))
    sim.do(km.Circuit('\n'.join(lines[:start-1])));w=sim.read_across_shots(qs)
    q=list(range(0,22,2));basis=Basis();basis.insert(2047,1<<43)
    for j,row in enumerate(w):
        if j in q or j==37:continue
        f=[np.unique(row[k==z])for z in range(11)]
        if all(len(bits)==1 for bits in f):
            tt=sum(int(bits[0])<<i for i,bits in enumerate(f))
            if tt:basis.insert(tt,1<<j)
    assert not np.any(w[37]), 'The shared selector must start at zero.'
    old=lines[start:start+163];positions=[i for i,x in enumerate(old)if x.startswith('CSWAP ')]
    assert len(positions)==17 and all(all(int(n)%2==0 for n in re.findall(r'q(\d+)',old[i])[1:])for i in positions)
    for z in range(11):
        for j in range(11-z):assert shift(1<<j,z)==1<<(j+z)
    lines[start:start+163]=emit(q,37,38,basis)+[x for i,x in enumerate(old)if i not in positions]
    return '\n'.join(lines)+'\n'
