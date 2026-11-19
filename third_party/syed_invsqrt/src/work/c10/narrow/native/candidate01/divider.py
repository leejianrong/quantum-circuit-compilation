# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Own Q49 consuming divider, direct u12, and endpoint phase.

The public API returns CURRENT logical product owners. No quantum owner is
silently deleted: consumed product information becomes a quotient-history
owner, and the matching inverse restores it before u12 cleanup.
"""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import dataclass,field
from fractions import Fraction
from common import km,cb,NARROW,checked_json,plan_from_json,array
from paired_arithmetic import forward_add,inverse_add
from quadratic_terms import xor_polynomial
from cyclic_phase import _erase_polynomial

LOCAL=checked_json(NARROW/'research/recompute_root/initializer_u12/local_algebra.json',
    '978c2adafd8d3355558a5e672982623372d459dec610273e1e43847681cc4c14')
P13=cb.factor_polynomial(5,False,13,set())
P14=cb.factor_polynomial(5,True,23,{(0,2),(0,3),(2,3)})
OLDQ0=cb.factor_polynomial(4,True,7,set())
OLDQ1=cb.factor_polynomial(4,True,12,{(0,1),(0,2),(1,2)})
HIGH=cb.factor_polynomial(6,False,39,{(3,4),(3,5),(4,5)})
FEED4=cb.factor_polynomial(4,False,3,{(0,1),(0,2),(1,2),(1,3),(2,3)})
FEED3=cb.factor_polynomial(3,False,3,{(0,1),(1,2)})
assert FEED4.and_count==FEED3.and_count==1


def _compose(plan,mapping,width):
    constant=int(plan.constant);linear=0;edges=set()
    for i in cb.bits(plan.linear):
        constant^=mapping[i][0];linear^=mapping[i][1]
    for i,j in plan.edges:
        ca,ma=mapping[i];cc,mc=mapping[j];constant^=ca*cc
        if ca:linear^=mc
        if cc:linear^=ma
        for a in cb.bits(ma):
            for b in cb.bits(mc):
                if a==b:linear^=1<<a
                else:
                    edge=tuple(sorted((a,b)))
                    if edge in edges:edges.remove(edge)
                    else:edges.add(edge)
    return cb.factor_polynomial(width,constant,linear,edges)


def _erase(builder,target,variables,plan):
    assert target not in variables
    m=builder.alloc_bits(1)[0]
    builder.hmr(target,m);cb.emit_phase(builder,variables,m,plan)
    builder.free(m);builder.free(target)


def initialize_u12(builder,v,P,u):
    """24 CCX forward; b13 and b14 become classical measurements, fully paid."""
    P=list(P);carry=list(builder.alloc_qubits(2))
    for q in (v[0],P[13],P[12]):builder.cx(q,u[0])
    env={'v0':v[0],'v1':v[1],'p12':P[12],'p13':P[13],'p14':P[14],
         'u0':u[0],'u1':u[1],'q0':carry[0],'q1':carry[1]}
    for item in LOCAL['best_low']['plans']:
        cb.emit_xor(builder,[env[name]for name in item['inputs']],env[item['output']],plan_from_json(item['plan']))
    variables=[v[0],v[1],P[12],u[0],u[1]]
    _erase(builder,P[13],variables,P13);_erase(builder,P[14],variables,P14)
    P[13]=None;P[14]=None
    for i in range(2,13):
        nextcarry=list(builder.alloc_qubits(2 if i<12 else 1))
        if i<12:
            aq=v[i];bq=v[i-1];builder.x(aq);builder.x(bq)
        else:
            # u13 is still zero and is restored by every source frame.
            aq=u[13];bq=v[11];builder.x(bq)
        q0,q1=carry
        builder.x(u[i])
        for q in (aq,bq,q0):builder.cx(q,u[i])
        for which,target in enumerate(nextcarry):
            cb.emit_xor(builder,[aq,bq,q0,q1],target,plan_from_json(LOCAL['high_forward'][f'next{which}']['plan']))
        variables=[aq,bq,u[i],nextcarry[0]]
        _erase(builder,q0,variables,OLDQ0);_erase(builder,q1,variables,OLDQ1)
        if i<12:builder.x(aq)
        builder.x(bq);carry=nextcarry
    builder.cx(carry[0],u[13]);builder.cx(u[13],carry[0]);builder.free(carry[0])
    return P


def cleanup_u12(builder,v,P,u):
    """One CCX; reconstruct product on current owners and HMR all u bits."""
    P=list(P);P[13],P[14]=list(builder.alloc_qubits(2))
    variables=[v[0],v[1],P[12],u[0],u[1]]
    cb.emit_xor(builder,variables,P[13],P13);cb.emit_xor(builder,variables,P[14],P14)
    def aa(i):return (1,1<<i)if 0<=i<12 else(0,0)
    def bb(i):return (1,0)if i in (0,13)else(1,1<<(i-1))
    for i in reversed(range(4,14)):
        phase=_compose(HIGH,[aa(i),bb(i),aa(i-2),aa(i-3),aa(i-1),(0,1<<12)],13)
        _erase(builder,u[i],list(v)+[u[i-1]],phase)
    for i in reversed(range(4)):
        item=LOCAL['low_cleanup'][i]
        env={f'v{j}':v[j]for j in range(i+1)}
        env.update(p12=P[12],p13=P[13],p14=P[14])
        env.update({f'u{j}':u[j]for j in range(i)})
        _erase(builder,u[i],[env[name]for name in item['inputs']],plan_from_json(item['plan']))
    return P


def _frame(builder,sign,target):
    for q in target:builder.x(q);builder.cx(sign,q)


def _leading_offset(builder,target,inverse=False):
    if inverse:
        builder.x(target[-2]);builder.cx(target[-2],target[-1])
    else:
        builder.cx(target[-2],target[-1]);builder.x(target[-2])


def _feed_variables(v,low,cur,sign):
    return ([v[0],low,sign],FEED3)if cur is None else([v[0],low,cur,sign],FEED4)


def _feed_carry(builder,v,low,cur,sign):
    variables,plan=_feed_variables(v,low,cur,sign)
    carry=builder.alloc_qubits(1)[0];cb.emit_xor(builder,variables,carry,plan)
    return carry


def _feed_erase(builder,carry,v,low,cur,sign):
    variables,plan=_feed_variables(v,low,cur,sign)
    _erase(builder,carry,variables,plan)


@dataclass
class DividerToken:
    v:list
    P:list
    flags:list
    u:list
    initial_u:tuple
    history:dict=field(default_factory=dict)
    rows:list=field(default_factory=list)
    consumed:bool=False


def _dirty(token):
    forbidden=set(token.v+token.u)
    wires=token.flags+[q for q in token.P if q is not None]+list(token.history.values())
    return list(dict.fromkeys(q for q in wires if q not in forbidden))


def compute_divider(builder,v12,P15,flags4):
    """Compute the m37 balanced endpoint, preserving every quotient owner."""
    v=list(v12);P=list(P15);flags=list(flags4)
    assert len(v)==12 and len(P)==15 and len(flags)==4
    assert len(set(v+P+flags))==31
    assert builder.num_allocated_qubits==31,'Unpriced retained owner before divider'
    u=list(builder.alloc_qubits(14));initial_u=tuple(u)
    P=initialize_u12(builder,v,P,u)
    token=DividerToken(v,P,flags,u,initial_u)
    assert builder.num_allocated_qubits==43
    for j in range(12,36):
        u=token.u
        if j<=24:
            prev=token.P[24-j];cur=token.P[23-j]if j<24 else None
            assert prev is not None
            sign=u[-1];target=u[:-1]
            carry=_feed_carry(builder,v,prev,cur,sign)
            _frame(builder,sign,target)
            debt=forward_add(builder,v[1:],target,carry_in=carry)
            _leading_offset(builder,target);_frame(builder,sign,target)
            # The former previous-input owner becomes the next low remainder.
            builder.cx(v[0],prev);builder.cx(sign,prev)
            if cur is not None:builder.cx(cur,prev)
            _feed_erase(builder,carry,v,prev,cur,sign)
            token.u=[prev]+target;token.history[j]=sign;token.P[24-j]=None
            k=0
        else:
            k=j-26 if j>=28 else 0
            u=[u[-1]]+u[:-1];sign=u[0];target=u[k+1:]
            _frame(builder,sign,target)
            debt=forward_add(builder,v[k+1:],target,carry_in=v[k])
            _leading_offset(builder,target);_frame(builder,sign,target)
            builder.cx(v[0],u[0]);token.u=u
        token.rows.append((j,k,debt))
        assert builder.num_allocated_qubits==43,(j,builder.num_allocated_qubits)
    assert sorted(token.history)==list(range(12,25)) and all(q is None for q in token.P)
    return token


def cleanup_divider(builder,token):
    """Reverse all rows, pay every CarryDebt, then clear direct u12."""
    assert not token.consumed;token.consumed=True
    v=token.v
    for j,k,debt in reversed(token.rows):
        u=token.u
        if j<=24:
            low=u[0];target=u[1:];sign=token.history[j]
            cur=token.P[23-j]if j<24 else None
            if j<24:assert cur is not None
            carry=_feed_carry(builder,v,low,cur,sign)
            _frame(builder,sign,target);_leading_offset(builder,target,inverse=True)
            inverse_add(builder,v[1:],target,debt,carry_in=carry,dirty_wires=_dirty(token))
            _frame(builder,sign,target)
            _feed_erase(builder,carry,v,low,cur,sign)
            if cur is not None:builder.cx(cur,low)
            builder.cx(sign,low);builder.cx(v[0],low)
            token.P[24-j]=low;token.u=target+[sign];del token.history[j]
        else:
            builder.cx(v[0],u[0]);sign=u[0];target=u[k+1:]
            _frame(builder,sign,target);_leading_offset(builder,target,inverse=True)
            inverse_add(builder,v[k+1:],target,debt,carry_in=v[k],dirty_wires=_dirty(token))
            _frame(builder,sign,target);token.u=u[1:]+u[:1]
        assert debt.consumed and not debt.measurements
        assert builder.num_allocated_qubits==43
    assert tuple(token.u)==token.initial_u and not token.history
    token.P=cleanup_u12(builder,v,token.P,token.u)
    assert builder.num_allocated_qubits==31 and all(q is not None for q in token.P)
    return list(token.P)


CENTRES=(0,-2,-6,0,-1)
ACTIVE=(30,6,27,3,17,9,18,10,23,15,20)
CONTROLS=((2,4,8),(0,4,16),(0,2,4,16),(0,1,4,8),(0,1))
THRESHOLDS={1:(1,2,4,8,16,3,5,9,17),2:(2,4,8,16),3:(4,8,3,17),
    4:(4,8),5:(8,16,32,5,17),6:(8,16,32),7:(8,17),8:(8,),9:(9,10),10:(32,)}


@contextmanager
def _affine_control(builder,variables,terms):
    linear=[t.bit_length()-1 for t in terms if t]
    assert linear and all(t==0 or t.bit_count()==1 for t in terms)
    pivot=variables[linear[0]]
    for i in linear[1:]:builder.cx(variables[i],pivot)
    if 0 in terms:builder.x(pivot)
    try:yield pivot
    finally:
        if 0 in terms:builder.x(pivot)
        for i in reversed(linear[1:]):builder.cx(variables[i],pivot)


@contextmanager
def _threshold(builder,variables,t):
    terms=THRESHOLDS[t]
    if max(x.bit_count()for x in terms)<=1:
        with _affine_control(builder,variables,terms)as q:yield q
    else:
        q=builder.alloc_qubits(1)[0];xor_polynomial(builder,variables,q,terms)
        try:yield q
        finally:_erase_polynomial(builder,q,variables,terms)


def _route(builder,word,variables,inverse=False):
    stages=list(range(5))
    if inverse:stages.reverse()
    for stage in stages:
        with _affine_control(builder,variables,CONTROLS[stage])as q:
            for i in range(27):
                k=(CENTRES[stage]-i)%27
                if i<k:builder.cswap(q,word[i],word[k])


def _slots():
    word=list(range(27))
    for stage,centre in enumerate(CENTRES):
        if ACTIVE[0]>>stage&1:word=[word[(centre-i)%27]for i in range(27)]
    inverse={v:i for i,v in enumerate(word)}
    return [inverse[i]for i in range(27)]


def _feature(builder,control,data,turns):
    turns=Fraction(turns)%1
    if turns==Fraction(1,2):builder.cz(control,data)
    elif turns in (Fraction(1,4),Fraction(3,4)):
        sign=1 if turns==Fraction(1,4)else-1
        builder.z_pow(control,Fraction(sign,4));builder.z_pow(data,Fraction(sign,4))
        builder.cx(control,data);builder.z_pow(data,Fraction(-sign,4));builder.cx(control,data)
    else:
        q=builder.alloc_qubits(1)[0]
        builder.ccx(control,data,q);builder.z_pow(q,2*turns)
        builder.del_and(control,data,q);builder.free(q)


def _sigma25_frame(builder,v,u,inverse=False):
    # Involutory, but source-affine masks must be applied after/before this
    # frame in the forward/inverse endpoint chart respectively.
    for q in (v[10],v[0],v[1]):builder.cx(q,u[10])
    builder.cx(u[8],u[9]);builder.cx(v[1],v[0])
    builder.ccx(u[9],v[0],u[10])
    builder.cx(v[1],v[0]);builder.cx(u[8],u[9])


def phase_endpoint(builder,token):
    """146 CCX-equivalents +4 T +34 arbitrary rotations, N27 cyclic model."""
    v,u,flags=token.v,token.u,token.flags
    assert builder.num_allocated_qubits==43
    _sigma25_frame(builder,v,u)
    for q in u[:9]:builder.cx(v[0],q)
    builder.cx(v[1],u[9])
    signs={**token.history,25:u[10],26:u[9],36:u[13]}
    signs.update({j:u[35-j]for j in range(27,36)})
    for q in signs.values():builder.x(q)
    ones=list(builder.alloc_qubits(2));builder.x(array(ones))
    word=[ones[0]]+[signs[37-i]for i in range(1,26)]+[ones[1]]
    assert len(set(word))==27
    p,c=list(builder.alloc_qubits(2))
    xor_polynomial(builder,flags,p,(6,10));xor_polynomial(builder,flags,c,(10,))
    variables=flags+[p,c]
    _route(builder,word,variables)
    slots=[word[i]for i in _slots()]
    factor=1<<27
    for i,q in enumerate(slots):
        units=(1<<i)+(factor if i==0 else 0)
        builder.z_pow(q,Fraction(2*units,1<<37))
    for j in range(10):
        angle=Fraction(factor*(1<<j),1<<37)
        if j==0:
            with _threshold(builder,variables,1)as q:
                builder.x(q);builder.z_pow(q,-2*angle);builder.x(q)
        elif j==9:builder.z_pow(c,2*angle)
        else:
            with _threshold(builder,variables,j+1)as q:_feature(builder,q,slots[j],angle)
    _route(builder,word,variables,inverse=True)
    _erase_polynomial(builder,c,flags,(10,));_erase_polynomial(builder,p,flags,(6,10))
    builder.x(array(ones));builder.free(array(ones))
    for q in signs.values():builder.x(q)
    builder.cx(v[1],u[9])
    for q in u[:9]:builder.cx(v[0],q)
    _sigma25_frame(builder,v,u,inverse=True)
    assert builder.num_allocated_qubits==43


def compute_phase_cleanup(builder,v12,P15,flags4):
    token=compute_divider(builder,v12,P15,flags4)
    phase_endpoint(builder,token)
    return cleanup_divider(builder,token)
