# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Source-preserving65-T GF4096 reciprocal with22 extra qubits.

This is the supplied cubic-child reciprocal with one lifetime change:
erase the original6-bit norm after its inverse has been computed, before
allocating the12-bit reciprocal output. Its HMR phase is paid immediately
from the unchanged source. No arithmetic is omitted and zero still maps
to zero. The child peak is6+6+10=22; final reassembly needs6+12=18.
This source is separate from the immutable integrator implementation.
"""
from cubic_inverse130 import inverse_six_cubic
from tower_inverse import (quadratic_basis, apply_inplace_linear,
                           init_norm, erase_norm, xor_product)
from low_space_inverse import erase_norm_original_basis


def compact_inverse_twelve(builder, source, zero_flag=None):
    info = quadratic_basis(12)
    apply_inplace_linear(builder, source, info['to_tower'])
    left, right = source[:6], source[6:]
    norm = init_norm(builder, left, right, info['delta'])
    inverse_norm = inverse_six_cubic(builder, norm, zero_flag=zero_flag)
    erase_norm(builder, left, right, norm, info['delta'])
    builder.free(norm)
    target = builder.alloc_qubits(12)
    builder.cx(right, left)
    xor_product(builder, left, inverse_norm, target[:6])
    builder.cx(right, left)
    xor_product(builder, right, inverse_norm, target[6:])
    apply_inplace_linear(builder, target, info['from_tower'])
    erase_norm_original_basis(builder, target, inverse_norm)
    builder.free(inverse_norm)
    apply_inplace_linear(builder, source, info['from_tower'])
    return target
