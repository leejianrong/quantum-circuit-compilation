# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""C2.7 narrow GF24 kernels with explicit HMR-mask ownership.

Common basis: a+b*theta, theta^2+theta=delta, with both halves in the
official GF4096 polynomial basis. Deferred inverses return masks of the
EXACT entry halves. Affine quotient masks are ordinary bit-dot masks.

Native component counts (4096-case receipts under runs/all-full):
195 deferred inverse, 283 locally closed inverse; affine quotient phase
264 T with quantum targets (180 with only a constant inverse mask);
rank99 consuming product pair462 T, including the joint-zero extension
verified under runs/unit462zero-full; guarded fallback pair483 static/
477.993408... mean. Helpers are24, except the guarded return's25.
"""
from dataclasses import dataclass
from functools import cache
import c27_paths  # noqa: F401
import kickmix as km
import extension24_tensor as Tensor
import modular_quadratic_direct as Prior
import narrow_field130 as Narrow
import zero_erasure as Zero
from coherent_border import toggle_zero
from field_tensor import (apply_linear, invert_binary_columns, parity_pivot)
from quantum_reciprocal import xor_linear
from tower_inverse import (quadratic_basis, norm_columns, init_norm, erase_norm,
                           xor_product, phase_product, phase_linear, kernel)
import phase_inverse12 as Phase12

FIELD = km.GF2Field(12)
DEFAULT_DELTA = 2048


def record_uniform_hmr_event(name, conditional_t, mask_bits):
    """Optional exact-expectation hook, valid for the documented fresh masks."""
    return None


def mul24(a, b, delta=DEFAULT_DELTA):
    a0, a1, b0, b1 = a & 4095, a >> 12, b & 4095, b >> 12
    aa, bb = FIELD.mul(a0, b0), FIELD.mul(a1, b1)
    return ((aa ^ FIELD.mul(delta, bb)) |
            ((FIELD.mul(a0 ^ a1, b0 ^ b1) ^ aa) << 12))


def inverse24(a, delta=DEFAULT_DELTA):
    if not a:
        return 0
    x, y = a & 4095, a >> 12
    norm = FIELD.mul(x, x) ^ FIELD.mul(x, y) ^ FIELD.mul(delta, FIELD.mul(y, y))
    reciprocal = FIELD.invert(norm)
    return FIELD.mul(x ^ y, reciprocal) | (FIELD.mul(y, reciprocal) << 12)


@cache
def tensor24(delta=DEFAULT_DELTA):
    return Prior.convert_tensor(delta, Tensor.multiplication_tensor(), Tensor.DELTA)


def product(builder, source, value, target, delta=DEFAULT_DELTA, tensor=None):
    return Prior.product(builder, source, value, target, delta,
                         tensor24(delta) if tensor is None else tensor)


def _classical_word(builder, length):
    word = builder.alloc_bits(length)
    builder.bit_store(word, False)
    return word


def _repay_norm_source_masks(builder, source, masks, delta, zero_flag=None):
    """Consume the GF12 inverse's tower-basis old-source masks at zero T."""
    measured = km.array([*masks[0], *masks[1]])
    polynomial = _classical_word(builder, 12)
    xor_linear(builder, measured, polynomial, quadratic_basis(12)['to_tower'])
    a_columns, b_columns = norm_columns(12, delta)
    phase_linear(builder, source[:12], polynomial, a_columns)
    phase_linear(builder, source[12:], polynomial, b_columns)
    phase_product(builder, source[:12], source[12:], polynomial, kernel(12))
    if zero_flag is not None:
        builder.cz(polynomial[0], zero_flag[0])
    builder.free(polynomial)
    for mask in masks:
        builder.free(mask)


@dataclass
class InverseRecord:
    builder_id: int
    source: tuple
    old_source_masks: tuple
    closed: bool = False


def inverse_deferred(builder, source, delta=DEFAULT_DELTA):
    """Invert a unit in195 T/24 helpers; return its two old-half masks.

    Those masks are NOT locally repaid. Call repay_source_masks once the
    exact entry source is restored, or use their concatenation as the
    constant_mask of a reciprocal-carry affine quotient phase and then
    release the record with free_source_masks.
    """
    assert len(source) == 24
    norm = init_norm(builder, source[:12], source[12:], delta)
    norm_masks = Prior.inverse_twelve_deferred(builder, norm)
    _repay_norm_source_masks(builder, source, norm_masks, delta)
    temporary = builder.alloc_qubits(12)
    masks = []
    for half in (source[:12], source[12:]):
        xor_product(builder, half, norm, temporary)
        builder.swap(half, temporary)
        mask = builder.alloc_bits(12)
        builder.hmr(temporary, mask)
        masks.append(mask)
    builder.free(temporary)
    builder.cx(source[12:], source[:12])
    erase_norm(builder, source[:12], source[12:], norm, delta)
    builder.free(norm)
    return InverseRecord(id(builder), tuple(source), tuple(masks))


