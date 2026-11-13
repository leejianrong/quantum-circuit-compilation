# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""90-T inverse and88-T quotient phase with twelve scratch qubits."""
from functools import cache
import kickmix as km
from lowspace_field130 import invert as inverse_small
from lowspace_field import partial_inverse_product_terms
from scalar_inverse_phase import phase_inverse_six
from field_tensor import parity_pivot
from tower_inverse import (quadratic_basis, apply_inplace_linear, init_norm,
                           erase_norm, xor_product, phase_product, erase_product,
                           init_inverse_three, erase_inverse_three, kernel)


def record_uniform_hmr_event(event_type, conditional_t, mask_bits):
    """Construction-time no-op hook for the caller's exact expectation ledger.

    The caller may replace this module global with a recorder. An event
    contributes conditional_t/2**mask_bits below branch-static T. This
    hook never emits gates and must not also count scalar_inverse_phase.
    """
    return None


def _selected_parity_ccz(builder, first, second, words, coefficients):
    """One physicalCCZ on a classical-mask-selected data parity; no ancilla.

    The same recorded classical swaps restore both the data and mask view.
    Every active mask is moved to a fixed quantum pivot before thatCCZ.
    """
    wires = km.array([wire for word in words for wire in word])
    assert len(wires) == len(coefficients) and len(wires)
    choices = builder.alloc_bits(len(wires) - 1)
    builder.bit_store(choices, False)
    for j in range(1, len(wires)):
        builder.cx(coefficients[j], choices[j - 1])
        builder.push_condition(choices[j - 1])
        builder.swap(wires[0], wires[j])
        builder.swap(coefficients[0], coefficients[j])
        builder.pop_condition()
    for j in range(1, len(wires)):
        builder.push_condition(coefficients[j])
        builder.cx(wires[j], wires[0])
        builder.pop_condition()
    builder.push_condition(coefficients[0])
    builder.ccz(first, second, wires[0])
    builder.pop_condition()
    for j in reversed(range(1, len(wires))):
        builder.push_condition(coefficients[j])
        builder.cx(wires[j], wires[0])
        builder.pop_condition()
    for j in reversed(range(1, len(wires))):
        builder.push_condition(choices[j - 1])
        builder.swap(coefficients[0], coefficients[j])
        builder.swap(wires[0], wires[j])
        builder.pop_condition()
    builder.free(choices)


@cache
def _embedded_weights(component):
    field = km.GF2Field(6)
    rows = quadratic_basis(6)['from_tower']
    result = []
    for a, b, weight in kernel(3):
        embedded = sum(((row & (weight << (3 * component))).bit_count() & 1) << j
                       for j, row in enumerate(rows))
        products = tuple(field.mul(1 << bit, embedded) for bit in range(6))
        result.append((a, b, products))
    return tuple(result)


def phase_quotients_six6(builder, source, targets):
    """21-T GF64 masked quotient phase using six scratch and data pivots."""
    assert len(source) == 6 and targets
    info = quadratic_basis(6)
    apply_inplace_linear(builder, source, info['to_tower'])
    left, right = source[:3], source[3:]
    norm = init_norm(builder, left, right, info['delta'])
    inverse_norm = builder.alloc_qubits(3)
    init_inverse_three(builder, norm, inverse_norm)
    for component, word in enumerate((left, right)):
        if component == 0:
            builder.cx(right, left)
        for a, b, products in _embedded_weights(component):
            first = parity_pivot(builder, word, a)
            second = parity_pivot(builder, inverse_norm, b)
            coefficients = builder.alloc_bits(6 * len(targets))
            builder.bit_store(coefficients, False)
            for j, (_, mask) in enumerate(targets):
                for bit, product in enumerate(products):
                    for out in range(6):
                        if product >> out & 1:
                            builder.cx(mask[out], coefficients[6 * j + bit])
            _selected_parity_ccz(builder, first, second,
                                  [value for value, _ in targets], coefficients)
            builder.free(coefficients)
            parity_pivot(builder, inverse_norm, b)
            parity_pivot(builder, word, a)
        if component == 0:
            builder.cx(right, left)
    erase_inverse_three(builder, norm, inverse_norm)
    builder.free(inverse_norm)
    erase_norm(builder, left, right, norm, info['delta'])
    builder.free(norm)
    apply_inplace_linear(builder, source, info['from_tower'])


def invert_twelve12(builder, source, zero_flag=None):
    """90-T source inversion, including zero, with twelve scratch bits."""
    info = quadratic_basis(12)
    apply_inplace_linear(builder, source, info['to_tower'])
    left, right = source[:6], source[6:]
    inverse_norm = init_norm(builder, left, right, info['delta'])
    inverse_small(builder, inverse_norm, zero_flag)
    temporary = builder.alloc_qubits(6)
    masks = []
    for word in (left, right):
        xor_product(builder, word, inverse_norm, temporary)
        builder.swap(word, temporary)
        mask = builder.alloc_bits(6)
        builder.hmr(temporary, mask)
        masks.append(mask)
    builder.free(temporary)
    record_uniform_hmr_event('inverse_old_half_phase', 12, 12)
    phase_quotients_six6(builder, inverse_norm,
                         [(left, masks[0]), (right, masks[1])])
    for mask in masks:
        builder.free(mask)
    builder.cx(right, left)
    erase_norm(builder, left, right, inverse_norm, info['delta'])
    builder.free(inverse_norm)
    apply_inplace_linear(builder, source, info['from_tower'])


def phase_quotients12(builder, source, targets):
    """88-T masked quotient phase with twelve scratch, preserving all inputs."""
    info = quadratic_basis(12)
    apply_inplace_linear(builder, source, info['to_tower'])
    left, right = source[:6], source[6:]
    inverse_norm = init_norm(builder, left, right, info['delta'])
    inverse_small(builder, inverse_norm)
    temporary = builder.alloc_qubits(6)
    for component, word in enumerate((left, right)):
        if component == 0:
            builder.cx(right, left)
        xor_product(builder, word, inverse_norm, temporary)
        for value, mask, power in targets:
            phase_product(builder, value, temporary, mask,
                          partial_inverse_product_terms(component, power))
        erase_product(builder, word, inverse_norm, temporary)
        if component == 0:
            builder.cx(right, left)
    builder.free(temporary)
    apply_inplace_linear(builder, inverse_norm, quadratic_basis(6)['to_tower'])
    mask = builder.alloc_bits(6)
    builder.hmr(inverse_norm, mask)
    builder.free(inverse_norm)
    norm = init_norm(builder, left, right, info['delta'])
    phase_inverse_six(builder, norm, mask)
    builder.free(mask)
    erase_norm(builder, left, right, norm, info['delta'])
    builder.free(norm)
    apply_inplace_linear(builder, source, info['from_tower'])
