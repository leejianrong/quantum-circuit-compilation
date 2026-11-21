# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Consume normalized22-bit norm into nearest-odd-root v12 and residual h10.

For norm in [2**20,2**22), Q=isqrt(16*norm), d=2Q+1=8193+2v,
h=(64*norm-d*d)//64. Output h occupies the original low10 wires;
v occupies the original high12 wires. Four appended zero wires are reset.
The non-restoring remainder sign is the complement of the newest root bit,
so each old sign wire becomes an explicit root wire without a history tape.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'fusion_handoff/official/kickmix'),str(ROOT/'cleanroom/baseline_stage97/engine')]
import kickmix as km
from fusion.arithmetic import add


def _arr(wires):return km.array(list(wires))


def _add_leading_one(builder, target, *, inverse=False):
    """Add/subtract2**(n-2) modulo2**n, entirely Clifford."""
    if len(target)<2:raise ValueError('Leading-one add needs two target positions')
    if inverse:
        builder.x(target[-2]);builder.cx(target[-2],target[-1])
    else:
        builder.cx(target[-2],target[-1]);builder.x(target[-2])


def _low_prepare(builder, low, b, *, inverse=False):
    """Low three bits add3 mod8. Return OR and carry, both quadratic-cleanable."""
    x0,x1,x2=low
    u,c=builder.alloc_qubits(2)
    if inverse:
        # After the low add3: u=1 XOR(y0*y1), cplus=u*(NOT y2).
        builder.x(u);builder.ccx(x0,x1,u)
        builder.x(x2);builder.ccx(u,x2,c);builder.x(x2)
    else:
        # Before the low add3: u=x0 OR x1, cplus=x2*u.
        builder.cx(x0,u);builder.cx(x1,u);builder.ccx(x0,x1,u)
        builder.ccx(x2,u,c)
        builder.cx(u,x2)
        builder.cx(x0,x1);builder.x(x1);builder.x(x0)
    builder.cx(b,c)
    return u,c


def _low_finish(builder, low, b, u, c, *, inverse=False):
    x0,x1,x2=low
    builder.cx(b,c)
    builder.x(x2);builder.del_and(u,x2,c);builder.x(x2)
    builder.free(c)
    if inverse:builder.cx(u,x2)
    builder.x(u);builder.del_and(x0,x1,u);builder.free(u)
    if inverse:
        builder.x(x0);builder.x(x1);builder.cx(x0,x1)


def _root_step(builder, remainder, older_root, b, *, initial=False, inverse=False):
    """One non-restoring step, after routing next inputpair into remainder[:2]."""
    low=list(remainder[:3]);high=list(remainder[3:])
    u,c=_low_prepare(builder,low,b,inverse=inverse)
    builder.cx(b,_arr(high))
    if inverse:
        if not initial:_add_leading_one(builder,high,inverse=True)
        add(builder,older_root,high,carry_in=c,subtract=True)
    else:
        add(builder,older_root,high,carry_in=c)
        if not initial:_add_leading_one(builder,high)
    builder.cx(b,_arr(high))
    _low_finish(builder,low,b,u,c,inverse=inverse)


def _low_remainder_xor(builder, Q, low):
    """XOR (-Q²-Q-1) mod16 into low, using one CCX and no ancilla."""
    q0,q1,q2,q3=Q[:4]
    builder.x(_arr(low))
    builder.cx(q0,low[1]);builder.cx(q1,low[1])
    builder.cx(q1,low[2]);builder.cx(q2,low[2])
    builder.cx(q3,low[3]);builder.cx(q2,low[3])
    builder.cx(q2,q0);builder.cx(q2,q1)
    builder.ccx(q0,q1,low[3])
    builder.cx(q2,q1);builder.cx(q2,q0)


def forward(builder, norm):
    norm=list(norm)
    if len(norm)!=22 or len(set(norm))!=22:raise ValueError('Expected22 distinct input wires')
    # First root digit is the known1. Its remainder is the top pair minus1.
    builder.x(norm[20]);builder.cx(norm[20],norm[21])
    remainder=norm[20:22];root=[]
    for j in range(1,13):
        pair=norm[20-2*j:22-2*j] if j<=10 else list(builder.alloc_qubits(2))
        if j==1:
            b=True;older=[];remainder=pair+remainder
        else:
            b=remainder[-1];builder.x(b)
            older=root;root=[b]+root;remainder=pair+remainder[:-1]
        _root_step(builder,remainder,older,b,initial=j==1)
    # Direct signed remainder conversion W=Rstd-Q-1, without an Rstd word.
    b=remainder[-1];builder.x(b);Q=[b]+root;W=remainder[:-1]
    high=W[1:]
    builder.cx(b,_arr(high))
    add(builder,root,high,carry_in=b)
    _add_leading_one(builder,high)
    builder.cx(b,_arr(high))
    _low_remainder_xor(builder,Q,W[:4])
    builder.free(_arr(W[:4]))
    if Q!=norm[10:] or W[4:]!=norm[:10]:raise AssertionError('In-place output layout changed')
    return dict(root=Q,residual=W[4:])


def inverse(builder, norm):
    norm=list(norm)
    if len(norm)!=22 or len(set(norm))!=22:raise ValueError('Expected22 distinct input wires')
    Q=norm[10:];W=list(builder.alloc_qubits(4))+norm[:10]
    _low_remainder_xor(builder,Q,W[:4])
    b=Q[0];root=Q[1:];high=W[1:]
    builder.cx(b,_arr(high))
    _add_leading_one(builder,high,inverse=True)
    add(builder,root,high,carry_in=b,subtract=True)
    builder.cx(b,_arr(high))
    builder.x(b);remainder=W+[b]
    for j in reversed(range(1,13)):
        pair=remainder[:2]
        if j==1:b=True;older=[]
        else:b=root[0];older=root[1:]
        _root_step(builder,remainder,older,b,initial=j==1,inverse=True)
        if j==1:remainder=remainder[2:]
        else:
            remainder=remainder[2:]+[b];builder.x(b);root=older
        if j>=11:builder.free(_arr(pair))
        elif pair!=norm[20-2*j:22-2*j]:raise AssertionError('Restored inputpair layout changed')
    if remainder!=norm[20:] or root:raise AssertionError('Initial remainder layout changed')
    builder.cx(norm[20],norm[21]);builder.x(norm[20])
    return norm
