# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Fixed additive-FFT implementation of the existing D/K root phase scan.

The basis changes, high-coefficient shears and butterflies are public
invertible linear maps. No coefficient, mask, mode or scratch is retained.
The original quadratic_phase_scan module remains the reference implementation.
"""
from functools import cache

from quantum_reciprocal import xor_linear
from tower_inverse import apply_inplace_linear, rows_from_columns
from scan10 import point_cell
from public_geometry import F, geometry, syndrome_gauge_plan, evaluate
from quadratic_phase_scan import mask_scale
import projective_finish as Finish


def polynomial_product(left, right):
    out = [0]*(len(left)+len(right)-1)
    for i, a in enumerate(left):
        for j, b in enumerate(right):
            out[i+j] ^= F.mul(a, b)
    return tuple(out)


@cache
def fft_geometry():
    """Normalized subspace polynomials and triangular degree0..35 basis."""
    subspace, phis, constants = (0, 1), [], []
    for k in range(6):
        constant = evaluate(subspace, 1 << k)
        assert constant
        inverse = F.invert(constant)
        phi = tuple(F.mul(x, inverse) for x in subspace)
        assert evaluate(phi, 1 << k) == 1
        phis.append(phi)
        constants.append(constant)
        nxt = [0]*(2*(len(subspace)-1)+1)
        for i, value in enumerate(subspace):
            nxt[2*i] ^= F.mul(value, value)
            nxt[i] ^= F.mul(constant, value)
        subspace = tuple(nxt)
    basis = [(1,)]
    for i in range(1, 36):
        k = i.bit_length()-1
        value = polynomial_product(basis[i ^ (1 << k)], phis[k])
        assert len(value) == i+1 and value[-1]
        basis.append(value)
    logs, point = [-1]*4096, 1
    for index in range(4095):
        assert point and logs[point] == -1
        logs[point] = index
        point = F.mul(point, F.primitive_element)
    assert point == 1 and all(value >= 0 for value in logs[1:])
    return dict(phi=tuple(phis), basis=tuple(basis), constants=tuple(constants),
                log=tuple(logs), cosets=tuple(range(0, 4096, 32)))


@cache
def multiplier_columns(scalar):
    return tuple(F.mul(scalar, 1 << bit) for bit in range(12))


@cache
def multiplier_rows(scalar):
    assert scalar
    return rows_from_columns(multiplier_columns(scalar))


def add_multiple(builder, source, target, scalar):
    if scalar == 1:
        builder.cx(source, target)
    elif scalar:
        xor_linear(builder, source, target, multiplier_columns(scalar))


def scale_word(builder, word, scalar):
    assert scalar
    if scalar != 1:
        # Quantum values require the ordinary multiplication map. The
        # inherited mask_scale intentionally uses its transpose instead.
        apply_inplace_linear(builder, word, multiplier_rows(scalar))


def emit_basis(builder, words, *, inverse=False):
    """Monomial coefficients <-> normalized novel coefficients, in place."""
    assert len(words) in (35, 36) and all(len(word) == 12 for word in words)
    basis = fft_geometry()['basis']
    indices = range(len(words)) if inverse else reversed(range(len(words)))
    for i in indices:
        if not inverse:
            scale_word(builder, words[i], F.invert(basis[i][-1]))
        for j, coefficient in enumerate(basis[i][:-1]):
            add_multiple(builder, words[i], words[j], coefficient)
        if inverse:
            scale_word(builder, words[i], basis[i][-1])


def emit_fft32(builder, words, coset, *, inverse=False):
    """Evaluate degree<32 in the novel basis at coset XOR range(32)."""
    assert len(words) == 32 and coset in range(0, 4096, 32)
    phis = fft_geometry()['phi']

    def recurse(view, k, offset):
        if k < 0:
            return
        size = 1 << k
        left, right = view[:size], view[size:]
        scalar = evaluate(phis[k], offset)
        if inverse:
            recurse(left, k-1, offset)
            recurse(right, k-1, offset ^ size)
        for a, b in zip(left, right):
            if inverse:
                builder.cx(a, b)
                add_multiple(builder, b, a, scalar)
            else:
                add_multiple(builder, b, a, scalar)
                builder.cx(a, b)
        if not inverse:
            recurse(left, k-1, offset)
            recurse(right, k-1, offset ^ size)

    recurse(words, 4, coset)


def emit_coset_view(builder, words, coset, *, inverse=False):
    """Novel coefficients ->32 values plus unchanged high novel words."""
    assert len(words) in (35, 36) and coset in range(0, 4096, 32)
    scalar = evaluate(fft_geometry()['phi'][5], coset)
    if inverse:
        emit_fft32(builder, words[:32], coset, inverse=True)
    for j in range(len(words)-32):
        add_multiple(builder, words[32+j], words[j], scalar)
    if not inverse:
        emit_fft32(builder, words[:32], coset)


def emit(builder, D, K, masks, *, start_index=0, positions=4095, stage=lambda _: None):
    """Same input/output/phase contract and extent API as the original scan."""
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
        stage(dict(stage='additive_fft_scan', cosets=used_cosets,
                   public_positions=covered, point_tests=active))
    assert covered == positions
    emit_basis(builder, K, inverse=True)
    emit_basis(builder, D, inverse=True)
    builder.free(ladder)
    return dict(physical_positions=positions, point_tests=active,
                full_cycle=start_index == 0 and positions == 4095,
                static_T=11*active, uniform_original_mask_mean_T=active*(11-1/4096),
                helpers=10, implementation='fixed_additive_fft32',
                additive_cosets=used_cosets, coefficient_basis='normalized_subspace_products')
