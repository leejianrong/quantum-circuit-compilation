# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Separate optional classical-mask guard for the23-T parked phase seam.

The supplied mask is the caller's fresh12-bit HMR mask. A zero mask needs
no phase and leaves the parked gauge unchanged. The whole underlying helper,
including its gauge-mask merge, is inside the classical condition. StaticT
and width are unchanged; exact fresh-mask expectation saves23/4096 per call.
No prior candidate source is edited.
"""
import parked_scale_phase as Base


def record_uniform_hmr_event(name, conditional_t, mask_bits):
    """Optional source-expectation hook; no gates or samples are emitted."""
    return None


def repay_parked_scale(builder, carrier, target, mask, label=''):
    assert len(mask) == 12
    active = builder.alloc_bits(1)
    builder.bit_store(active, False)
    builder.bit_store(active[0], True, control=mask)
    builder.push_condition(active[0])
    # In the skipped branch neither the gauge HMR nor the mask XOR executes.
    # Base owns/frees the12-bit input mask; active remains live until pop.
    Base.repay_parked_scale(builder, carrier, target, mask, label)
    builder.pop_condition()
    builder.free(active)
    record_uniform_hmr_event('parked_scale_fresh_mask_guard', 23, 12)
