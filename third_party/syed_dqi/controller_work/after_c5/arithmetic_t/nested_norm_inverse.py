# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""66-T deferred GF4096 inverse by paying its child's entry norm directly.

The old69-T implementation closes a GF64 child with a3-T reconstruction of
the child's original GF8 norm. Here the GF64 child returns its old-entry
half masks instead. Its entry is the known GF64 quadratic norm of the still
unchanged parent GF4096 halves, so that mask is paid at zero T before those
halves change. The parent's returned mask ABI is exactly the original one.

Source model until native checks:66T,12 helpers, inv0 on all4096 values.
No original production source is modified. convert_tensor/product are exact
aliases supplied for an isolated copy of the GF24 caller.
"""
import c27_paths  # noqa: F401
import kickmix as km
from lowspace_field import inverse_three
from quantum_reciprocal import xor_linear
from tower_inverse import (quadratic_basis, apply_inplace_linear, init_norm,
                           erase_norm, norm_columns, xor_product, phase_product,
                           phase_linear, kernel)
from modular_quadratic_direct import convert_tensor, product  # unchanged aliases


def inverse_six_deferred(builder, source):
    """In-place inv0 in21T/6 helpers, returning exact entry tower-half masks."""
    assert len(source) == 6
    info = quadratic_basis(6)
    apply_inplace_linear(builder, source, info['to_tower'])
    left, right = source[:3], source[3:]
    norm = init_norm(builder, left, right, info['delta'])
    inverse_three(builder, norm)
    temporary = builder.alloc_qubits(3)
    masks = []
    for half in (left, right):
        xor_product(builder, half, norm, temporary)
        builder.swap(half, temporary)
        mask = builder.alloc_bits(3)
        builder.hmr(temporary, mask)
        masks.append(mask)
    builder.free(temporary)
    builder.cx(right, left)
    # Norm(inv0(source_entry))=inv0(Norm(source_entry)), including zero.
    erase_norm(builder, left, right, norm, info['delta'])
    builder.free(norm)
    apply_inplace_linear(builder, source, info['from_tower'])
    return tuple(masks)


def repay_norm_entry(builder, left, right, delta, child_masks):
    """Pay masks of the GF64 norm of preserved six-bit parent halves.

    The masks are in the GF64 quadratic tower coordinates of the child's
    exact entry. xor_linear takes columns: passing the to_tower rows here
    implements the required transpose on the classical mask.
    """
    assert len(left) == len(right) == 6
    assert len(child_masks) == 2 and all(len(mask) == 3 for mask in child_masks)
    measured = km.array([*child_masks[0], *child_masks[1]])
    polynomial_mask = builder.alloc_bits(6)
    builder.bit_store(polynomial_mask, False)
    xor_linear(builder, measured, polynomial_mask, quadratic_basis(6)['to_tower'])
    a_columns, b_columns = norm_columns(6, delta)
    phase_linear(builder, left, polynomial_mask, a_columns)
    phase_linear(builder, right, polynomial_mask, b_columns)
    phase_product(builder, left, right, polynomial_mask, kernel(6))
    builder.free(polynomial_mask)
    for mask in child_masks:
        builder.free(mask)


def inverse_twelve_deferred(builder, source):
    """In-place inv0 in66T/12 helpers; original69-T returned-mask ABI."""
    assert len(source) == 12
    info = quadratic_basis(12)
    apply_inplace_linear(builder, source, info['to_tower'])
    left, right = source[:6], source[6:]
    reciprocal_norm = init_norm(builder, left, right, info['delta'])
    child_masks = inverse_six_deferred(builder, reciprocal_norm)
    # Crucial seam: the parent halves have not yet been scaled or changed.
    repay_norm_entry(builder, left, right, info['delta'], child_masks)
    temporary = builder.alloc_qubits(6)
    masks = []
    for half in (left, right):
        xor_product(builder, half, reciprocal_norm, temporary)
        builder.swap(half, temporary)
        mask = builder.alloc_bits(6)
        builder.hmr(temporary, mask)
        masks.append(mask)
    builder.free(temporary)
    builder.cx(right, left)
    erase_norm(builder, left, right, reciprocal_norm, info['delta'])
    builder.free(reciprocal_norm)
    apply_inplace_linear(builder, source, info['from_tower'])
    return masks
