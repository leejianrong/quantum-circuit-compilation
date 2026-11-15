# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Preserved-source quotient phase with a deferred GF64 norm child.

Source model:85 static T/12 helpers rather than the supplied88/12.
The only change is24->21 for the child inverse; its exact entry masks
are paid from the preserved parent halves before either half is changed.
Value/domain/powers/mask APIs match narrow_field130.phase_quotients12.
Native verification is separate. No production module is modified.
"""
import k24_paths  # noqa: F401
import narrow_field130 as Original
import nested_norm_inverse as Nested
import gf24_nested_norm as Arithmetic


def phase_quotients12(builder, source, targets):
    """Phase sum dot(mask,value*inv0(source)**power), preserving inputs."""
    assert len(source) == 12 and targets
    info = Original.quadratic_basis(12)
    Original.apply_inplace_linear(builder, source, info['to_tower'])
    left, right = source[:6], source[6:]
    inverse_norm = Original.init_norm(builder, left, right, info['delta'])
    child_masks = Nested.inverse_six_deferred(builder, inverse_norm)
    Nested.repay_norm_entry(builder, left, right, info['delta'], child_masks)
    temporary = builder.alloc_qubits(6)
    for component, word in enumerate((left, right)):
        if component == 0:
            builder.cx(right, left)
        Original.xor_product(builder, word, inverse_norm, temporary)
        for value, mask, power in targets:
            Original.phase_product(builder, value, temporary, mask,
                                   Original.partial_inverse_product_terms(component, power))
        Original.erase_product(builder, word, inverse_norm, temporary)
        if component == 0:
            builder.cx(right, left)
    builder.free(temporary)
    Original.apply_inplace_linear(builder, inverse_norm,
                                  Original.quadratic_basis(6)['to_tower'])
    mask = builder.alloc_bits(6)
    builder.hmr(inverse_norm, mask)
    builder.free(inverse_norm)
    norm = Original.init_norm(builder, left, right, info['delta'])
    Original.phase_inverse_six(builder, norm, mask)
    builder.free(mask)
    Original.erase_norm(builder, left, right, norm, info['delta'])
    builder.free(norm)
    Original.apply_inplace_linear(builder, source, info['from_tower'])


def inverse_closed(builder, source, delta=Arithmetic.DEFAULT_DELTA):
    """277-T/24-helper locally closed K24 inverse, including zero."""
    assert len(source) == 24
    norm = Arithmetic.init_norm(builder, source[:12], source[12:], delta)
    norm_masks = Arithmetic.Prior.inverse_twelve_deferred(builder, norm)
    Arithmetic._repay_norm_source_masks(builder, source, norm_masks, delta)
    temporary = builder.alloc_qubits(12)
    masks = []
    for half in (source[:12], source[12:]):
        Arithmetic.xor_product(builder, half, norm, temporary)
        builder.swap(half, temporary)
        mask = builder.alloc_bits(12)
        builder.hmr(temporary, mask)
        masks.append(mask)
    builder.free(temporary)
    phase_quotients12(builder, norm,
                      [(source[:12], masks[0], 1),
                       (source[12:], masks[1], 1)])
    for mask in masks:
        builder.free(mask)
    builder.cx(source[12:], source[:12])
    Arithmetic.erase_norm(builder, source[:12], source[12:], norm, delta)
    builder.free(norm)
