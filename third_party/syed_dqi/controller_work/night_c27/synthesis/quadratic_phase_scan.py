# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Fixed physical scan of the padded D and projective finish polynomial K.

The full cycle visits all4095 nonzero positions and omits only the70 public
positions whose logical original-weight gauge is zero. K(a) at physical
error roots equals e_a*a*U(a)*M(a); every phase mask is therefore scaled by
the transpose of multiplication by1/(a*U(a)*M(a)), then restored.
"""
from quantum_reciprocal import xor_linear
from tower_inverse import apply_inplace_linear
from scan10 import point_cell
from public_geometry import F, geometry, syndrome_gauge_plan, evaluate
import projective_finish as Finish


def mask_scale(builder, mask, scalar):
    assert scalar
    if scalar != 1:
        apply_inplace_linear(builder, mask, tuple(F.mul(scalar, 1 << j) for j in range(12)))


def emit(builder, D, K, masks, *, start_index=0, positions=4095, stage=lambda _: None):
    assert len(D) == 36 and len(K) == 35 and len(masks) == 4095
    assert 0 <= start_index < 4095 and 0 < positions <= 4095-start_index
    U, M = geometry()['U'], Finish.geometry()['M']
    selected = frozenset(syndrome_gauge_plan().selected)
    ladder = builder.alloc_qubits(10)
    previous = [1]+[0]*35

    def move(point):
        nonlocal previous
        powers = [1]
        for _ in range(35):
            powers.append(F.mul(powers[-1], point))
        for i in range(1, 36):
            multiplier = powers[i] ^ previous[i]
            if multiplier:
                columns = tuple(F.mul(multiplier, 1 << bit) for bit in range(12))
                xor_linear(builder, D[i], D[0], columns)
                if i < 35:
                    xor_linear(builder, K[i], K[0], columns)
        previous = powers

    point = F.pow(F.primitive_element, start_index)
    active = 0
    for index in range(start_index, start_index+positions):
        move(point)
        if point not in selected:
            factor = F.invert(F.mul(point, F.mul(evaluate(U, point), evaluate(M, point))))
            mask_scale(builder, masks[index], factor)
            point_cell(builder, D[0], K[0], masks[index], ladder)
            mask_scale(builder, masks[index], F.invert(factor))
            active += 1
        point = F.mul(point, F.primitive_element)
        if (index-start_index+1) % 256 == 0:
            stage(dict(stage='scan', public_positions=index-start_index+1, point_tests=active))
    assert point == F.pow(F.primitive_element, start_index+positions)
    move(0)
    builder.free(ladder)
    return dict(physical_positions=positions, point_tests=active,
                full_cycle=start_index == 0 and positions == 4095,
                static_T=11*active, uniform_original_mask_mean_T=active*(11-1/4096),
                helpers=10)
