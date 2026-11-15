# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Deferred unit division and one shared-norm direct-carry return.

Unit source u is preserved.  Prefix maps v to v/u for294T/24 helpers and
returns the exact old-v, old-adjoint and inverse-norm HMR masks.  A matching
return restores v, optionally divides the next pending u*Y word, and pays
all masks before u or v changes.  It is546T with next Y,363T without.

These are source counts pending native checks.  No C5 file is changed.
"""
from dataclasses import dataclass
import ew_paths  # noqa: F401
import kickmix as km
import gf24_arithmetic as A
import modular_quadratic_direct as Prior
import narrow_field130 as Narrow
import phase_inverse12 as Phase12
from field_tensor import parity_pivot
from tower_inverse import init_norm, erase_norm, xor_product, phase_product, kernel


@dataclass
class DivisionRecord:
    builder_id: int
    source: tuple
    target: tuple
    old_target_mask: object
    adjoint_masks: tuple
    inverse_norm_mask: object
    delta: int
    closed: bool = False


def _adjoint_consume(builder, source, target, delta):
    """target <- conjugate(source)*target,99T; return its exact old mask."""
    temporary = builder.alloc_qubits(24)
    builder.cx(source[12:], source[:12])
    A.product(builder, source, target, temporary, delta)
    builder.cx(source[12:], source[:12])
    builder.swap(target, temporary)
    mask = builder.alloc_bits(24)
    builder.hmr(temporary, mask)
    builder.free(temporary)
    return mask


def _consume_halves(builder, reciprocal_norm, target):
    """Two42T scalar products,12 additional helpers; return old-half masks."""
    temporary = builder.alloc_qubits(12)
    masks = []
    for half in (target[:12], target[12:]):
        xor_product(builder, half, reciprocal_norm, temporary)
        builder.swap(half, temporary)
        mask = builder.alloc_bits(12)
        builder.hmr(temporary, mask)
        masks.append(mask)
    builder.free(temporary)
    return tuple(masks)


def _inverse_norm(builder, source, delta):
    norm = init_norm(builder, source[:12], source[12:], delta)
    masks = Prior.inverse_twelve_deferred(builder, norm)
    A._repay_norm_source_masks(builder, source, masks, delta)
    return norm


def divide_deferred(builder, source, target, delta=2048):
    """Preserve unit source u and consume v into v/u;294T,24 helpers."""
    assert len(source) == len(target) == 24 and not set(source) & set(target)
    old_target = _adjoint_consume(builder, source, target, delta)
    norm = _inverse_norm(builder, source, delta)
    adjoint_masks = _consume_halves(builder, norm, target)
    inverse_norm_mask = builder.alloc_bits(12)
    builder.hmr(norm, inverse_norm_mask)
    builder.free(norm)
    return DivisionRecord(id(builder), tuple(source), tuple(target), old_target,
                          adjoint_masks, inverse_norm_mask, delta)


def _quotient_phase_with_norm(builder, source, reciprocal_norm, target, mask, delta):
    """dot(mask,target/source),84T; caller owns the live inverse norm."""
    assert len(source) == len(target) == len(mask) == 24
    assert len(reciprocal_norm) == 12
    for component, half in ((0, source[12:]), (1, source[:12])):
        for first_form, second_form, weight in kernel(12):
            first = parity_pivot(builder, reciprocal_norm, first_form)
            second = parity_pivot(builder, half, second_form)
            coefficients = A._classical_word(builder, 24)
            rows = A._component_mask_rows(delta, component, weight)
            for bit, row in enumerate(rows):
                for k in range(24):
                    if row >> k & 1:
                        builder.cx(mask[k], coefficients[bit])
            Narrow._selected_parity_ccz(builder, first, second, (target,), coefficients)
            builder.free(coefficients)
            parity_pivot(builder, half, second_form)
            parity_pivot(builder, reciprocal_norm, first_form)
    A.record_uniform_hmr_event('direct_carry84_selected_target_parities', 84, 24)


def restore_with_shared_norm(builder, source, target, record, *,
                             next_word=None, next_input_record=None):
    """Restore v and optional raw Y, paying every prefix/return phase debt.

    Entry target=v/u; next_word, if present, equals u*Y.  Exit target=v and
    next_word=Y.  source=u remains unchanged.  This must precede the inverse
    tail selection and inverse query sweep.  Classical masks in record and
    next_input_record are consumed exactly once.
    """
    assert record.builder_id == id(builder) and not record.closed
    assert tuple(source) == record.source and tuple(target) == record.target
    assert (next_word is None) == (next_input_record is None)
    if next_word is not None:
        assert len(next_word) == 24
        assert not set(next_word) & (set(source) | set(target))
    delta = record.delta
    # Every24-helper product precedes allocation of the12-bit norm.
    head_return = A.emit_prefix(builder, source, target, delta)
    next_old = None
    if next_word is not None:
        next_old = _adjoint_consume(builder, source, next_word, delta)
    inverse_norm = _inverse_norm(builder, source, delta)
    next_adjoint = None
    if next_word is not None:
        next_adjoint = _consume_halves(builder, inverse_norm, next_word)

    # The prefix's three debts: old v, conjugate(u)*v, and1/Norm(u).
    builder.cz(record.old_target_mask, target)
    builder.free(record.old_target_mask)
    builder.cx(source[12:], source[:12])
    phase_product(builder, source, target,
                  km.array([*record.adjoint_masks[0], *record.adjoint_masks[1]]),
                  A.tensor24(delta))
    builder.cx(source[12:], source[:12])
    for mask in record.adjoint_masks:
        builder.free(mask)
    builder.cz(record.inverse_norm_mask, inverse_norm)
    builder.free(record.inverse_norm_mask)

    # New old-head debt is v/u; it shares the inverse norm already live.
    _quotient_phase_with_norm(builder, source, inverse_norm, target,
                              head_return.old_target_mask, delta)
    A.free_product_mask(builder, head_return)
    if next_word is not None:
        # Old next word was u*Y. Its original forward input was raw Y.
        phase_product(builder, source, next_word, next_old, A.tensor24(delta))
        builder.free(next_old)
        A.repay_product_input(builder, next_word, next_input_record)

    inverse_mask = builder.alloc_bits(12)
    builder.hmr(inverse_norm, inverse_mask)
    builder.free(inverse_norm)
    norm = init_norm(builder, source[:12], source[12:], delta)
    Phase12.phase_inverse_twelve_polynomial(builder, norm, inverse_mask)
    builder.free(inverse_mask)
    if next_word is not None:
        # Its old adjoint was conjugate(u)*(u*Y)=Norm(u)*Y.
        for half, mask in zip((next_word[:12], next_word[12:]), next_adjoint):
            phase_product(builder, norm, half, mask, kernel(12))
            builder.free(mask)
    erase_norm(builder, source[:12], source[12:], norm, delta)
    builder.free(norm)
    record.closed = True


def source_ledger(with_next=True):
    return dict(status='SOURCE_MODEL_NOT_YET_NATIVE_CHECKED', prefix_T=294,
                return_T=546 if with_next else 363, helpers=24,
                current_product_T=99, next_adjoint_product_T=99 if with_next else 0,
                initial_norm_T=42, norm_inverse_T=69,
                next_scalar_products_T=84 if with_next else 0,
                quotient_phase_T=84, cleanup_norm_T=42, inverse_norm_phase_T=27,
                prefix_mask_bits=60, new_domain_assumptions=False)
