# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""AR005: retire raw v3 only while the consuming product is inverted.

The immutable baseline supplies the arithmetic and seed conventions. The
caller must pass its mutable root-owner list: v[3] changes physical identity.
No phase debt escapes the adapter, and the original seed token is untouched.
"""


def restore_v3(builder, v, seed, outcome, *, omit_phase=False,
               omit_linear_c=False, trace=None):
    assert v[3] is None and len(seed) == 6
    a, b, c = v[:3]
    assert a is not None and b is not None and c is not None
    q = builder.alloc_qubits(1)[0]
    builder.x(q)
    builder.cx(seed[5], q)
    if not omit_linear_c:
        builder.cx(c, q)
    builder.cx(c, a)
    builder.cx(c, b)
    builder.ccx(a, b, q)
    builder.cx(c, b)
    builder.cx(c, a)
    builder.push_condition(outcome)
    if not omit_phase:
        builder.z(q)
    builder.pop_condition()
    builder.free(outcome)
    v[3] = q
    if trace is not None:
        trace.append(dict(stage='raw_v3_restored_and_phase_paid',
                          live=builder.num_allocated_qubits,
                          current_v3=str(q), phase_omitted=omit_phase))
    return q


def product_inverse(builder, v, D, word, token, dirty, *, baseline,
                    omit_v3_phase=False, omit_original_debt=None,
                    omit_linear_c=False, trace=None):
    """Return seed6/h10 and replace v[3] with its fresh restored owner.

Production requires all omission arguments at their defaults. They exist
solely for negative component proofs. Dirty spectators must name the actual
44-owner entry chart, including the original live v3 exactly once.
"""
    km = baseline.km
    assert isinstance(v, list) and len(v) == 12
    assert builder.max_qubits == 48 and builder.num_allocated_qubits == 44
    D, word, dirty = list(D), list(word), list(dirty)
    assert len(D) == 13 and len(word) == 16 and len(token.rows) == 10
    assert len(dirty) == 15 and len(set(D + word + dirty)) == 44
    assert all(not debt.consumed for debt in token.rows)
    old_v3 = v[3]
    assert isinstance(old_v3, km.q) and dirty.count(old_v3) == 1
    assert all(v[i] is not None for i in (0, 1, 2, 3, 4, 8, 10))
    assert all(v[i] is None for i in (5, 6, 7, 9, 11))
    m3 = builder.alloc_bits(1)[0]
    builder.hmr(old_v3, m3)
    builder.free(old_v3)
    v[3] = None
    dirty = [q for q in dirty if q != old_v3]
    assert len(dirty) == 14 and builder.num_allocated_qubits == 43
    if trace is not None:
        trace.append(dict(stage='raw_v3_retired', live=43,
                          retired_physical=str(old_v3),
                          actual_measurement=str(m3), dirty=list(map(str, dirty))))
    C = [False] + D
    builder.x(word[15])
    for i in reversed(range(10)):
        debt = token.rows[i]
        if omit_original_debt is not None and i == omit_original_debt[0]:
            position = omit_original_debt[1]
            assert position in debt.measurements
            builder.free(debt.measurements.pop(position))
        q = word[6 + i]
        target = word[:6 + i]
        source = C[9 - i:] if i < 9 else C
        for t in target:
            builder.cx(q, t)
        carry = baseline._product_carry(builder, C, q, i)
        regenerations = []

        def erase(value):
            assert i < 8 and value != q
            baseline._clear_product_carry(builder, C, q, i, value)

        def regenerate():
            assert i < 8
            value = baseline._product_carry(builder, C, q, i)
            regenerations.append(str(value))
            return value

        released = baseline.product_ar.inverse_add(
            builder, source, target, debt, carry_in=carry,
            dirty_wires=dirty + word[6:],
            carry_lifecycle=(erase, regenerate) if i < 8 else None)
        if not released:
            baseline._clear_product_carry(builder, C, q, i, carry)
        if i == 8:
            assert carry is False and not released
        if i == 9:
            assert carry == q and not released
        for t in target:
            builder.cx(q, t)
        assert debt.consumed and not debt.measurements
        assert builder.num_allocated_qubits == 43
        if trace is not None:
            trace.append(dict(stage=f'inverse_row_{i}', live=43,
                              original_debt_consumed=True,
                              owned_carry_released=bool(released),
                              conditional_regenerations=len(regenerations)))
    builder.x(word[15])
    seed, h = word[:6], word[6:]
    restore_v3(builder, v, seed, m3, omit_phase=omit_v3_phase,
               omit_linear_c=omit_linear_c, trace=trace)
    assert builder.num_allocated_qubits == 44
    assert len(set(D + word + dirty + [v[3]])) == 44
    assert all(debt.consumed and not debt.measurements for debt in token.rows)
    return seed, h


COMPONENT_CONTRACT = dict(
    Q=48, entry_data=44, inverse_data=43, return_data=44,
    forward_product_E=103, inverse_product_E=124.5,
    restored_v3_E=1, product_and_recovery_E=228.5,
    AR002_comparator_E=238, saving_E=9.5,
    mutable_v3_physical_handle=True, protected_seed_token_untouched=True,
    new_external_phase_debts=0, measured_v3_phase_paid_on_current_wire=True,
    AR002_known_zero_row_not_added=True,
    all_original_product_debts_consumed=True,
    row8_false_and_row9_alias_preserved=True)
