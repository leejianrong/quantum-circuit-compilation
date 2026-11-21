# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Native narrow coefficient/seed/consuming-product lifecycle.

All physical arrays returned from measured/recreated registers are current.
No supplied source is modified. Every measurement bit has one explicit owner.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
import importlib.util
import sys
import hashlib
from common import km,cb,NARROW,ENGINE,MODEL,checked_json,plan_from_json,array
import paired_arithmetic as ar

AR_SHA='a10b28423640a50a45a6ab23d3604dd869c26943b0ed12021526e87d1fbf8ccc'
assert hashlib.sha256((ENGINE/'paired_arithmetic.py').read_bytes()).hexdigest()==AR_SHA
SEED=checked_json(NARROW/'research/lifecycle_schedule/seed_phase_cleanup_conditional.json',
    '71f0fcb5645fd32cf128c310c5e5cba406d1ad33c02b4f37e51869ee845ed466')['certificate']
METADATA=checked_json(NARROW/'research/lifecycle_schedule/slope_h3_h4_retirement_v3.json',
    '1e5afe12bc0a9005bb3705afdc564f30c0861d99970d31f71d9b7c2556e17721')['certificate']
H3_INITIAL=plan_from_json(METADATA['H3_initial']['plan'])
H3_CURRENT=plan_from_json(METADATA['H3_current']['plan'])
H4_PLAN=plan_from_json(METADATA['H4']['plan'])
CUT_HOOK=None  # Optional diagnostic callback(label,builder,current owner dict).


def _literal_inputs(source,target,carry_in,signed_source):
    source,target=list(source),list(target);width=len(target);source=source[:width]
    if any(q is not False and not isinstance(q,km.q)for q in source):raise ValueError('Product source contains a nonwire/nonzero constant.')
    real=[q for q in source if isinstance(q,km.q)]
    if len(set(real+target))!=len(real)+len(target):raise ValueError('Product data wires alias.')
    if isinstance(carry_in,km.q)and carry_in in real+target:raise ValueError('Product carry aliases data.')
    if carry_in is not False and not isinstance(carry_in,km.q):raise ValueError('Invalid product carry.')
    preserve=real[-1]if signed_source and real else None
    source+=[preserve if preserve is not None else False]*(width-len(source))
    return source,target,preserve


# Isolated validator extension; baseline ar and every other component stay
# unchanged. The arithmetic kernels already implement literal-zero operands.
_spec=importlib.util.spec_from_file_location('_candidate01_product_paired',ENGINE/'paired_arithmetic.py')
product_ar=importlib.util.module_from_spec(_spec);sys.modules[_spec.name]=product_ar;_spec.loader.exec_module(product_ar)
product_ar._inputs=_literal_inputs


def _mark(builder,trace,label,expected=None,owners=None):
    live=builder.num_allocated_qubits
    if expected is not None:assert live==expected,(label,live,expected)
    if trace is not None:trace.append(dict(label=label,live_owners=live))
    if CUT_HOOK is not None:CUT_HOOK(label,builder,{}if owners is None else{key:list(value)for key,value in owners.items()})


def _erase(builder,target,variables,plan):
    outcome=builder.alloc_bits(1)[0];builder.hmr(target,outcome)
    cb.emit_phase(builder,list(variables),outcome,plan)
    builder.free(outcome);builder.free(target)


def root_R_frame(builder,v,*,inverse=False):
    operations=[('cx',v[7],v[8]),('cx',v[7],v[10]),('ccx',v[6],v[10],v[8]),('cx',v[7],v[10])]
    if inverse:operations.reverse()
    for name,*wires in operations:getattr(builder,name)(*wires)


def seed_root_frame(builder,v,*,inverse=False):
    operations=[('cx',v[2],v[0]),('cx',v[2],v[1]),('cx',v[2],v[3]),('ccx',v[0],v[1],v[3]),('cx',v[1],v[0])]
    if inverse:operations.reverse()
    for name,*wires in operations:getattr(builder,name)(*wires)


def prepare_H3_initial(builder,v,A,Hlow):
    q=builder.alloc_qubits(1)[0]
    cb.emit_xor(builder,[A[i]for i in(10,11,12)]+[Hlow[2],v[10],v[11]],q,H3_INITIAL)
    return q


def prepare_H3_current(builder,v,D,Hlow):
    q=builder.alloc_qubits(1)[0]
    cb.emit_xor(builder,[D[i]for i in(9,10,11,12)]+[Hlow[2],v[10]],q,H3_CURRENT)
    return q


def prepare_H4(builder,D,H3):
    q=builder.alloc_qubits(1)[0];cb.emit_xor(builder,[D[11],D[12],H3],q,H4_PLAN);return q


