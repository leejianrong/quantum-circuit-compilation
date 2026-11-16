# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Separate C5 candidate: share one reciprocal across the finish/outer seam.

The prefix is the unmodified full-degree35 outer followed by the unmodified
projective finish. Only closing changes. Move its independent scalar closing
after the seventeen quadratic closings, keep inverse(D35), and square-root
that word alongside D before the odd outer return. This removes one65-T
inverse construction and one27-T inverse-erasure phase. The remaining inverse
is erased at the original outer location. No new field or domain is assumed.

Source model only until the isolated native checker passes: -92 static T,
-91.993408203125 expected T, unchanged25-helper maximum for the combination.
The accepted C5 files and generator are never modified by this module.
"""
from dataclasses import dataclass

from monic_forney import flat, scale
from compact_inverse import compact_inverse_twelve
from projective_carry import erase_inverse_word, repay_inverse_mask
from tower_inverse import xor_product, phase_product, kernel, apply_inplace_linear
import night_outer as Outer
import projective_finish as Finish


@dataclass
class Record:
    builder_id: int
    outer: object
    finish: object
    D: tuple
    X: tuple
    closed: bool = False


def emit_prefix(builder, D, X, *, stage=lambda _: None):
    assert len(D) == 36 and len(X) == 35
    outer = Outer.emit_prefix(builder, D, X, fused=False, stage=stage)
    finish = Finish.emit_prefix(builder, D, X)
    stage('shared_seam_prefix_unchanged')
    return Record(id(builder), outer, finish, tuple(flat(D)), tuple(flat(X)))


def scalar_closing_keep_inverse(builder, source, value, old_value_mask):
    """Restore the scalar target and return its live unit reciprocal.

    Before returning, both target-dependent HMR masks are fully paid and
    freed. Only the reciprocal's future erasure remains; no HMR mask has
    yet been created for that reciprocal. Its source must remain unchanged
    until the caller transforms both source and inverse consistently.
    """
    reciprocal = compact_inverse_twelve(builder, source)
    temporary = builder.alloc_qubits(12)
    xor_product(builder, reciprocal, value, temporary)
    builder.swap(value, temporary)
    old_product_mask = builder.alloc_bits(12)
    builder.hmr(temporary, old_product_mask)
    builder.free(temporary)
    builder.cz(old_value_mask, value)
    builder.free(old_value_mask)
    phase_product(builder, source, value, old_product_mask, kernel(12))
    builder.free(old_product_mask)
    return reciprocal


def finish_closing_keep_inverse(builder, D, X, record):
    assert id(builder) == record.builder_id
    assert len(D) == 36 and len(X) == 35
    spec = Finish.geometry()
    apply_inplace_linear(builder, flat(X), spec['crt_rows'])
    # Every quadratic acts on a distinct X pair, and its source view
    # restores D. The scalar X34 return therefore commutes with all17.
    for i in reversed(range(17)):
        Finish.source_view(builder, D, i)
        Finish.Arithmetic.emit_closing(builder, flat(D[:2]), flat(X[2*i:2*i+2]),
                                       record.quadratic_records[i])
        Finish.source_view(builder, D, i, True)
    reciprocal = scalar_closing_keep_inverse(builder, D[35], X[34], record.scalar_record)
    apply_inplace_linear(builder, flat(X), spec['pre_inverse_rows'])
    return reciprocal


def outer_closing_with_inverse(builder, locator, numerator, record, reciprocal,
                               *, stage=lambda _: None):
    """Exact odd35/fused=False closing with an already-live inverse(D35).

    This is the corresponding branch of night_outer.emit_closing, with
    only its initial inverse construction replaced. No reciprocal survives
    the original erase point before the half-core return.
    """
    D, O, E, X = Outer._shape(locator, numerator, (), False)
    assert len(O) == record.degree == 35 and record.histories == 0
    assert not record.fused and record.values == X
    assert len(reciprocal) == 12
    assert not set(reciprocal).intersection(flat(D+O))
    context = record.core
    assert context.builder_id == id(builder)
    Outer._basis(builder, D+O, 2048)
    Outer._basis(builder, [reciprocal], 2048)
    A, B = D[::2], D[1::2]
    s = B[-1]
    # inv(D35)^(1/2) = inv(sqrt(D35)); repay the original prefix debt.
    repay_inverse_mask(builder, reciprocal, context.outer.pop('night_finish_inverse'))
    even, odd, H = O[::2][:-1], O[1::2], O[-1]
    q = A[-1]
    Outer._swap_halves(builder, even, odd)
    scale(builder, [H], s, reciprocal, False)
    for coefficient, value in zip(B[:-1], odd):
        xor_product(builder, coefficient, value, H)
    scale(builder, [q], s, reciprocal, True)
    erase_inverse_word(builder, s, reciprocal)
    for coefficient, target in zip(B[:-1], A[:-1]):
        xor_product(builder, q, coefficient, target)
    stage('shared_seam_undo_odd_full_preimage')
    Outer.core.emit(builder, B, A[:-1], [even, odd], False, context, True)
    for coefficient, target in zip(B[:-1], A[:-1]):
        xor_product(builder, q, coefficient, target)
    for coefficient, target in zip(B[:-1], even):
        xor_product(builder, H, coefficient, target)
    Outer.paired_scale.multiply_closing(builder, [H, q], s,
                                       context.outer.pop('night_odd_leading'))
    Outer._basis(builder, D+O, 2)
    assert not context.beta and not context.flags and not context.quotients and not context.outer
    stage('shared_seam_restored_raw_inputs')


def emit_closing(builder, D, X, record, *, stage=lambda _: None):
    assert id(builder) == record.builder_id and not record.closed
    assert tuple(flat(D)) == record.D and tuple(flat(X)) == record.X
    reciprocal = finish_closing_keep_inverse(builder, D, X, record.finish)
    stage('shared_seam_finish_return_live_inverse')
    outer_closing_with_inverse(builder, D, X, record.outer, reciprocal, stage=stage)
    record.closed = True
