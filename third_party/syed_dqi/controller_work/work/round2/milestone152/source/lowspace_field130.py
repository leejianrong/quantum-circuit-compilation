# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""Measured-parent cleanup for24/117-T inverses at6/12 scratch qubits."""
from lowspace_field import inverse_three, partial_inverse_product_terms
from tower_inverse import (quadratic_basis, apply_inplace_linear, init_norm,
                           erase_norm, xor_product, phase_product, erase_product,
                           init_inverse_three, erase_inverse_three, kernel)


def invert(builder, source, zero_flag=None):
    degree = len(source)
    if degree == 3:
        if zero_flag is not None:
            builder.x(source)
            temporary = builder.alloc_qubits(1)
            builder.init_and(source[0],source[1],temporary[0])
            builder.ccx(temporary[0],source[2],zero_flag)
            builder.del_and(source[0],source[1],temporary[0]);builder.free(temporary)
            builder.x(source)
        inverse_three(builder, source)
        return
    assert degree in (6, 12)
    info, half = quadratic_basis(degree), degree // 2
    apply_inplace_linear(builder, source, info['to_tower'])
    left, right = source[:half], source[half:]
    norm = init_norm(builder, left, right, info['delta'])
    invert(builder, norm, zero_flag)
    temporary = builder.alloc_qubits(half)
    measured = []
    for word in (left, right):
        xor_product(builder, word, norm, temporary)
        builder.swap(word, temporary)
        mask = builder.alloc_bits(half)
        builder.hmr(temporary, mask)
        measured.append(mask)
    builder.free(temporary)
    builder.cx(right, left)
    if degree == 6:
        # The live norm is1/N. Build N once in a fresh three-bit word.
        # It replaces the two in-place3-T flips and has a quadratic eraser.
        old_norm = builder.alloc_qubits(3)
        init_inverse_three(builder, norm, old_norm)
    else:
        invert(builder, norm)
        old_norm = norm
    builder.cx(right, left)
    phase_product(builder, left, old_norm, measured[0], kernel(half))
    builder.cx(right, left)
    phase_product(builder, right, old_norm, measured[1], kernel(half))
    for mask in measured:
        builder.free(mask)
    if degree == 6:
        erase_inverse_three(builder, norm, old_norm)
        builder.free(old_norm)
    else:
        invert(builder, norm)
    erase_norm(builder, left, right, norm, info['delta'])
    builder.free(norm)
    apply_inplace_linear(builder, source, info['from_tower'])


def phase_quotients(builder, source, targets):
    """Preserved source/masks; sum dot(mask,word*inverse(source)^power)."""
    assert len(source) == 12
    info = quadratic_basis(12)
    apply_inplace_linear(builder, source, info['to_tower'])
    left, right = source[:6], source[6:]
    norm = init_norm(builder, left, right, info['delta'])
    invert(builder, norm)
    temporary = builder.alloc_qubits(6)
    for component, word in enumerate((left, right)):
        if component == 0:
            builder.cx(right, left)
        xor_product(builder, word, norm, temporary)
        for value, mask, power in targets:
            phase_product(builder, value, temporary, mask,
                          partial_inverse_product_terms(component, power))
        erase_product(builder, word, norm, temporary)
        if component == 0:
            builder.cx(right, left)
    builder.free(temporary)
    invert(builder, norm)
    erase_norm(builder, left, right, norm, info['delta'])
    builder.free(norm)
    apply_inplace_linear(builder, source, info['from_tower'])
