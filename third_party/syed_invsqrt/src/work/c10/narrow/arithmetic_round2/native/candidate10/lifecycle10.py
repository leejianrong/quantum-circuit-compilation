# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Isolated arithmetic lifecycle; unchanged protected callbacks, mutable v3 owner."""
baseline = None
product_inverse = None
CUT_HOOK = None


def _mark(builder,trace,label,expected,owners=None):
    live=builder.num_allocated_qubits
    assert live==expected,(label,live,expected)
    assert live<=48,(label,live)
    if trace is not None:trace.append(dict(label=label,live_owners=live))
    if CUT_HOOK is not None:
        CUT_HOOK(label,builder,{} if owners is None else {key:list(value) for key,value in owners.items()})


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
    seed,h=product_inverse(builder,v,D,word,product_token,dirty)
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
