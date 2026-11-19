# Copyright2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Own coefficient-top transfer; the unchanged baseline is supplied explicitly.

Only the accepted7-bit coefficient inverse is adapted. Original forward
carry records, the quantum incoming source carry and all other owners are
preserved or explicitly consumed. No phase endpoint or table code is changed.
"""


def inverse_low6(builder,source,target,debt,*,carry_in,top_outcome,ar,omit_wrap=False):
    source=list(source);b=list(target);km=ar.km
    assert len(b)==6 and 1<=len(source)<=5
    assert debt.width==7 and not debt.consumed
    assert set(debt.measurements)=={1,2,3,4,5}
    assert isinstance(carry_in,km.q) and isinstance(top_outcome,km.b)
    assert len(set(source+b+[carry_in]))==len(source)+len(b)+1
    assert builder.max_qubits-builder.num_allocated_qubits>=5
    entry=builder.num_allocated_qubits
    a=source+[False]*(6-len(source));assert a[5]is False
    debt.consumed=True;builder.x(km.array(b))
    frames=[];carry=carry_in
    for i in range(5):
        frame=ar._compute_carry(builder,a[i],b[i],carry,preserve=None)
        assert isinstance(frame.outgoing,km.q)
        outcome=debt.measurements.pop(i+1)
        builder.push_condition(outcome);builder.z(frame.outgoing);builder.pop_condition();builder.free(outcome)
        frames.append(frame);carry=frame.outgoing
    # The omitted old top changes by this exact final borrow. Its majority
    # has a literal-zero source input, so its Pauli phase is one CliffordCZ.
    if not omit_wrap:
        builder.push_condition(top_outcome)
        ar.phase_quadratic(builder,[False,b[5],carry],ar.MAJORITY_TRUTH)
        builder.pop_condition()
    builder.cx(carry,b[5])
    for frame in reversed(frames):ar._erase_carry(builder,frame,write_sum=True)
    builder.x(km.array(b))
    assert not debt.measurements and builder.num_allocated_qubits==entry


def coefficient_inverse(builder,v,D,H,token,dirty,*,baseline,omit_wrap=False,omit_saved=False):
    """Drop-in logical API with an explicit immutable baseline dependency."""
    ar=baseline.ar;km=baseline.km
    assert len(D)==13 and len(H)==5 and token.window==7
    assert len(token.row_debts)==5 and token.saved_bit is not None
    assert token.saved_bit not in list(D)+list(H)
    S=[v[8]]+list(H)
    entry=builder.num_allocated_qubits
    ar._deferred_overflow(builder,v[:5],S,D,token,inverse=True)
    assert builder.num_allocated_qubits==entry and token.overflow_debt.consumed
    # Current top is measured; originalA6 stays quantum and is transferred
    # into that reset physical top. The snapshot allocation is then zero.
    saved=token.saved_bit;top=D[6];phase=builder.alloc_bits(1)[0]
    builder.hmr(top,phase);builder.cx(saved,top);builder.cx(top,saved)
    builder.free(saved);token.saved_bit=None
    for i in reversed(range(5)):
        k=4-i;carry=baseline._coefficient_carry(builder,S,v[i],k)
        for q in D[:6]:builder.cx(v[i],q)
        inverse_low6(builder,S[k+1:],D[:6],token.row_debts[i],carry_in=carry,
                     top_outcome=phase,ar=ar,omit_wrap=omit_wrap)
        for q in D[:6]:builder.cx(v[i],q)
        baseline._clear_coefficient_carry(builder,S,v[i],k,carry)
    if omit_saved:builder.free(phase)
    else:ar.repay_saved_bit(builder,top,phase)
    assert all(d.consumed and not d.measurements for d in token.row_debts)
    assert token.overflow_debt.consumed and not token.overflow_debt.measurements
    assert builder.num_allocated_qubits==entry-1


COMPONENT_CONTRACT=dict(original_window=7,shortened_window=6,source_extents=[1,2,3,4,5],
    original_debt_positions=[1,2,3,4,5],forward_passes_E=[41,41],inverse_E=36,total_E=118,
    baseline_total_E=123,saving_E=5,production_inverse_entry=40,production_inverse_peak=45,
    production_inverse_return=39,extra_top_transfer_CX=2,new_external_phase_debts=0)