def erase_high_H(builder,v,D,H,*,initial=False):
    """Erase H4 first, retaining H3 until its dependent phase is paid."""
    _erase(builder,H[4],[D[11],D[12],H[3]],H4_PLAN)
    variables=([D[i]for i in(10,11,12)]+[H[2],v[10],v[11]])if initial else([D[i]for i in(9,10,11,12)]+[H[2],v[10]])
    _erase(builder,H[3],variables,H3_INITIAL if initial else H3_CURRENT)
    return list(H[:3])


def _coefficient_carry(builder,S,sign,k):
    q=builder.alloc_qubits(1)[0]
    if k:
        builder.cx(S[k],S[k-1]);builder.ccx(sign,S[k-1],q);builder.cx(S[k],S[k-1]);builder.cx(S[k],q)
    else:
        builder.x(sign);builder.ccx(sign,S[0],q);builder.x(sign)
    return q


def _clear_coefficient_carry(builder,S,sign,k,q):
    if k:
        builder.cx(S[k],q);builder.cx(S[k],S[k-1]);builder.del_and(sign,S[k-1],q);builder.cx(S[k],S[k-1])
    else:
        builder.x(sign);builder.del_and(sign,S[0],q);builder.x(sign)
    builder.free(q)


def coefficient_forward(builder,v,D,H):
    S=[v[8]]+list(H);snapshot=builder.alloc_qubits(1)[0];builder.cx(D[6],snapshot)
    token=ar.DeferredBoundedToken(SimpleNamespace(last=5,signed_source=False),snapshot,7,[])
    for i in range(5):
        k=4-i;carry=_coefficient_carry(builder,S,v[i],k)
        for q in D[:7]:builder.cx(v[i],q)
        token.row_debts.append(ar.forward_add(builder,S[k+1:],D[:7],carry_in=carry))
        for q in D[:7]:builder.cx(v[i],q)
        _clear_coefficient_carry(builder,S,v[i],k,carry)
    ar._deferred_overflow(builder,v[:5],S,D,token,inverse=False)
    return token


def _merge_debts(builder,first,second):
    assert not first.consumed and not second.consumed and first.width==second.width
    for position,outcome in list(first.measurements.items()):
        other=second.measurements.get(position)
        if other is None:second.measurements[position]=outcome
        else:builder.cx(outcome,other);builder.free(outcome)
    first.measurements.clear();first.consumed=True


def merge_coefficient_transcripts(builder,first,second):
    assert first.window==second.window==7 and len(first.row_debts)==len(second.row_debts)==5
    for a,b in zip(first.row_debts,second.row_debts):_merge_debts(builder,a,b)
    _merge_debts(builder,first.overflow_debt,second.overflow_debt)


def coefficient_inverse(builder,v,D,H,token,dirty):
    S=[v[8]]+list(H)
    ar._deferred_overflow(builder,v[:5],S,D,token,inverse=True)
    saved=ar.release_saved_bit(builder,token.saved_bit);token.saved_bit=None
    for i in reversed(range(5)):
        k=4-i;carry=_coefficient_carry(builder,S,v[i],k)
        for q in D[:7]:builder.cx(v[i],q)
        ar.inverse_add(builder,S[k+1:],D[:7],token.row_debts[i],carry_in=carry,dirty_wires=dirty)
        for q in D[:7]:builder.cx(v[i],q)
        _clear_coefficient_carry(builder,S,v[i],k,carry)
    ar.repay_saved_bit(builder,D[6],saved)
    assert all(d.consumed and not d.measurements for d in token.row_debts)
    assert token.overflow_debt.consumed and not token.overflow_debt.measurements


@dataclass
class SeedToken:
    rows:list


def seed_forward(builder,v,D):
    seed_root_frame(builder,v);seed=list(builder.alloc_qubits(3));builder.x(array(seed));rows=[]
    for i,control in enumerate((v[0],v[1],v[3])):
        builder.x(control)
        rows.append(ar.forward_signed_row(builder,D,seed,shift=-(11-i),sign=control))
        builder.x(control)
        q=builder.alloc_qubits(1)[0];builder.x(q);builder.cx(control,q);seed.append(q)
    seed_root_frame(builder,v,inverse=True)
    return seed,SeedToken(rows)


