# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Independent complete integer model, starting before the u12 shortcut.

This test oracle uses the original signed remainder recurrence from j9,
not the native initializer or the native endpoint alias implementation.
"""
from common import MODEL,MODEL_SHA
import numpy as np

MAX_X=3133452
C_TABLE=np.array(MODEL['C'],dtype=np.int64)
SEED_TABLE=np.array(MODEL['U0'],dtype=np.int64)


def phase_units(xs,*,return_chart=False):
    """Return exact target model integers in2^-37 turns, modulo one turn."""
    x=np.asarray(xs,dtype=np.int64);assert np.all((x>=1)&(x<=MAX_X))
    leading=np.searchsorted(np.left_shift(np.ones(22,dtype=np.int64),np.arange(22)),x,side='right')-1
    exponent=(21-leading)//2;norm=x<<(2*exponent)
    Q=np.sqrt(norm<<4).astype(np.int64)
    assert np.all(Q*Q<=norm<<4) and np.all((Q+1)*(Q+1)>norm<<4),'Integer root boundary'
    v=Q-4096;d=2*Q+1;h=((norm<<6)-d*d)//64
    C=C_TABLE[v];U0=SEED_TABLE[v];q=h+512
    rootclass=(v*(v+1)//2)&7
    seed=-np.ones(len(x),dtype=np.int64)
    for i in range(3):seed+=(2*((rootclass>>i)&1)-1)*((C+(1<<(11-i)))>>(12-i))
    assert np.array_equal(seed,U0),'Independent seed formula disagrees with frozen model'
    F=np.zeros(len(x),dtype=np.int64)
    for i in range(10):
        shift=8-i
        term=(C+(1<<(shift-1)))>>shift if shift>0 else C if shift==0 else 2*C+1
        F+=(2*((q>>i)&1)-1)*term
    U=U0-F//2;assert np.all((-16384<=U)&(U<16384))
    product=U&32767;r=4096-d
    phase=np.full(len(x),-((1<<37)-(1<<29)),dtype=np.int64)
    for j in range(9,36):
        sign=(r<0).astype(np.int64);phase-=sign<<(37-j)
        if j<=23:
            bit=(product>>(23-j))&1
            if j==9:bit=-bit
            raw=2*r+(2*sign-1)*d+bit
        elif j==24:raw=2*r+(2*sign-1)*d
        else:
            k=j-26 if j>=28 else 0;V=d//2
            A=((((V>>(k+1))+((V>>k)&1))<<(k+1))-(V&1))if k else V
            u=(r-1)//2;raw=2*(2*u+sign+(2*sign-1)*A)+1
        nextu=raw//2
        assert np.all((-8192<=nextu)&(nextu<8192)),('Physical remainder overflow',j)
        nextu=((nextu+8192)&16383)-8192;r=2*nextu+(raw&1)
    phase-=(r<0).astype(np.int64)<<1;p=(phase-1)&((1<<37)-1)
    word=((p<<exponent)+(p>>(27-exponent)))&((1<<37)-1)
    if return_chart:return word,dict(n=norm,v=v,h=h,flags=exponent,D=C//2,seed=seed,U=U)
    return word.astype(np.uint64)
