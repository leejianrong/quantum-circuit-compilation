# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Zero-safe variable-numerator GF4096 trace phase with a 62-T source model.

The two original field words are arbitrary quantum data. A joint dual-number
product computes their norm and relative-trace numerator, and an existing
GF64 quotient phase completes the absolute trace. Both computed words are
measured and their exact bilinear/linear phase debts are repaid locally.
"""
from __future__ import annotations

import kickmix as km
from dual64_tensor import multiplication_tensor, trace, BASE_MODULUS
from field_tensor import accumulate_product
from quantum_reciprocal import xor_linear
from tower_inverse import (quadratic_basis, apply_inplace_linear,
                           norm_columns, phase_product, phase_linear)
from cubic_trace_quotient20 import phase_trace_quotient_six


STATIC_T = 62
HELPERS = 22


def phase_inverse_trace_twelve(builder, denominator, numerator):
    """Apply the absolute trace of numerator times inv0(denominator).

All inputs are preserved, every quantum helper returns to zero, and all
measurement masks are paid before being freed. The zero denominator branch
has norm and relative-trace numerator both zero for every numerator.
"""
    assert len(denominator) == len(numerator) == 12
    if (len(set(denominator)) != 12 or len(set(numerator)) != 12
            or set(denominator) & set(numerator)):
        raise ValueError('quotient phase requires disjoint quantum words')
    if not all(isinstance(wire, km.q) for wire in [*denominator, *numerator]):
        raise TypeError('quotient phase requires two quantum source words')
    assert km.GF2Field(6).modulus == BASE_MODULUS
    before = builder.num_allocated_qubits
    info = quadratic_basis(12)
    apply_inplace_linear(builder, denominator, info['to_tower'])
    apply_inplace_linear(builder, numerator, info['to_tower'])
    a, b = denominator[:6], denominator[6:]
    u, v = numerator[:6], numerator[6:]
    left, right = km.array([*a, *u]), km.array([*b, *v])
    work = builder.alloc_qubits(12)
    norm, relative = work[:6], work[6:]
    terms = multiplication_tensor()
    accumulate_product(builder, left, right, work, terms)
    square_a, square_b = norm_columns(6, info['delta'])
    xor_linear(builder, a, norm, square_a)
    xor_linear(builder, b, norm, square_b)
    phase_trace_quotient_six(builder, norm, relative)
    measured = builder.alloc_bits(12)
    builder.hmr(work, measured)
    builder.free(work)
    phase_product(builder, left, right, measured, terms)
    phase_linear(builder, a, measured[:6], square_a)
    phase_linear(builder, b, measured[:6], square_b)
    builder.free(measured)
    apply_inplace_linear(builder, numerator, info['from_tower'])
    apply_inplace_linear(builder, denominator, info['from_tower'])
    assert builder.num_allocated_qubits == before