def seed_cleanup(builder,v,D,seed,token):
    seed=list(seed);seed_root_frame(builder,v);raw=list(D[8:13])+[v[0],v[1],v[3]]
    _erase(builder,seed[5],raw,plan_from_json(SEED['initial_seed5_erasure']))
    helpers=[]
    for item in SEED['persistent_helpers']:
        q=builder.alloc_qubits(1)[0];cb.emit_xor(builder,raw+helpers,q,plan_from_json(item['plan']));helpers.append(q)
    carries=[]
    for debt in token.rows:
        carries.extend(debt.measurements[position]for position in sorted(debt.measurements))
    assert len(carries)==len(SEED['carry_phase_plans'])==6
    for outcome,plan in zip(carries,SEED['carry_phase_plans']):
        cb.emit_phase(builder,raw+helpers+seed[:5],outcome,plan_from_json(plan));builder.free(outcome)
    for debt in token.rows:debt.measurements.clear();debt.consumed=True
    m=builder.alloc_bits(1)[0];builder.hmr(seed[4],m);builder.free(seed[4])
    fifth=builder.alloc_qubits(1)[0]
    builder.push_condition(m)
    cb.emit_xor(builder,raw+helpers,fifth,plan_from_json(SEED['conditional_helper']['plan']))
    builder.pop_condition()
    cb.emit_phase(builder,raw+helpers+[fifth]+seed[:4],m,plan_from_json(SEED['seed4_erasure']['plan']))
    aux=builder.alloc_bits(1)[0];builder.hmr(fifth,aux)
    builder.push_condition(m)
    cb.emit_phase(builder,raw+helpers,aux,plan_from_json(SEED['conditional_helper']['plan']))
    builder.pop_condition();builder.free(aux);builder.free(fifth);builder.free(m)
    for item in SEED['remaining_seed_erasures']:
        i=item['bit'];variables=raw+helpers+[seed[j]for j in item['remaining_seed_bits']]
        _erase(builder,seed[i],variables,plan_from_json(item['plan']))
    for i in reversed(range(4)):
        _erase(builder,helpers[i],raw+helpers[:i],plan_from_json(SEED['persistent_helpers'][i]['plan']))
    seed_root_frame(builder,v,inverse=True)


def _product_carry(builder,C,q,i):
    """Return an owned rounding carry, False, or the final aliased q owner."""
    shift=8-i;parity=C[8]
    if shift<0:
        builder.cx(parity,q);builder.x(q);return q
    if shift==0:
        assert C[0]is False;return False
    carry=builder.alloc_qubits(1)[0];upper=C[shift];lower=C[shift-1]
    if lower is False:
        builder.cx(parity,q);builder.ccx(upper,q,carry);builder.cx(parity,q)
    else:
        builder.cx(upper,lower);builder.cx(parity,q);builder.x(q)
        builder.ccx(lower,q,carry)
        builder.x(q);builder.cx(parity,q);builder.cx(upper,lower);builder.cx(upper,carry)
    return carry


def _clear_product_carry(builder,C,q,i,carry):
    shift=8-i;parity=C[8]
    if shift<0:builder.x(q);builder.cx(parity,q);return
    if shift==0:assert carry is False;return
    upper=C[shift];lower=C[shift-1]
    if lower is False:
        builder.cx(parity,q);builder.del_and(upper,q,carry);builder.cx(parity,q)
    else:
        builder.cx(upper,carry);builder.cx(upper,lower);builder.cx(parity,q);builder.x(q)
        builder.del_and(lower,q,carry)
        builder.x(q);builder.cx(parity,q);builder.cx(upper,lower)
    builder.free(carry)


@dataclass
class ProductToken:
    rows:list


def product_forward(builder,D,seed,h):
    word=list(seed)+list(h);C=[False]+list(D);rows=[];builder.x(word[15])
    for i in range(10):
        q=word[6+i];target=word[:6+i];source=C[9-i:]if i<9 else C
        # The target frame MUST precede the last control/carry alias.
        for t in target:builder.cx(q,t)
        carry=_product_carry(builder,C,q,i)
        rows.append(product_ar.forward_add(builder,source,target,carry_in=carry))
        _clear_product_carry(builder,C,q,i,carry)
        for t in target:builder.cx(q,t)
    builder.x(word[15]);return word,ProductToken(rows)


def product_inverse(builder,D,word,token,dirty):
    word=list(word);C=[False]+list(D);builder.x(word[15])
    for i in reversed(range(10)):
        q=word[6+i];target=word[:6+i];source=C[9-i:]if i<9 else C
        for t in target:builder.cx(q,t)
        carry=_product_carry(builder,C,q,i)
        product_ar.inverse_add(builder,source,target,token.rows[i],carry_in=carry,dirty_wires=dirty+word[6:])
        _clear_product_carry(builder,C,q,i,carry)
        for t in target:builder.cx(q,t)
    builder.x(word[15])
    assert all(d.consumed and not d.measurements for d in token.rows)
    return word[:6],word[6:]


