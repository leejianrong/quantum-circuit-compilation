# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Narrow direct quadratic-field product with a consuming paired return.

Root proposed the narrow inverse/deferred-phase construction. This emitter
spells it out for arbitrary public trace-one delta, theta^2+theta+delta=0.
Every field half uses the supplied GF4096 polynomial basis. Source must be
nonzero. The prefix preserves source and leaves one classical mask of its
old target. Any source/output-preserving diagonal operation may intervene.
Closing restores the original target, source and all quantum scratch.

The current return uses multiplication by the conjugate and two narrow norm
inversions. Its first norm inversion defers two GF64-half masks. With a
rank-p product the pair costs2p+285 staticT:483 with the new rank99 tensor,
537 with the simple rank126 tensor. At most24 quantum scratch are needed.
This is NOT a full CRT finish, metadata controller or failure proof.
"""
from dataclasses import dataclass
from functools import cache
import kickmix as km
from tower_inverse import (init_norm, erase_norm, xor_product, kernel, phase_product,
                           quadratic_basis, apply_inplace_linear)
from field_tensor import accumulate_product
import narrow_field130 as Narrow

FIELD = km.GF2Field(12)


@cache
def terms(delta):
    result = []
    for left, right, value in kernel(12):
        # P0=a*x contributes to both output halves.
        result.append((left, right, value | (value << 12)))
    for left, right, value in kernel(12):
        # P1=b*y contributes delta*P1 to the low half.
        result.append((left << 12, right << 12, FIELD.mul(delta, value)))
    for left, right, value in kernel(12):
        # P2=(a+b)*(x+y) contributes to the high half.
        result.append((left | (left << 12), right | (right << 12), value << 12))
    assert len(result) == 126
    return tuple(result)


def product(builder, source, value, target, delta, tensor=None):
    assert len(source) == len(value) == len(target) == 24
    accumulate_product(builder, source, value, target, terms(delta) if tensor is None else tensor)


def convert_tensor(delta, tensor, canonical_delta=2048):
    """Transport one fixed quadratic tensor through a public field isomorphism."""
    kappa = next(k for k in range(4096) if FIELD.mul(k, k) ^ k == delta ^ canonical_delta)
    def mask_view(mask):
        low, high = mask & 4095, mask >> 12
        high ^= sum(((low & FIELD.mul(kappa, 1 << j)).bit_count() & 1) << j for j in range(12))
        return low | (high << 12)
    return tuple((mask_view(a), mask_view(b),
                  ((value & 4095) ^ FIELD.mul(kappa, value >> 12)) | (value & (4095 << 12)))
                 for a, b, value in tensor)


def inverse_twelve_deferred(builder, source):
    """69T,12 scratch; two source-half masks are returned instead of a21T phase.

This is the supplied narrow inverse with only its old-half phase postponed.
The masks refer to the entry source in the standard GF12 quadratic tower.
All lower norm scaffolds remain locally closed.
"""
    info = quadratic_basis(12)
    apply_inplace_linear(builder, source, info['to_tower'])
    left, right = source[:6], source[6:]
    reciprocal_norm = init_norm(builder, left, right, info['delta'])
    Narrow.inverse_small(builder, reciprocal_norm)
    temporary = builder.alloc_qubits(6)
    masks = []
    for word in (left, right):
        xor_product(builder, word, reciprocal_norm, temporary)
        builder.swap(word, temporary)
        mask = builder.alloc_bits(6)
        builder.hmr(temporary, mask)
        masks.append(mask)
    builder.free(temporary)
    builder.cx(right, left)
    erase_norm(builder, left, right, reciprocal_norm, info['delta'])
    builder.free(reciprocal_norm)
    apply_inplace_linear(builder, source, info['from_tower'])
    return masks


def repay_twelve_source(builder, source, masks):
    info = quadratic_basis(12)
    apply_inplace_linear(builder, source, info['to_tower'])
    for half, mask in zip((source[:6], source[6:]), masks):
        builder.cz(mask, half)
        builder.free(mask)
    apply_inplace_linear(builder, source, info['from_tower'])


def inverse(builder, source, delta, *, defer_old_halves=False):
    """In-place unit inverse;304T locally closed or216T with two masks.

The deferred masks refer to the exact two source halves at this function's
entry. Repay them only after those original halves are reconstructed. Norm
cleanup is local in both variants and uses the inverse output's norm.
"""
    assert len(source) == 24
    a, b = source[:12], source[12:]
    norm_inverse = init_norm(builder, a, b, delta)
    Narrow.invert_twelve12(builder, norm_inverse)
    temporary = builder.alloc_qubits(12)
    masks = []
    for half in (a, b):
        xor_product(builder, half, norm_inverse, temporary)
        builder.swap(half, temporary)
        mask = builder.alloc_bits(12)
        builder.hmr(temporary, mask)
        masks.append(mask)
    builder.free(temporary)
    if not defer_old_halves:
        # Before conjugation: half_new=half_old/norm_old. Hence
        # half_old=half_new/norm_inverse, exactly this quotient phase.
        Narrow.phase_quotients12(builder, norm_inverse,
                                [(a, masks[0], 1), (b, masks[1], 1)])
        for mask in masks:
            builder.free(mask)
    builder.cx(b, a)
    # Norm(inverse(source))=inverse(Norm(source)).
    erase_norm(builder, a, b, norm_inverse, delta)
    builder.free(norm_inverse)
    return masks if defer_old_halves else None


@dataclass
class Record:
    builder_id: int
    delta: int
    old_target_mask: object
    tensor: object


def emit_prefix(builder, source, value, delta, *, tensor=None):
    tensor = terms(delta) if tensor is None else tensor
    temporary = builder.alloc_qubits(24)
    product(builder, source, value, temporary, delta, tensor)
    builder.swap(value, temporary)
    mask = builder.alloc_bits(24)
    builder.hmr(temporary, mask)
    builder.free(temporary)
    return Record(id(builder), delta, mask, tensor)


def emit_closing(builder, source, value, record):
    assert id(builder) == record.builder_id
    delta = record.delta
    temporary = builder.alloc_qubits(24)
    builder.cx(source[12:], source[:12])
    product(builder, source, value, temporary, delta, record.tensor)
    builder.cx(source[12:], source[:12])
    builder.swap(value, temporary)
    old_product_mask = builder.alloc_bits(24)
    builder.hmr(temporary, old_product_mask)
    builder.free(temporary)
    norm = init_norm(builder, source[:12], source[12:], delta)
    norm_masks = inverse_twelve_deferred(builder, norm)
    temporary = builder.alloc_qubits(12)
    scaled_masks = []
    for half in (value[:12], value[12:]):
        xor_product(builder, half, norm, temporary)
        builder.swap(half, temporary)
        mask = builder.alloc_bits(12)
        builder.hmr(temporary, mask)
        scaled_masks.append(mask)
    builder.free(temporary)
    Narrow.invert_twelve12(builder, norm)
    repay_twelve_source(builder, norm, norm_masks)
    for half, mask in zip((value[:12], value[12:]), scaled_masks):
        phase_product(builder, half, norm, mask, kernel(12))
        builder.free(mask)
    erase_norm(builder, source[:12], source[12:], norm, delta)
    builder.free(norm)
    # The input target is now restored, and its original product is a
    # bilinear function of these restored source and target registers.
    builder.cz(record.old_target_mask, value)
    builder.free(record.old_target_mask)
    phase_product(builder, source, value, old_product_mask, record.tensor)
    builder.free(old_product_mask)
