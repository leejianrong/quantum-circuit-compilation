# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""The supplied 27-T inverse phase, with its last leaf AND made a CCZ.

The fifth GF16 leaf AND appears in exactly one output phase (B[1]).
Replacing its allocation/phase/HMR by a direct CCZ preserves the map and
T count, while reducing the peak from thirteen to twelve clean helpers.
No supplied source is modified. The mask is classical and preserved.
"""
import c27_paths  # noqa: F401
import inverse_phase27 as Base
from field_tensor import invert_binary_columns, accumulate_product
from quantum_reciprocal import xor_linear
from tower_inverse import (apply_inplace_linear, rows_from_columns,
                           phase_product, phase_linear)


def record_uniform_hmr_event(name, conditional_t, mask_bits):
    """Optional construction-time exact-expectation hook; emits no gates."""
    return None


def _leaf_phase12(builder, C, B):
    apply_inplace_linear(builder, B, Base.GRAM_ROWS)
    signals, records = list(C), []
    for left, right in Base.LEAF_GATES[:-1]:
        view, undo = Base._view_pair(builder, signals, left, right)
        target = builder.alloc_qubits(1)
        builder.init_and(view[0], view[1], target[0])
        apply_inplace_linear(builder, view, undo)
        records.append((tuple(signals), left, right, target))
        signals.append(target[0])
    last_index = len(signals)
    users = [bit for bit, form in enumerate(Base.LEAF_OUTPUTS)
             if form >> last_index & 1]
    assert users == [1] and last_index == 8
    for bit, form in enumerate(Base.LEAF_OUTPUTS):
        for j, signal in enumerate(signals):
            if form >> j & 1:
                builder.cz(B[bit], signal)
    left, right = Base.LEAF_GATES[-1]
    view, undo = Base._view_pair(builder, signals, left, right)
    builder.ccz(B[1], view[0], view[1])
    apply_inplace_linear(builder, view, undo)
    for parents, left, right, target in reversed(records):
        view, undo = Base._view_pair(builder, parents, left, right)
        builder.del_and(view[0], view[1], target[0])
        builder.free(target)
        apply_inplace_linear(builder, view, undo)
    apply_inplace_linear(builder, B,
                         invert_binary_columns(rows_from_columns(Base.GRAM_ROWS)))


def fixed_inverse_trace12(builder, source):
    """Apply Tr(inv0(source)); source is restored, 27 T, 12 helpers."""
    assert len(source) == 12
    info = Base.cubic_basis()
    apply_inplace_linear(builder, source, info['to_cubic'])
    a, b, c, bc = source[:4], source[4:8], source[8:], source[4:]
    B, C = builder.alloc_qubits(4), builder.alloc_qubits(4)
    Base._joint_init(builder, bc, B, C)
    squares = tuple(Base.SMALL.mul(1 << j, 1 << j) for j in range(4))
    for word in (a, b, c):
        xor_linear(builder, word, B, squares)
    accumulate_product(builder, a, B, C, Base.gf16_kernel())
    _leaf_phase12(builder, C, B)
    measured = builder.alloc_bits(4)
    builder.hmr(C, measured)
    phase_product(builder, a, B, measured, Base.gf16_kernel())
    Base._joint_phase(builder, bc, measured, 4)
    builder.free(measured)
    builder.free(C)
    measured = builder.alloc_bits(4)
    builder.hmr(B, measured)
    for word in (a, b, c):
        phase_linear(builder, word, measured, squares)
    Base._joint_phase(builder, bc, measured, 0)
    builder.free(measured)
    builder.free(B)
    apply_inplace_linear(builder, source, info['from_cubic'])


def phase_inverse_twelve_polynomial(builder, source, mask):
    """Apply dot(mask,inv0(source)), with standard-basis classical mask.

    Static count27; for a fresh uniform12-bit mask the exact expectation
    is27*(4095/4096). At most12 quantum helpers are live.
    """
    assert len(source) == len(mask) == 12
    alpha = Base._classical_word(builder)
    xor_linear(builder, mask, alpha, Base.trace_dual_columns())
    reciprocal, owned = Base._classical_inverse(builder, alpha)
    active = Base._classical_word(builder, 1)
    builder.bit_store(active[0], True, control=alpha)
    builder.push_condition(active[0])
    Base._classical_scale(builder, source, reciprocal, alpha)
    fixed_inverse_trace12(builder, source)
    Base._classical_scale(builder, source, alpha, reciprocal)
    builder.pop_condition()
    for word in owned:
        builder.free(word)
    builder.free(active)
    builder.free(alpha)
    record_uniform_hmr_event('inverse_phase27_12_helpers', 27, 12)
