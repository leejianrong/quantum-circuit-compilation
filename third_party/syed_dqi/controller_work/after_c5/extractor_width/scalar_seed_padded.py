# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""177-T closing of the C5 scalar seed while its tail flag remains erased.

Entry is the padded seed boundary.  If f=0: N0=lambda, D0=lambda*P0,
Dx=lambda*P1.  If f=1: N0=0,D0=0,Dx=lambda and P0=P1=0.  lambda is a
unit in both branches.  The existing tail seed mask still owns f's phase.

close_padded leaves N0 unchanged, divides both D words by N0 when N0 is
nonzero and leaves them unchanged otherwise.  Then call tail.seed_return
to query f and exchange N0/Dx, followed by finish_after_swap to repay all
new and old scalar masks.  No flag is retained across the 24-helper peak.
"""
from dataclasses import dataclass
import ew_paths  # noqa: F401
import kickmix as km
import scalar_seed as Base
from compact_inverse22 import compact_inverse_twelve
from tower_inverse import xor_product, phase_product, kernel
from phase_inverse12 import phase_inverse_twelve_polynomial

emit_prefix = Base.emit_prefix
node_coefficients_inplace = Base.node_coefficients_inplace


@dataclass
class ReturnRecord:
    builder_id: int
    source: tuple
    targets: tuple
    seed: object
    product_masks: tuple
    zero_mask: object
    inverse_mask: object
    closed: bool = False


def close_padded(builder, numerator_constant, head, seed):
    """177 static T,24 helpers; leave only classical debts for f/old P."""
    assert not seed.closed and seed.builder_id == id(builder)
    assert tuple(numerator_constant) == seed.source and tuple(head) == seed.targets
    z = builder.alloc_qubits(1)
    inverse = compact_inverse_twelve(builder, numerator_constant, zero_flag=z[0])
    # inv0(x)+[x=0] is a unit for EVERY x, including the even-tail branch.
    builder.cx(z[0], inverse[0])
    zero_mask = builder.alloc_bits(1)
    builder.hmr(z, zero_mask)
    builder.free(z)
    temporary = builder.alloc_qubits(12)
    product_masks = []
    for target in (head[:12], head[12:]):
        xor_product(builder, inverse, target, temporary)
        builder.swap(target, temporary)
        mask = builder.alloc_bits(12)
        builder.hmr(temporary, mask)
        product_masks.append(mask)
    builder.free(temporary)
    inverse_mask = builder.alloc_bits(12)
    builder.hmr(inverse, inverse_mask)
    builder.free(inverse)
    phase_inverse_twelve_polynomial(builder, numerator_constant, inverse_mask)
    # Residual phase is (zero_mask[0] XOR inverse_mask[0])*f.
    return ReturnRecord(id(builder), tuple(numerator_constant), tuple(head),
                        seed, tuple(product_masks), zero_mask, inverse_mask)


def finish_after_swap(builder, scale, head, flag, record):
    """0 T after tail.seed_return restored lambda,P and produced real f."""
    assert not record.closed and record.builder_id == id(builder)
    assert tuple(scale) == record.source and tuple(head) == record.targets
    builder.cz(record.zero_mask[0], flag)
    builder.cz(record.inverse_mask[0], flag)
    builder.free(record.zero_mask)
    builder.free(record.inverse_mask)
    for i, (target, old_product, old_input) in enumerate(zip(
            (head[:12], head[12:]), record.product_masks, record.seed.old_masks)):
        phase_product(builder, scale, target, old_product, kernel(12))
        if i == 1:
            # Old padded Dx = lambda*P1 + f*lambda, since f=1 => P1=0.
            for q, classical in zip(scale, old_product):
                builder.ccz(classical, flag, q)
        builder.free(old_product)
        builder.cz(old_input, target)
        builder.free(old_input)
    record.seed.closed = True
    record.closed = True


def source_ledger():
    return dict(status='SOURCE_MODEL_NOT_YET_NATIVE_CHECKED', prefix_T=84,
                closing_T=177, pair_T=261, delta_C5_T=1, helpers=24,
                inverse_with_zero_query_T=66, products_T=84,
                inverse_phase_T=27, remaining_debt_repayment_T=0,
                gauge_and_seed_controller_not_included=True)
