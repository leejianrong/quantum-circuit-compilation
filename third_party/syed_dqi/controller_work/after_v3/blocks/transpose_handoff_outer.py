# New copy: direct parked-phase provider and exact fourteen park-pair count.
# Isolated post-C5 gauge parking preimage; no C5 production files are modified.
# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Public-shape odd/even raw Forney preimage and fused history finish.

This component does NOT implement quantum contact-count or degree routing.
Source shapes are public. Internal half-Euclidean gap coverage is inherited
unchanged from raw_gap2_bezout. Preserve D and all returned value words until
the matching closing call. The only inter-call debt is classical HMR masks.
"""
from dataclasses import dataclass
import cw_paths  # noqa: F401
from gauge_park_lender import GaugeLender, GaugeCarrier
from monic_forney import scale
from tower_inverse import xor_product, apply_inplace_linear
from projective_carry import power_rows, erase_inverse_word, repay_inverse_mask
from gauge_park_lender import compact_inverse_twelve
import transpose_handoff_core as core
import raw_toeplitz as toeplitz
import gauge_park_paired as paired_scale


@dataclass
class Context:
    core: object
    degree: int
    histories: int
    fused: bool
    values: list
    lender: object
    source_builder_id: int


def _basis(builder, words, power):
    for word in words:
        apply_inplace_linear(builder, word, power_rows(power))


def _swap_halves(builder, even, odd):
    for a, b in zip(even, odd):
        builder.swap(a, b)


def _reverse(builder, words):
    for i in range(len(words)//2):
        builder.swap(words[i], words[-1-i])


def _even_shear(builder, odd, even, coefficients, factor, reciprocal):
    scale(builder, [odd[-1]], factor, reciprocal, True)
    for coefficient, target in zip(coefficients, even):
        xor_product(builder, coefficient, odd[-1], target)
    scale(builder, [odd[-1]], factor, reciprocal, False)


def _shape(locator, numerator, histories, fused):
    D, O, E = list(locator), list(numerator), list(histories)
    d = len(O)
    assert len(D) == d+1 and d >= 3
    assert all(len(word) == 12 for word in D+O+E)
    assert len(set(q for word in D+O+E for q in word)) == 12*len(D+O+E)
    X = list(reversed(E))+O if fused else O
    return D, O, E, X


def emit_prefix(builder, locator, numerator, histories=(), *, gauge_flag, gauge_other,
                fused=False, stage=lambda _: None):
    """C5 public degree35 preimage; sparse gauge f=1 implies other=0.

    No quantum gauge value is measured in the computational basis. The
    original flag is returned exactly on the same physical wire.
    """
    original_builder=builder
    builder=GaugeLender(builder,gauge_flag)
    D, O, E, X = _shape(locator, numerator, histories, fused)
    d = len(O)
    assert d==35 and not E and not fused
    assert len(gauge_other)==12
    assert not set([gauge_flag,*gauge_other]) & set(q for word in D+O for q in word)
    context = core.PhaseContext(builder)
    context.gauge_carrier=GaugeCarrier(builder,gauge_flag,gauge_other)
    context.gauge_h_requeries=0
    _basis(builder, D+O+E, 2048)
    A, B = D[::2], D[1::2]
    if d % 2:
        even, odd, H = O[::2][:-1], O[1::2], O[-1]
        s, q = B[-1], A[-1]
        context.outer['night_odd_leading'] = paired_scale.divide_prefix(builder, [H, q], s)
        for coefficient, target in zip(B[:-1], even):
            xor_product(builder, H, coefficient, target)
        for coefficient, target in zip(B[:-1], A[:-1]):
            xor_product(builder, q, coefficient, target)
        stage('odd_border_and_elimination')
        core.emit(builder, B, A[:-1], [even, odd], True, context, False)
        for coefficient, target in zip(B[:-1], A[:-1]):
            xor_product(builder, q, coefficient, target)
        reciprocal = compact_inverse_twelve(builder, s)
        scale(builder, [q], s, reciprocal, False)
        # The old fused finish instead dots A[1:] against even and leaves H
        # outside its T_(d-1). Solving that missing Toeplitz row cancels those
        # terms, leaving precisely this B*odd dot followed by division by s.
        for coefficient, value in zip(B[:-1], odd):
            xor_product(builder, coefficient, value, H)
        scale(builder, [H], s, reciprocal, True)
        _swap_halves(builder, even, odd)
        stage('odd_full_preimage')
    else:
        even, odd = O[::2], O[1::2]
        s = A[-1]
        reciprocal = compact_inverse_twelve(builder, s)
        _even_shear(builder, odd, even, B, s, reciprocal)
        debt = erase_inverse_word(builder, s, reciprocal, True)
        stage('even_border')
        core.emit(builder, A, B, [even, odd], True, context, False)
        _swap_halves(builder, even, odd)
        reciprocal = compact_inverse_twelve(builder, s)
        repay_inverse_mask(builder, reciprocal, debt)
        stage('even_full_preimage')
    if fused:
        coefficients = list(reversed(D[:-1]))[:len(X)-1]
        toeplitz.emit(builder, coefficients, X, s, reciprocal)
        stage('full_toeplitz_with_histories')
    context.outer['night_finish_inverse'] = erase_inverse_word(builder, s, reciprocal, True)
    _basis(builder, D+O+E, 2)
    if fused:
        _reverse(builder, X)
    stage('raw_boundary')
    context.gauge_carrier.clean_boundary()
    assert context.gauge_h_requeries==1
    return Context(context, d, len(E), fused, X, builder, id(original_builder))


def emit_closing(builder, locator, numerator, histories, record, *, stage=lambda _: None):
    assert id(builder)==record.source_builder_id
    builder=record.lender
    D, O, E, X = _shape(locator, numerator, histories, record.fused)
    assert record.degree == len(O) and record.histories == len(E) and record.values == X
    context = record.core
    assert context.builder_id == id(builder)
    if record.fused:
        _reverse(builder, X)
    _basis(builder, D+O+E, 2048)
    A, B = D[::2], D[1::2]
    s = B[-1] if len(O) % 2 else A[-1]
    reciprocal = compact_inverse_twelve(builder, s)
    repay_inverse_mask(builder, reciprocal, context.outer.pop('night_finish_inverse'))
    if record.fused:
        coefficients = list(reversed(D[:-1]))[:len(X)-1]
        toeplitz.emit(builder, coefficients, X, s, reciprocal, True)
        stage('undo_full_toeplitz_with_histories')
    if len(O) % 2:
        even, odd, H = O[::2][:-1], O[1::2], O[-1]
        q = A[-1]
        _swap_halves(builder, even, odd)
        scale(builder, [H], s, reciprocal, False)
        for coefficient, value in zip(B[:-1], odd):
            xor_product(builder, coefficient, value, H)
        scale(builder, [q], s, reciprocal, True)
        erase_inverse_word(builder, s, reciprocal)
        for coefficient, target in zip(B[:-1], A[:-1]):
            xor_product(builder, q, coefficient, target)
        stage('undo_odd_full_preimage')
        core.emit(builder, B, A[:-1], [even, odd], False, context, True)
        for coefficient, target in zip(B[:-1], A[:-1]):
            xor_product(builder, q, coefficient, target)
        for coefficient, target in zip(B[:-1], even):
            xor_product(builder, H, coefficient, target)
        paired_scale.multiply_closing(builder, [H, q], s, context.outer.pop('night_odd_leading'))
    else:
        even, odd = O[::2], O[1::2]
        _swap_halves(builder, even, odd)
        debt = erase_inverse_word(builder, s, reciprocal, True)
        stage('undo_even_full_preimage')
        core.emit(builder, A, B, [even, odd], False, context, True)
        reciprocal = compact_inverse_twelve(builder, s)
        repay_inverse_mask(builder, reciprocal, debt)
        _even_shear(builder, odd, even, B, s, reciprocal)
        erase_inverse_word(builder, s, reciprocal)
    _basis(builder, D+O+E, 2)
    assert not context.beta and not context.flags and not context.quotients and not context.outer
    context.gauge_carrier.clean_boundary()
    assert context.gauge_h_requeries==1
    assert (context.gauge_carrier.parks,context.gauge_carrier.unparks)==(14,14)
    stage('restored_raw_inputs')
