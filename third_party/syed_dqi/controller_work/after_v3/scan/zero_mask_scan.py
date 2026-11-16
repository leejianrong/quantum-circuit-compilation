# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Exact classical-zero bypass for the accepted additive FFT phase scan.

Only a cell with an all-zero classical phase mask is skipped. The inherited
FFT and coefficient views are unchanged. Every nonzero mask runs the exact
accepted cell, including its HMR repayments and mask restoration.
"""
import additive_fft_phase_scan as Base
import projective_finish_infinity3 as Finish

F = Base.F
geometry = Base.geometry
syndrome_gauge_plan = Base.syndrome_gauge_plan
evaluate = Base.evaluate
mask_scale = Base.mask_scale
fft_geometry = Base.fft_geometry
emit_basis = Base.emit_basis
emit_coset_view = Base.emit_coset_view


def point_cell(builder, locator_value, value, mask, ladder):
    """T=11*[mask!=0], preserving the complete accepted cell contract."""
    assert len(locator_value) == len(value) == len(mask) == 12
    assert len(ladder) == 10
    active = builder.alloc_bits(1)
    builder.bit_store(active, False)
    builder.bit_store(active[0], True, control=mask)
    builder.push_condition(active[0])
    Base.point_cell(builder, locator_value, value, mask, ladder)
    builder.pop_condition()
    builder.bit_store(active, False)
    builder.free(active)


def emit(builder, D, K, masks, *, start_index=0, positions=4095,
         stage=lambda _: None):
    """Same extent, arbitrary-coefficient, phase and restoration contract."""
    assert len(D) == 36 and len(K) == 35 and len(masks) == 4095
    assert 0 <= start_index < 4095 and 0 < positions <= 4095-start_index
    spec = fft_geometry()
    U, M = geometry()['U'], Finish.geometry()['M']
    selected = frozenset(syndrome_gauge_plan().selected)
    stop = start_index+positions
    ladder = builder.alloc_qubits(10)
    emit_basis(builder, D)
    emit_basis(builder, K)
    active, covered, used_cosets = 0, 0, 0
    for coset in spec['cosets']:
        points = [(offset, coset ^ offset, spec['log'][coset ^ offset])
                  for offset in range(32)
                  if coset ^ offset and start_index <= spec['log'][coset ^ offset] < stop]
        if not points:
            continue
        used_cosets += 1
        emit_coset_view(builder, D, coset)
        emit_coset_view(builder, K, coset)
        for offset, point, index in points:
            covered += 1
            if point in selected:
                continue
            factor = F.invert(F.mul(point, F.mul(evaluate(U, point), evaluate(M, point))))
            mask_scale(builder, masks[index], factor)
            point_cell(builder, D[offset], K[offset], masks[index], ladder)
            mask_scale(builder, masks[index], F.invert(factor))
            active += 1
        emit_coset_view(builder, K, coset, inverse=True)
        emit_coset_view(builder, D, coset, inverse=True)
        stage(dict(stage='additive_fft_scan_zero_mask', cosets=used_cosets,
                   public_positions=covered, point_tests=active))
    assert covered == positions
    emit_basis(builder, K, inverse=True)
    emit_basis(builder, D, inverse=True)
    builder.free(ladder)
    return dict(physical_positions=positions, point_tests=active,
                full_cycle=start_index == 0 and positions == 4095,
                static_T=11*active,
                uniform_original_mask_mean_T=active*11*(1-1/4096),
                uniform_original_mask_saving_T=active*10/4096,
                helpers=10, classical_zero_mask_bypass=True,
                implementation='fixed_additive_fft32_zero_mask',
                additive_cosets=used_cosets,
                coefficient_basis='normalized_subspace_products',
                admitted_domain_change=False)