def inverse_closed(builder, source, delta=DEFAULT_DELTA):
    """Locally closed inverse,283 static T/24 helpers, for component checks."""
    assert len(source) == 24
    norm = init_norm(builder, source[:12], source[12:], delta)
    norm_masks = Prior.inverse_twelve_deferred(builder, norm)
    _repay_norm_source_masks(builder, source, norm_masks, delta)
    temporary = builder.alloc_qubits(12)
    masks = []
    for half in (source[:12], source[12:]):
        xor_product(builder, half, norm, temporary)
        builder.swap(half, temporary)
        mask = builder.alloc_bits(12)
        builder.hmr(temporary, mask)
        masks.append(mask)
    builder.free(temporary)
    Narrow.phase_quotients12(builder, norm,
                            [(source[:12], masks[0], 1),
                             (source[12:], masks[1], 1)])
    for mask in masks:
        builder.free(mask)
    builder.cx(source[12:], source[:12])
    erase_norm(builder, source[:12], source[12:], norm, delta)
    builder.free(norm)


def source_mask(record):
    assert not record.closed
    return km.array([*record.old_source_masks[0], *record.old_source_masks[1]])


def free_source_masks(builder, record):
    assert id(builder) == record.builder_id and not record.closed
    for mask in record.old_source_masks:
        builder.free(mask)
    record.closed = True


def repay_source_masks(builder, restored_source, record):
    assert tuple(restored_source) == record.source
    builder.cz(source_mask(record), restored_source)
    free_source_masks(builder, record)


@cache
def _trace12(value):
    result = 0
    for _ in range(12):
        result ^= value
        value = FIELD.mul(value, value)
    assert result in (0, 1)
    return result


@cache
def _dual24(delta):
    columns = tuple(sum(_trace12(mul24(1 << j, 1 << k, delta) >> 12) << k
                        for k in range(24)) for j in range(24))
    rows = invert_binary_columns(columns)
    return tuple(apply_linear(rows, 1 << j) for j in range(24))


@cache
def _component_mask_rows(delta, component, weight):
    """For each target bit, its classical-mask parity in Tr(weight*(mu*T)_c)."""
    dual = _dual24(delta)
    result = []
    for bit in range(24):
        row = 0
        for mask_bit, mu in enumerate(dual):
            value = (mul24(mu, 1 << bit, delta) >> (12 * component)) & 4095
            row |= _trace12(FIELD.mul(weight, value)) << mask_bit
        result.append(row)
    return tuple(result)


def phase_affine_quotient(builder, source, targets=(), constant_mask=None,
                          delta=DEFAULT_DELTA):
    """Apply sum dot(mask,T/source)+dot(constant_mask,1/source).

    source is a unit. Every word/mask is preserved. targets is a list of
    disjoint (quantum24,classical24) pairs, also disjoint from source.
    It accepts an affine numerator over multiple live words WITHOUT a
    separate quantum numerator register. Static264 with targets,180 if
    only the constant term is requested. Quantum helpers:24.
    """
    assert len(source) == 24
    targets = tuple(targets)
    assert targets or constant_mask is not None
    assert all(len(word) == len(mask) == 24 for word, mask in targets)
    words = [word for word, _ in targets]
    all_wires = [*source, *(wire for word in words for wire in word)]
    assert len(set(all_wires)) == len(all_wires)
    if constant_mask is not None:
        assert len(constant_mask) == 24
    norm = init_norm(builder, source[:12], source[12:], delta)
    norm_masks = Prior.inverse_twelve_deferred(builder, norm)
    _repay_norm_source_masks(builder, source, norm_masks, delta)
    if constant_mask is not None:
        builder.cx(source[12:], source[:12])
        phase_product(builder, source[:12], norm, constant_mask[:12], kernel(12))
        builder.cx(source[12:], source[:12])
        phase_product(builder, source[12:], norm, constant_mask[12:], kernel(12))
    if targets:
        for component, half in ((0, source[12:]), (1, source[:12])):
            for first_form, second_form, weight in kernel(12):
                first = parity_pivot(builder, norm, first_form)
                second = parity_pivot(builder, half, second_form)
                coefficients = _classical_word(builder, 24 * len(targets))
                rows = _component_mask_rows(delta, component, weight)
                for j, (_, mask) in enumerate(targets):
                    for bit, row in enumerate(rows):
                        for k in range(24):
                            if row >> k & 1:
                                builder.cx(mask[k], coefficients[24 * j + bit])
                Narrow._selected_parity_ccz(builder, first, second, words, coefficients)
                builder.free(coefficients)
                parity_pivot(builder, half, second_form)
                parity_pivot(builder, norm, first_form)
        record_uniform_hmr_event('affine84_selected_target_parities', 84,
                                 24 * len(targets))
    inverse_mask = builder.alloc_bits(12)
    builder.hmr(norm, inverse_mask)
    builder.free(norm)
    original_norm = init_norm(builder, source[:12], source[12:], delta)
    Phase12.phase_inverse_twelve_polynomial(builder, original_norm, inverse_mask)
    builder.free(inverse_mask)
    erase_norm(builder, source[:12], source[12:], original_norm, delta)
    builder.free(original_norm)


