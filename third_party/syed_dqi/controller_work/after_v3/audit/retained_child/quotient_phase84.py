# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Preserved-source quotient phase with a retained three-bit child norm.

New isolated source model:84 static T/12 helpers, replacing phase85's
four-T inverse-phase cleanup by a three-T inverse of an already-live word.
The two inverse-component products are applied directly as phase tensors,
so their six-bit output buffer is not needed while the child stays live.
No production or previously qualified component source is changed.
"""
from functools import cache
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
K24 = HERE.parents[1] / 'k24'
if str(K24) not in sys.path:
    sys.path.insert(0, str(K24))
import quotient_phase85 as Base  # noqa: E402
import kickmix as km  # noqa: E402
from field_tensor import parity_pivot  # noqa: E402
from lowspace_field import inverse_three  # noqa: E402

Original = Base.Original
Nested = Base.Nested
Arithmetic = Base.Arithmetic


def _rank(rows):
    pivots = {}
    for row in rows:
        while row:
            bit = row.bit_length()-1
            if bit not in pivots:
                pivots[bit] = row
                break
            row ^= pivots[bit]
    return len(pivots)


@cache
def target_mask_rows(component, power, weight):
    """Mask -> parity coefficients on one twelve-bit quantum target.

    Contract the accepted partial-product phase tensor with one public
    nonzero six-bit product output. Rows use the original physical mask
    coordinates; no quantum field multiplication or basis is assumed free.
    """
    assert component in (0, 1) and 0 < weight < 64
    assert power > 0 and power & (power-1) == 0
    rows = [0]*12
    for left, right, output in Original.partial_inverse_product_terms(component, power):
        if (right & weight).bit_count() & 1:
            for bit in range(12):
                if left >> bit & 1:
                    rows[bit] ^= output
    # This is multiplication by a nonzero embedded field element, followed
    # by the invertible dot-mask transpose, for every Frobenius power.
    assert _rank(rows) == 12
    return tuple(rows)


def inverse_six_keep_child(builder, source):
    """Inv0 in21 T; return entry masks and live inv0(norm(entry)).

    The source is in the standard six-bit polynomial basis on entry/exit.
    The returned child is three bits in the standard GF8 basis. The caller
    must close it explicitly; it is never an unowned dirty/clean promise.
    """
    assert len(source) == 6
    info = Original.quadratic_basis(6)
    Original.apply_inplace_linear(builder, source, info['to_tower'])
    left, right = source[:3], source[3:]
    child = Original.init_norm(builder, left, right, info['delta'])
    inverse_three(builder, child)
    temporary = builder.alloc_qubits(3)
    masks = []
    for half in (left, right):
        Original.xor_product(builder, half, child, temporary)
        builder.swap(half, temporary)
        mask = builder.alloc_bits(3)
        builder.hmr(temporary, mask)
        masks.append(mask)
    builder.free(temporary)
    builder.cx(right, left)
    Original.apply_inplace_linear(builder, source, info['from_tower'])
    return tuple(masks), child


def inverse_component_phases(builder, left, right, inverse_norm, targets):
    """Thirty zero-helper selected-parity CCZ leaves, all views restored."""
    targets = tuple(targets)
    assert targets
    assert len(left) == len(right) == len(inverse_norm) == 6
    for component, word in enumerate((left, right)):
        if component == 0:
            builder.cx(right, left)
        for a, b, weight in Original.kernel(6):
            first = parity_pivot(builder, word, a)
            second = parity_pivot(builder, inverse_norm, b)
            coefficients = builder.alloc_bits(12*len(targets))
            builder.bit_store(coefficients, False)
            for j, (_, mask, power) in enumerate(targets):
                for bit, row in enumerate(target_mask_rows(component, power, weight)):
                    for k in range(12):
                        if row >> k & 1:
                            builder.cx(mask[k], coefficients[12*j+bit])
            Original._selected_parity_ccz(
                builder, first, second, [value for value, _, _ in targets], coefficients)
            builder.free(coefficients)
            parity_pivot(builder, inverse_norm, b)
            parity_pivot(builder, word, a)
        if component == 0:
            builder.cx(right, left)


def phase_quotients12(builder, source, targets):
    """Same preserved-source inv0 quotient phase; no source-unit promise."""
    targets = tuple(targets)
    assert len(source) == 12 and targets
    assert all(len(value) == len(mask) == 12 for value, mask, _ in targets)
    quantum = [*source, *(wire for value, _, _ in targets for wire in value)]
    assert all(isinstance(wire, km.q) for wire in quantum)
    assert len(set(quantum)) == len(quantum)
    info = Original.quadratic_basis(12)
    Original.apply_inplace_linear(builder, source, info['to_tower'])
    left, right = source[:6], source[6:]
    inverse_norm = Original.init_norm(builder, left, right, info['delta'])
    child_masks, child = inverse_six_keep_child(builder, inverse_norm)
    Nested.repay_norm_entry(builder, left, right, info['delta'], child_masks)

    # Keep child3 while these direct phases avoid the old six-bit buffer.
    inverse_component_phases(builder, left, right, inverse_norm, targets)
    Original.record_uniform_hmr_event('retained_child30_selected_target_parities',
                                     30, 12*len(targets))

    child_info = Original.quadratic_basis(6)
    Original.apply_inplace_linear(builder, inverse_norm, child_info['to_tower'])
    inverse_mask = builder.alloc_bits(6)
    builder.hmr(inverse_norm, inverse_mask)
    builder.free(inverse_norm)

    # Reconstruct exact entry N. Its inverse tower halves were
    # ((x+y)*child, y*child), so this HMR debt is now Clifford.
    norm = Original.init_norm(builder, left, right, info['delta'])
    Original.apply_inplace_linear(builder, norm, child_info['to_tower'])
    x, y = norm[:3], norm[3:]
    builder.cx(y, x)
    Original.phase_product(builder, x, child, inverse_mask[:3], Original.kernel(3))
    builder.cx(y, x)
    Original.phase_product(builder, y, child, inverse_mask[3:], Original.kernel(3))
    builder.free(inverse_mask)

    # Inverting the retained child costs3 T and restores the original
    # norm of N, which has an exact quadratic eraser on the still-live N.
    inverse_three(builder, child)
    Original.erase_norm(builder, x, y, child, child_info['delta'])
    builder.free(child)
    Original.apply_inplace_linear(builder, norm, child_info['from_tower'])
    Original.erase_norm(builder, left, right, norm, info['delta'])
    builder.free(norm)
    Original.apply_inplace_linear(builder, source, info['from_tower'])


def inverse_closed(builder, source, delta=Arithmetic.DEFAULT_DELTA):
    """276 static T/24 helpers, with the same inv0 closed-inverse contract."""
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


def source_ledger(targets=2):
    assert targets > 0
    discount = 30/(1 << (12*targets))
    return dict(status='SOURCE_MODEL_NOT_NATIVE_RESULT',
                phase_static_T=84, phase_helpers=12,
                phase_uniform_target_mask_mean_T=84-discount,
                exact_count='54 + 30*[any target mask is nonzero]',
                closed_inverse_static_T=276, inverse_helpers=24,
                actual_two_target_inverse_mean_T=276-30/(1 << 24),
                actual_v3_closed_inverse_calls=3,
                whole_static_saving_vs_phase85=3,
                whole_mean_saving_vs_phase85=3*(1-4/64+30/(1 << 24)),
                extra_quantum_qubits=0, admitted_domain_change=False,
                event_scope='Independent uniform target masks; actual closed-inverse masks are fresh24-bit HMR.',
                supersedes_not_additive_with_final_norm_guard=True)