def emit_body(builder,v12,h10,flags4,table_module,divider_module,decode_root_callback,*,trace=None):
    """Compute/phase/uncompute and return current(v12,h10) physical owners."""
    v=list(v12);h=list(h10);flags=list(flags4)
    assert(len(v),len(h),len(flags))==(12,10,4)
    _mark(builder,trace,'body_entry',26,dict(v=v,h=h,flags=flags))
    table_debts=table_module.TableDebts();truths=table_module.model_truths()
    D,Hlow=table_module.load_joint16(builder,v[5:],variant='first',debts=table_debts)
    D=list(D);H=list(Hlow);_mark(builder,trace,'first_table',42,dict(v=v,h=h,flags=flags,D=D,H=H))
    H.append(prepare_H3_initial(builder,v,D,H));root_R_frame(builder,v)
    H.append(prepare_H4(builder,D,H[3]));first=coefficient_forward(builder,v,D,H)
    _mark(builder,trace,'first_coefficient',45,dict(v=v,h=h,flags=flags,D=D,H=H,snapshot=[first.saved_bit]))
    Hlow=erase_high_H(builder,v,D,H)
    for i,q in enumerate(Hlow):table_debts.erase(builder,q,truths['H'][i],free=True)
    first_snapshot=ar.release_saved_bit(builder,first.saved_bit);first.saved_bit=None
    root_R_frame(builder,v,inverse=True);_mark(builder,trace,'first_metadata_retired',39)
    seed,seed_token=seed_forward(builder,v,D);_mark(builder,trace,'seed_ready',45,dict(v=v,h=h,flags=flags,D=D,seed=seed))
    word,product_token=product_forward(builder,D,seed,h)
    builder.x(word[15]);builder.cx(word[14],word[15]);builder.free(word[15]);P=word[:15]
    _mark(builder,trace,'signed_product15',44,dict(v=v,P=P,flags=flags,D=D))
    first_D=[]
    for q in D:
        m=builder.alloc_bits(1)[0];builder.hmr(q,m);builder.free(q);first_D.append(m)
    _mark(builder,trace,'coefficient_retired_for_divider',31,dict(v=v,P=P,flags=flags))
    P=list(divider_module.compute_phase_cleanup(builder,v,P,flags))
    assert len(P)==15;_mark(builder,trace,'divider_return',31,dict(v=v,P=P,flags=flags))
    D,Hlow=table_module.load_joint16(builder,v[5:],variant='second',debts=table_debts)
    D=list(D);H=list(Hlow);_mark(builder,trace,'second_table',47,dict(v=v,P=P,flags=flags,D=D,H=H))
    ar.repay_saved_bit(builder,D[6],first_snapshot)
    H.append(prepare_H3_initial(builder,v,D,H));root_R_frame(builder,v)
    retired={}
    for a in(0,1,2,4,6):
        q=v[5+a];m=builder.alloc_bits(1)[0];builder.hmr(q,m);builder.free(q);v[5+a]=None;retired[a]=m
    H.append(prepare_H4(builder,D,H[3]));second=coefficient_forward(builder,v,D,H)
    _mark(builder,trace,'second_coefficient',45,dict(v=v,P=P,flags=flags,D=D,H=H,snapshot=[second.saved_bit]))
    for q,m in zip(D,first_D):
        builder.push_condition(m);builder.z(q);builder.pop_condition();builder.free(m)
    merge_coefficient_transcripts(builder,first,second)
    Hlow=erase_high_H(builder,v,D,H);_mark(builder,trace,'second_metadata_retired',43)
    high=builder.alloc_qubits(1)[0];builder.cx(P[14],high);builder.x(high);word=P+[high]
    _mark(builder,trace,'inverse_product_data',44,dict(v=v,word=word,flags=flags,D=D,H=Hlow,snapshot=[second.saved_bit]))
    dirty=[q for q in v if q is not None]+flags+Hlow+[second.saved_bit]
    seed,h=product_inverse(builder,D,word,product_token,dirty)
    seed_cleanup(builder,v,D,seed,seed_token);_mark(builder,trace,'seed_cleared',38,dict(v=v,h=h,flags=flags,D=D,H=Hlow,snapshot=[second.saved_bit]))
    H=list(Hlow);H.append(prepare_H3_current(builder,v,D,H));H.append(prepare_H4(builder,D,H[3]))
    _mark(builder,trace,'coefficient_sources_restored',40)
    coefficient_inverse(builder,v,D,H,second,[q for q in v if q is not None]+flags+h)
    _mark(builder,trace,'A_restored',39,dict(v=v,h=h,flags=flags,A=D,H=H))
    v=list(decode_root_callback(builder,v,D,H,retired));assert all(q is not None for q in v)
    root_R_frame(builder,v,inverse=True);_mark(builder,trace,'raw_root_restored',44,dict(v=v,h=h,flags=flags,A=D,H=H))
    Hlow=erase_high_H(builder,v,D,H,initial=True)
    table_module.cleanup_joint16(builder,v[5:],D,Hlow,table_debts)
    assert not table_debts.pending;_mark(builder,trace,'body_return',26,dict(v=v,h=h,flags=flags))
    return v,h
