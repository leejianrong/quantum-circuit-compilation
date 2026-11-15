# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Separate optional all-zero target-mask bypass for the phase84 sibling.

The frozen unguarded emitter is unchanged. No extra quantum workspace is
used. The existing thirty-leaf event plus the new fifty-four-T event account
for the single full eighty-four-T bypass; they must never be counted twice.
"""
import quotient_phase84 as Unguarded
import kickmix as km

Base = Unguarded.Base
Original = Unguarded.Original
Nested = Unguarded.Nested
Arithmetic = Unguarded.Arithmetic
target_mask_rows = Unguarded.target_mask_rows
_rank = Unguarded._rank


def phase_quotients12(builder, source, targets):
    targets = tuple(targets)
    assert len(source) == 12 and targets
    assert all(len(value) == len(mask) == 12 for value, mask, _ in targets)
    masks = km.array([bit for _, mask, _ in targets for bit in mask])
    assert all(isinstance(bit, km.b) for bit in masks)
    active = builder.alloc_bits(1)
    builder.bit_store(active, False)
    builder.bit_store(active[0], True, control=masks)
    builder.push_condition(active[0])
    Unguarded.phase_quotients12(builder, source, targets)
    builder.pop_condition()
    builder.bit_store(active, False)
    builder.free(active)
    # Unguarded already records30 under this identical zero-mask predicate.
    # This additional54 gives84 total, not114. Independence between the
    # two events is unnecessary; expectation is additive even when equal.
    Original.record_uniform_hmr_event('retained_child_outer_zero_guard_extra',
                                     54, 12*len(targets))


def inverse_closed(builder, source, delta=Arithmetic.DEFAULT_DELTA):
    """Same closed inv0 value/phase contract; only its phase helper differs."""
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
    bits = 12*targets
    return dict(status='SOURCE_MODEL_NOT_NATIVE_RESULT',
                phase_static_T=84, phase_helpers=12,
                exact_count='84*[any target mask is nonzero]',
                phase_uniform_target_mask_mean_T=84-84/(1 << bits),
                closed_inverse_static_T=276, inverse_helpers=24,
                actual_two_target_inverse_mean_T=276-84/(1 << 24),
                actual_v3_closed_inverse_calls=3,
                whole_static_saving_vs_phase85=3,
                whole_mean_saving_vs_phase85=3*(1-4/64+84/(1 << 24)),
                extra_mean_saving_over_unguarded_phase84=162/(1 << 24),
                event_total='30/2^bits + 54/2^bits = 84/2^bits',
                extra_quantum_qubits=0, admitted_domain_change=False,
                supersedes_not_additive_with_final_norm_guard=True,
                event_scope='Actual inverse uses two fresh12-bit HMR masks; generic masks need their own law.')
