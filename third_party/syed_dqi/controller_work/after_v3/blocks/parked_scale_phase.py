# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Pay one scale mask directly on an existing sparse parked gauge anchor.

The anchor r_p and other word mu_p encode a unit r and sparse gauge g by
r=r_p+g*mu_p, with g=zero(r_p). The lender's gauge wire is presently clean;
its old HMR mask is still owned by the carrier. This helper changes no field
value, does not move the anchor, and merges its one new gauge mask into that
existing mask. It consumes only the supplied target's12-bit classical mask.

Source count23 T: one11-T zero query plus12 controlled bilinear phase terms.
There is no fresh quantum field: the conditional-zero anchor itself holds
the transposed mask product temporarily. Only the query's ten ladder bits
are additional helpers. No accepted source is modified.
"""
import kickmix as km
from coherent_border import toggle_zero
from field_tensor import accumulate_product
from tower_inverse import kernel, phase_product


def repay_parked_scale(builder, carrier, target, mask, label=''):
    assert builder is carrier.b and carrier.anchor is not None
    assert carrier.mask is not None and builder.idle and builder.enabled
    anchor, other, flag = carrier.anchor, carrier.other, carrier.flag
    assert len(target) == len(anchor) == len(other) == len(mask) == 12
    quantum = [*target, *anchor, *other, flag]
    assert all(isinstance(q, km.q) for q in quantum)
    assert len(set(quantum)) == len(quantum)
    assert all(isinstance(bit, km.b) for bit in mask)
    assert len(carrier.mask) == 1 and not set(mask) & set(carrier.mask)
    terms = kernel(12)
    transposed = tuple((a, output, b) for a, b, output in terms)

    # The owned gauge wire must not be lent into its own query ladder.
    with builder.no_loan():
        toggle_zero(builder, anchor, flag)
        # Pay the ordinary r_p part while the original anchor is untouched.
        phase_product(builder, target, anchor, mask, terms)
        # t_k=dot(mask,target*e_k). The second input is classical, so this
        # bilinear accumulation is Clifford. It is safe on the dirty anchor:
        # g*anchor_old=0, hence g*anchor_new=g*t at the next diagonal gate.
        accumulate_product(builder, target, mask, anchor, transposed)
        for bit in range(12):
            builder.ccz(flag, anchor[bit], other[bit])
        accumulate_product(builder, target, mask, anchor, transposed)
        new_mask = builder.alloc_bits(1)
        builder.hmr(km.array([flag]), new_mask)
        builder.cx(new_mask, carrier.mask)
        builder.free(new_mask)
    builder.free(mask)
    assert carrier.anchor is anchor and carrier.mask is not None
    assert builder.idle and builder.enabled
    carrier.parked_phase_payments = getattr(carrier, 'parked_phase_payments', 0)+1
    carrier.events.append(('pay_parked_scale', label))
