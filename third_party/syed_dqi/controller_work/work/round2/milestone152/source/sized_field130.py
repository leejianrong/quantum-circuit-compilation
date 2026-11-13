# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""Cubic field substitutions with explicit16- and18-qubit scratch caps."""
from functools import cache
import kickmix as km
from compact_six130 import compact_inverse_six
from lowspace_field import partial_inverse_product_terms
from scalar_inverse_phase import phase_inverse_six
from quantum_reciprocal import compose_mask
from tower_inverse import (quadratic_basis, apply_inplace_linear, init_norm,
                           erase_norm, xor_product, phase_product, erase_product,
                           init_inverse_three, erase_inverse_three, kernel)


def difference_cache(builder, norm, zero_flag=None):
    cached = compact_inverse_six(builder, norm, zero_flag)
    builder.cx(norm, cached)
    return cached


def erase_difference_cache(builder, current_norm, cached):
    """Pay the inversion-invariant cache using the existing4-T scalar phase."""
    info = quadratic_basis(6)
    apply_inplace_linear(builder, cached, info['to_tower'])
    mask = builder.alloc_bits(6)
    builder.hmr(cached, mask)
    builder.free(cached)
    apply_inplace_linear(builder, current_norm, info['to_tower'])
    builder.cz(mask, current_norm)
    apply_inplace_linear(builder, current_norm, info['from_tower'])
    phase_inverse_six(builder, current_norm, mask)
    builder.free(mask)


def invert_twelve18(builder, source, zero_flag=None):
    """69-T inplace inverse, preserving the old18-scratch cap."""
    info = quadratic_basis(12)
    apply_inplace_linear(builder, source, info['to_tower'])
    left, right = source[:6], source[6:]
    norm = init_norm(builder, left, right, info['delta'])
    cached = difference_cache(builder, norm, zero_flag)
    builder.cx(cached, norm)
    temporary = builder.alloc_qubits(6)
    masks = []
    for word in (left, right):
        xor_product(builder, word, norm, temporary)
        builder.swap(word, temporary)
        mask = builder.alloc_bits(6)
        builder.hmr(temporary, mask)
        masks.append(mask)
    builder.free(temporary)
    builder.cx(right, left)
    builder.cx(cached, norm)
    builder.cx(right, left)
    phase_product(builder, left, norm, masks[0], kernel(6))
    builder.cx(right, left)
    phase_product(builder, right, norm, masks[1], kernel(6))
    for mask in masks:
        builder.free(mask)
    builder.cx(cached, norm)
    erase_difference_cache(builder, norm, cached)
    erase_norm(builder, left, right, norm, info['delta'])
    builder.free(norm)
    apply_inplace_linear(builder, source, info['from_tower'])


def _quotient_body(builder, left, right, inverse_norm, targets):
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


def phase_quotients18(builder, source, targets):
    """69-T quotient phase; same API and18-scratch cap as norm_cached_field."""
    info = quadratic_basis(12)
    apply_inplace_linear(builder, source, info['to_tower'])
    left, right = source[:6], source[6:]
    norm = init_norm(builder, left, right, info['delta'])
    cached = difference_cache(builder, norm)
    builder.cx(cached, norm)
    _quotient_body(builder, left, right, norm, targets)
    builder.cx(cached, norm)
    erase_difference_cache(builder, norm, cached)
    erase_norm(builder, left, right, norm, info['delta'])
    builder.free(norm)
    apply_inplace_linear(builder, source, info['from_tower'])


def phase_quotients16(builder, source, targets):
    """84-T quotient phase using16 scratch; rebuild the norm only at erasure."""
    info = quadratic_basis(12)
    apply_inplace_linear(builder, source, info['to_tower'])
    left, right = source[:6], source[6:]
    norm = init_norm(builder, left, right, info['delta'])
    inverse_norm = compact_inverse_six(builder, norm)
    erase_norm(builder, left, right, norm, info['delta'])
    builder.free(norm)
    _quotient_body(builder, left, right, inverse_norm, targets)
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


@cache
def _partial_six(component):
    rows = quadratic_basis(6)['from_tower']
    columns = tuple(sum(((row >> (3 * component + bit)) & 1) << out
                        for out, row in enumerate(rows)) for bit in range(3))
    return tuple((left, projected, output)
                 for left, right, output in kernel(6)
                 if (projected := compose_mask(right, columns)))


def _phase_quotients_six(builder, source, targets):
    """21-T internal GF64 quotient phase;9 scratch; inverse(0)=0."""
    info = quadratic_basis(6)
    apply_inplace_linear(builder, source, info['to_tower'])
    left, right = source[:3], source[3:]
    norm = init_norm(builder, left, right, info['delta'])
    inverse_norm = builder.alloc_qubits(3)
    init_inverse_three(builder, norm, inverse_norm)
    temporary = builder.alloc_qubits(3)
    for component, word in enumerate((left, right)):
        if component == 0:
            builder.cx(right, left)
        xor_product(builder, word, inverse_norm, temporary)
        for value, mask in targets:
            phase_product(builder, value, temporary, mask, _partial_six(component))
        erase_product(builder, word, inverse_norm, temporary)
        if component == 0:
            builder.cx(right, left)
    builder.free(temporary)
    erase_inverse_three(builder, norm, inverse_norm)
    builder.free(inverse_norm)
    erase_norm(builder, left, right, norm, info['delta'])
    builder.free(norm)
    apply_inplace_linear(builder, source, info['from_tower'])


def invert_twelve16(builder, source, zero_flag=None):
    """86-T inplace inverse with16 scratch, zero-safe and phase-clean."""
    info = quadratic_basis(12)
    apply_inplace_linear(builder, source, info['to_tower'])
    left, right = source[:6], source[6:]
    norm = init_norm(builder, left, right, info['delta'])
    inverse_norm = compact_inverse_six(builder, norm, zero_flag)
    erase_norm(builder, left, right, norm, info['delta'])
    builder.free(norm)
    temporary = builder.alloc_qubits(6)
    masks = []
    for word in (left, right):
        xor_product(builder, word, inverse_norm, temporary)
        builder.swap(word, temporary)
        mask = builder.alloc_bits(6)
        builder.hmr(temporary, mask)
        masks.append(mask)
    builder.free(temporary)
    # The halves still hold oldA/N and oldB/N. Repay oldA,oldB with a
    # quotient by inverseN; this21-T helper uses15 total extras here.
    _phase_quotients_six(builder, inverse_norm,
                         [(left, masks[0]), (right, masks[1])])
    for mask in masks:
        builder.free(mask)
    builder.cx(right, left)
    # Now inverse_norm is exactly Norm(the output), with a quadratic
    # cleanup witness. No second outer norm or inverse-phase call is needed.
    erase_norm(builder, left, right, inverse_norm, info['delta'])
    builder.free(inverse_norm)
    apply_inplace_linear(builder, source, info['from_tower'])