@dataclass
class Record:
    builder_id: int
    delta: int
    old_target_mask: object
    tensor: object
    guarded: bool = False
    closed: bool = False


def make_record(builder, oldmask, tensor=None, delta=DEFAULT_DELTA, guarded=False):
    """Adopt a fused prefix's mask of its exact old target in common-K basis."""
    assert len(oldmask) == 24
    return Record(id(builder), delta, oldmask,
                  tensor24(delta) if tensor is None else tensor, guarded)


def emit_prefix(builder, source, value, delta=DEFAULT_DELTA, *, tensor=None,
                guarded=False):
    assert len(source) == len(value) == 24
    tensor = tensor24(delta) if tensor is None else tensor
    temporary = builder.alloc_qubits(24)
    product(builder, source, value, temporary, delta, tensor)
    builder.swap(value, temporary)
    mask = builder.alloc_bits(24)
    builder.hmr(temporary, mask)
    builder.free(temporary)
    return make_record(builder, mask, tensor, delta, guarded)


def free_product_mask(builder, record):
    """Release an adopted product mask after a caller-supplied phase repayment."""
    assert id(builder) == record.builder_id and not record.closed
    builder.free(record.old_target_mask)
    record.closed = True


def repay_product_input(builder, restored_value, record):
    """Repay/release a consuming product's mask once its exact input is restored."""
    assert len(restored_value) == 24
    builder.cz(record.old_target_mask, restored_value)
    free_product_mask(builder, record)


def emit_closing(builder, source, value, record):
    """Close a unit product pair, or guarded zero-source/zero-target pair.

    Unguarded mode:462 static T for the pair,24 helpers, on a unit source
    OR source=0 AND original target=0 (the inv0 extension is native-tested).
    Guarded fallback:483 static,25 helpers on the same domain, with
    the guard's10T phase branch active only for one fair HMR bit.
    The source must be preserved between prefix and closing.
    """
    assert id(builder) == record.builder_id and not record.closed
    assert len(source) == len(value) == 24
    delta = record.delta
    # The24-bit adjoint product MUST precede allocation of the12-bit norm.
    temporary = builder.alloc_qubits(24)
    builder.cx(source[12:], source[:12])
    product(builder, source, value, temporary, delta, record.tensor)
    builder.cx(source[12:], source[:12])
    builder.swap(value, temporary)
    old_product_mask = builder.alloc_bits(24)
    builder.hmr(temporary, old_product_mask)
    builder.free(temporary)
    norm = init_norm(builder, source[:12], source[12:], delta)
    flag = None
    if record.guarded:
        flag = builder.alloc_qubits(1)
        toggle_zero(builder, norm, flag[0])
        builder.cx(flag[0], norm[0])
    norm_masks = Prior.inverse_twelve_deferred(builder, norm)
    _repay_norm_source_masks(builder, source, norm_masks, delta, flag)
    temporary = builder.alloc_qubits(12)
    scaled_masks = []
    for half in (value[:12], value[12:]):
        xor_product(builder, half, norm, temporary)
        builder.swap(half, temporary)
        mask = builder.alloc_bits(12)
        builder.hmr(temporary, mask)
        scaled_masks.append(mask)
    builder.free(temporary)
    inverse_mask = builder.alloc_bits(12)
    builder.hmr(norm, inverse_mask)
    builder.free(norm)
    norm = init_norm(builder, source[:12], source[12:], delta)
    if flag is not None:
        builder.cx(flag[0], norm[0])
    Phase12.phase_inverse_twelve_polynomial(builder, norm, inverse_mask)
    builder.free(inverse_mask)
    for half, mask in zip((value[:12], value[12:]), scaled_masks):
        phase_product(builder, half, norm, mask, kernel(12))
        builder.free(mask)
    if flag is not None:
        builder.cx(flag[0], norm[0])
        Zero.erase(builder, norm, flag)
        builder.free(flag)
        record_uniform_hmr_event('guard_zero_flag_phase', 10, 1)
    erase_norm(builder, source[:12], source[12:], norm, delta)
    builder.free(norm)
    builder.cz(record.old_target_mask, value)
    builder.free(record.old_target_mask)
    phase_product(builder, source, value, old_product_mask, record.tensor)
    builder.free(old_product_mask)
    record.closed = True
