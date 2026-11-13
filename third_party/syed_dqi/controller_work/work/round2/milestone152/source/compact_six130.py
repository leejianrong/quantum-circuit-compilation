# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""20-T clean GF64 inverse using its output and only four internal bits."""
from functools import cache
import kickmix as km
from cubic_inverse130 import (QUADRATIC_GATES, NORM_GATES, NORM_OUTPUTS,
                              ADJUGATE_OUTPUTS, cubic_data, _view_pair,
                              _xor_affine, _emit_same_source_product)
from scalar_inverse_phase import independent
from tower_inverse import apply_inplace_linear, rows_from_columns


@cache
def schedule():
    rows = [form >> 7 for form in ADJUGATE_OUTPUTS]
    assert independent(rows)
    junk = []
    for j in range(8):
        if independent(rows + [1 << j]):
            rows.append(1 << j)
            junk.append(j)
    assert len(rows) == 8 and len(junk) == 2
    parents = []
    for _, right in NORM_GATES[:2]:
        for mask in range(64):
            combined = 0
            for j, form in enumerate(ADJUGATE_OUTPUTS):
                if mask >> j & 1:
                    combined ^= form
            if (combined ^ right) < 128:
                parents.append((mask, combined ^ right))
                break
        else:
            raise AssertionError('Norm parent is not in adjugate span')
    assert NORM_GATES[0][1] ^ NORM_GATES[1][1] ^ NORM_GATES[2][1] == 58
    return tuple(rows), tuple(junk), tuple(parents)


def _phase_affine_quadratic(builder, source, mask, form):
    if form & 1:
        builder.cz(mask, True)
    for j, wire in enumerate(source):
        if form >> (j + 1) & 1:
            builder.cz(mask, wire)
    for j, (a, b) in enumerate(QUADRATIC_GATES):
        if form >> (7 + j) & 1:
            view, undo = _view_pair(builder, list(source), a, b)
            builder.ccz(mask, view[0], view[1])
            apply_inplace_linear(builder, view, undo)


def _norm_products(builder, source, parents, target, measured=False):
    signals = [*source, *parents]
    rights = (1 << 6, 1 << 7, (1 << 6) | (1 << 7) | (58 >> 1))
    for j, ((left, _), right) in enumerate(zip(NORM_GATES, rights)):
        weight = sum(((mask >> (15 + j)) & 1) << bit
                     for bit, mask in enumerate(NORM_OUTPUTS))
        _emit_same_source_product(builder, signals, target, left, right,
                                  weight, measured=measured)


def compact_inverse_six(builder, source, zero_flag=None):
    """Return allocated inverse(source), preserving source; inverse(0)=0.

    Peak10 extras include the returned6-bit output. Four internal scratch
    bits are enough: the temporary two quadratic bits are erased before
    the two norm-parent copies are allocated. No arbitrary-target XOR API.
    """
    assert len(source) == 6
    info = cubic_data()
    rows, junk_indices, parent_forms = schedule()
    target = builder.alloc_qubits(6)
    junk = builder.alloc_qubits(2)
    gates = km.array([*target, *junk])
    for j, (a, b) in enumerate(QUADRATIC_GATES):
        view, undo = _view_pair(builder, list(source), a, b)
        builder.ccx(view[0], view[1], gates[j])
        apply_inplace_linear(builder, view, undo)
    norm = builder.alloc_qubits(2)
    signals = [*source, *gates]
    for bit, form in enumerate(NORM_OUTPUTS):
        _xor_affine(builder, signals, norm[bit], form & ((1 << 15) - 1))
    apply_inplace_linear(builder, gates, rows)
    for bit, form in enumerate(ADJUGATE_OUTPUTS):
        _xor_affine(builder, list(source), target[bit], form & 127)
    masks = builder.alloc_bits(2)
    builder.hmr(junk, masks)
    builder.free(junk)
    for j, gate_index in enumerate(junk_indices):
        _phase_affine_quadratic(builder, source, masks[j], 1 << (7 + gate_index))
    builder.free(masks)
    parents = builder.alloc_qubits(2)
    for j, (mask, affine) in enumerate(parent_forms):
        for bit, wire in enumerate(target):
            if mask >> bit & 1:
                builder.cx(wire, parents[j])
        _xor_affine(builder, list(source), parents[j], affine)
    _norm_products(builder, source, parents, norm)
    if zero_flag is not None:
        builder.x(norm)
        builder.ccx(norm[0], norm[1], zero_flag)
        builder.x(norm)
    apply_inplace_linear(builder, target, info['to_cubic'])
    for j in range(3):
        first, second = target[2 * j], target[2 * j + 1]
        # Multiplication by Norm^2 at every nonzero Norm. At Norm0 the
        # adjugate is0, and this identity action is therefore also exact.
        builder.cx(norm[0], norm[1])
        builder.ccx(norm[1], second, first)
        builder.cx(norm[0], norm[1])
        builder.ccx(norm[1], first, second)
        builder.ccx(norm[0], second, first)
    apply_inplace_linear(builder, target, rows_from_columns(info['columns']))
    masks = builder.alloc_bits(2)
    builder.hmr(norm, masks)
    builder.free(norm)
    for bit, form in enumerate(NORM_OUTPUTS):
        _phase_affine_quadratic(builder, source, masks[bit], form & ((1 << 15) - 1))
    _norm_products(builder, source, parents, masks, measured=True)
    builder.free(masks)
    masks = builder.alloc_bits(2)
    builder.hmr(parents, masks)
    builder.free(parents)
    for j, (_, form) in enumerate(NORM_GATES[:2]):
        _phase_affine_quadratic(builder, source, masks[j], form)
    builder.free(masks)
    return target
