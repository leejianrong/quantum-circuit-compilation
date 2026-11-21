# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Q48 lifecycle with framed input retirement and owned carry disposal.

All unchanged arithmetic comes from the hash-pinned candidate01 module.
This module owns only its isolated emit_body and product inverse. It never
modifies a previous source or the previous lifecycle module's functions.
"""
from pathlib import Path
import hashlib,importlib.util,sys

HERE=Path(__file__).resolve().parent;NARROW=HERE.parents[1]
BASE=HERE.parent/'candidate01'
BASE_SHA='47b73f1f24ea027eedcbd1950cde7fc2535b32afeeb2e366ebdc4b6f1eb3c068'
COMMON_SHA='9872e64213a4219522a87efc49d1aa549a04e43ae3fb51c9d5b762b1ea6535ab'
assert hashlib.sha256((BASE/'lifecycle.py').read_bytes()).hexdigest()==BASE_SHA
assert hashlib.sha256((BASE/'common.py').read_bytes()).hexdigest()==COMMON_SHA
sys.path.insert(0,str(BASE))
import common

ACCEPTED=common.checked_json(NARROW/'PAPER_GATE_RECEIPT_018_VARIANT.json',
    '99ef9a891d4e99b262b1a452ea48b18c536e91e7017f018b77bc37f1793ccffd')
assert ACCEPTED['native_build_authorized'] and ACCEPTED['Q']==48
PAPER=common.checked_json(NARROW/ACCEPTED['paper_gate_path'],ACCEPTED['paper_gate_sha256'])
assert PAPER['full_lifecycle_E']==563 and PAPER['expected_Toffolis']==1591

_name='candidate06_pinned_candidate01_lifecycle'
if _name not in sys.modules:
    _spec=importlib.util.spec_from_file_location(_name,BASE/'lifecycle.py')
    _module=importlib.util.module_from_spec(_spec);sys.modules[_name]=_module
    _spec.loader.exec_module(_module)
baseline=sys.modules[_name]
km=common.km
CUT_HOOK=None


def _mark(builder,trace,label,expected,owners=None):
    live=builder.num_allocated_qubits
    assert live==expected,(label,live,expected)
    assert live<=48,(label,live)
    if trace is not None:trace.append(dict(label=label,live_owners=live))
    if CUT_HOOK is not None:
        CUT_HOOK(label,builder,{} if owners is None else {key:list(value) for key,value in owners.items()})


def product_inverse(builder,D,word,token,dirty):
    """Pay all ten paired debts; dispose only the eight owned input carries."""
    assert builder.max_qubits==48 and builder.num_allocated_qubits==44
    assert len(D)==13 and len(word)==16 and len(token.rows)==10
    assert all(not debt.consumed for debt in token.rows)
    word=list(word);C=[False]+list(D);builder.x(word[15])
    for i in reversed(range(10)):
        q=word[6+i];target=word[:6+i];source=C[9-i:] if i<9 else C
        # The target frame must precede the last row's control/carry alias.
        for t in target:builder.cx(q,t)
        carry=baseline._product_carry(builder,C,q,i)
        if i<8:
            assert isinstance(carry,km.q) and carry!=q
            lifecycle=(
                lambda value: baseline._clear_product_carry(builder,C,q,i,value),
                lambda: baseline._product_carry(builder,C,q,i))
        else:
            if i==8:assert carry is False
            else:assert carry==q
            lifecycle=None
        # Segment and borrow kernels restore C8 and every dirty q before
        # invoking either callback. Regeneration remains conditionally priced.
        released_input=baseline.product_ar.inverse_add(builder,source,target,token.rows[i],
            carry_in=carry,dirty_wires=dirty+word[6:],carry_lifecycle=lifecycle)
        if i<8:assert released_input,'The pinned Q48 owned-carry partition must release its input.'
        else:assert not released_input,'False/aliased product carries cannot be disposed.'
        if not released_input:
            baseline._clear_product_carry(builder,C,q,i,carry)
        for t in target:builder.cx(q,t)
        assert token.rows[i].consumed and not token.rows[i].measurements
        assert builder.num_allocated_qubits==44
    builder.x(word[15])
    assert all(debt.consumed and not debt.measurements for debt in token.rows)
    return word[:6],word[6:]


def emit_body(builder,v12,h10,flags4,table_module,divider_module,decode_root_callback,*,trace=None):
    """Compute phase and restore current(v12,h10), with no stale root handles.

    table_module.load_joint16 retains its old call shape. Its second variant
    expects the R frame already active and consumes address slots0/1/2/4.
    decode_root_callback accepts None for their already-owned table signs;
    the later raw-a6 HMR is the only separate direct root phase correction.
    """
    assert builder.max_qubits==48
    v=list(v12);h=list(h10);flags=list(flags4)
    assert (len(v),len(h),len(flags))==(12,10,4)
    assert len(set(v+h+flags))==26
    _mark(builder,trace,'body_entry',26,dict(v=v,h=h,flags=flags))
    table_debts=table_module.TableDebts();truths=table_module.model_truths()

    D,Hlow=table_module.load_joint16(builder,v[5:],variant='first',debts=table_debts)
    D=list(D);H=list(Hlow)
    _mark(builder,trace,'first_table',42,dict(v=v,h=h,flags=flags,D=D,H=H))
    H.append(baseline.prepare_H3_initial(builder,v,D,H));baseline.root_R_frame(builder,v)
    H.append(baseline.prepare_H4(builder,D,H[3]))
    first=baseline.coefficient_forward(builder,v,D,H)
    _mark(builder,trace,'first_coefficient',45,dict(v=v,h=h,flags=flags,D=D,H=H,snapshot=[first.saved_bit]))
    Hlow=baseline.erase_high_H(builder,v,D,H)
    for i,q in enumerate(Hlow):table_debts.erase(builder,q,truths['H'][i],free=True)
    first_snapshot=baseline.ar.release_saved_bit(builder,first.saved_bit);first.saved_bit=None
    baseline.root_R_frame(builder,v,inverse=True)
    _mark(builder,trace,'first_metadata_retired',39)

    seed,seed_token=baseline.seed_forward(builder,v,D)
    _mark(builder,trace,'seed_ready',45,dict(v=v,h=h,flags=flags,D=D,seed=seed))
    word,product_token=baseline.product_forward(builder,D,seed,h)
    builder.x(word[15]);builder.cx(word[14],word[15]);builder.free(word[15]);P=word[:15]
    _mark(builder,trace,'signed_product15',44,dict(v=v,P=P,flags=flags,D=D))
    first_D=[]
    for q in D:
        m=builder.alloc_bits(1)[0];builder.hmr(q,m);builder.free(q);first_D.append(m)
    _mark(builder,trace,'coefficient_retired_for_divider',31,dict(v=v,P=P,flags=flags))
    P=list(divider_module.compute_phase_cleanup(builder,v,P,flags))
    assert len(P)==15 and len(set(v+P+flags))==31
    _mark(builder,trace,'divider_return',31,dict(v=v,P=P,flags=flags))

    # This is the already-priced second R frame, moved before the loader.
    # Fixed controls are R,a5,a6; existing raw0/1/2/4 enter its mutable pool.
    baseline.root_R_frame(builder,v)
    D,Hlow=table_module.load_joint16(builder,v[5:],variant='second',debts=table_debts)
    D=list(D);H=list(Hlow)
    retired={a:None for a in (0,1,2,4)}
    for a in retired:v[5+a]=None
    assert all(v[5+a] is None for a in (0,1,2,4))
    assert v[8] is not None and v[10] is not None and v[11] is not None
    _mark(builder,trace,'second_table',43,dict(v=v,P=P,flags=flags,D=D,H=H))
    baseline.ar.repay_saved_bit(builder,D[6],first_snapshot)

    # Initial H3 needs raw a6. It must be prepared before the sole direct
    # root HMR. The four earlier mixed signs belong only to TableDebts.
    H.append(baseline.prepare_H3_initial(builder,v,D,H))
    _mark(builder,trace,'second_H3_ready',44,dict(v=v,P=P,flags=flags,D=D,H=H))
    q=v[11];m=builder.alloc_bits(1)[0];builder.hmr(q,m);builder.free(q)
    v[11]=None;retired[6]=m
    assert set(retired)=={0,1,2,4,6} and all(retired[a] is None for a in (0,1,2,4))
    _mark(builder,trace,'second_a6_retired',43,dict(v=v,P=P,flags=flags,D=D,H=H))
    H.append(baseline.prepare_H4(builder,D,H[3]))
    second=baseline.coefficient_forward(builder,v,D,H)
    _mark(builder,trace,'second_coefficient',45,dict(v=v,P=P,flags=flags,D=D,H=H,snapshot=[second.saved_bit]))
    for q,m in zip(D,first_D):
        builder.push_condition(m);builder.z(q);builder.pop_condition();builder.free(m)
    baseline.merge_coefficient_transcripts(builder,first,second)
    Hlow=baseline.erase_high_H(builder,v,D,H)
    _mark(builder,trace,'second_metadata_retired',43)

    high=builder.alloc_qubits(1)[0];builder.cx(P[14],high);builder.x(high);word=P+[high]
    _mark(builder,trace,'inverse_product_data',44,dict(v=v,word=word,flags=flags,D=D,H=Hlow,snapshot=[second.saved_bit]))
    dirty=[q for q in v if q is not None]+flags+Hlow+[second.saved_bit]
    seed,h=product_inverse(builder,D,word,product_token,dirty)
    baseline.seed_cleanup(builder,v,D,seed,seed_token)
    _mark(builder,trace,'seed_cleared',38,dict(v=v,h=h,flags=flags,D=D,H=Hlow,snapshot=[second.saved_bit]))
    H=list(Hlow);H.append(baseline.prepare_H3_current(builder,v,D,H))
    H.append(baseline.prepare_H4(builder,D,H[3]))
    _mark(builder,trace,'coefficient_sources_restored',40)
    # Neutral coefficient callbacks are deliberately not introduced.
    baseline.coefficient_inverse(builder,v,D,H,second,[q for q in v if q is not None]+flags+h)
    _mark(builder,trace,'A_restored',39,dict(v=v,h=h,flags=flags,A=D,H=H))
    v=list(decode_root_callback(builder,v,D,H,retired))
    assert all(q is not None for q in v) and len(set(v+h+flags))==26
    baseline.root_R_frame(builder,v,inverse=True)
    _mark(builder,trace,'raw_root_restored',44,dict(v=v,h=h,flags=flags,A=D,H=H))
    Hlow=baseline.erase_high_H(builder,v,D,H,initial=True)
    table_module.cleanup_joint16(builder,v[5:],D,Hlow,table_debts)

    assert not table_debts.pending
    assert first.saved_bit is None and second.saved_bit is None
    for token in (first,second):
        assert all(debt.consumed and not debt.measurements for debt in token.row_debts)
        assert token.overflow_debt.consumed and not token.overflow_debt.measurements
    assert all(debt.consumed and not debt.measurements for debt in product_token.rows)
    _mark(builder,trace,'body_return',26,dict(v=v,h=h,flags=flags))
    return v,h


COMPONENT_CONTRACT=dict(Q=48,lifecycle_E=563,product_forward_E=103,product_inverse_E=137.5,
    product_conditional_regeneration_E=4,coefficient_E=123,seed_E=17.5,metadata_E=7,
    root_frames_E=4,root_decoder_E=21,table_loaders_E=141,table_cleanup_E=9,
    retired_to_table_only=(0,1,2,4),retired_direct_Z=(6,),final_live_owners=26)
assert sum(COMPONENT_CONTRACT[k] for k in ('product_forward_E','product_inverse_E','coefficient_E',
    'seed_E','metadata_E','root_frames_E','root_decoder_E','table_loaders_E','table_cleanup_E'))==563
