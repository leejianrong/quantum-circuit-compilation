# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""Fresh quadratic-tower inverse kernels with measurement cleanup.

Degree 24 uses pairs of official GF(2^12) words, with theta^2+theta=delta.
It is not claimed to be Kickmix's default degree-24 polynomial basis.
"""
from __future__ import annotations

from functools import cache
import hashlib
import io
import json
from pathlib import Path
import sys

import kickmix as km
import numpy as np

from field_tensor import (apply_linear, invert_binary_columns, invert_field_matrix, multiplication_tensor,
                          parity_pivot, symmetric_tensor, accumulate_product, tensor_value)
from quantum_reciprocal import bit_matrix, xor_linear, xor_same_source_product


def rows_from_columns(columns):
    return tuple(sum(((column >> bit) & 1) << j for j, column in enumerate(columns))
                 for bit in range(len(columns)))


def apply_inplace_linear(builder, register, rows):
    work = list(rows)
    operations = []
    for col in range(len(rows)):
        pivot = next(i for i in range(col, len(rows)) if work[i] >> col & 1)
        if pivot != col:
            work[col], work[pivot] = work[pivot], work[col]
            operations.append(('swap', col, pivot))
        for i in range(len(rows)):
            if i != col and work[i] >> col & 1:
                work[i] ^= work[col]
                operations.append(('cx', col, i))
    assert work == [1 << i for i in range(len(rows))]
    for operation, i, j in reversed(operations):
        getattr(builder, operation)(register[i], register[j])


@cache
def quadratic_basis(degree):
    half = degree // 2
    base = km.GF2Field(half)
    if degree == 24:
        delta = next(x for x in range(1, 4096)
                     if sum_trace(x, base) == 1)
        identity = tuple(1 << bit for bit in range(degree))
        return dict(degree=degree, half=half, delta=delta,
                    to_tower=identity, from_tower=identity)
    field = km.GF2Field(degree)

    def evaluate_modulus(x):
        value = 0
        for bit in range(half + 1):
            if base.modulus >> bit & 1:
                value ^= field.pow(x, bit)
        return value

    beta = next(x for x in range(2, 1 << degree) if evaluate_modulus(x) == 0)
    subcolumns = [field.pow(beta, i) for i in range(half)]
    theta = next(x for x in range(2, 1 << degree)
                 if field.pow(x, 1 << half) ^ x == 1)
    columns = subcolumns + [field.mul(theta, x) for x in subcolumns]
    to_tower = invert_binary_columns(columns)
    delta = apply_linear(to_tower, field.mul(theta, theta) ^ theta)
    assert delta < 1 << half and sum_trace(delta, base) == 1
    return dict(degree=degree, half=half, delta=delta,
                to_tower=to_tower, from_tower=rows_from_columns(columns))


def sum_trace(x, field):
    result = 0
    for _ in range(field.degree):
        result ^= x
        x = field.mul(x, x)
    return result


@cache
def kernel(degree):
    if degree == 12:
        return multiplication_tensor()
    if degree == 3:
        return symmetric_tensor(3, km.GF2Field(3))
    assert degree == 6
    # A quadratic polynomial over GF(4) is determined by the four finite
    # evaluation points plus infinity. Its degree-four product therefore
    # uses five GF(4) products, each of binary rank three: total rank 15.
    field, base = km.GF2Field(6), km.GF2Field(2)
    beta = next(x for x in range(2, 64) if field.mul(x, x) ^ x ^ 1 == 0)
    def embed(x):
        return (x & 1) ^ (beta if x >> 1 else 0)
    for theta in range(2, 64):
        columns = [field.mul(field.pow(theta, i), embed(1 << bit))
                   for i in range(3) for bit in range(2)]
        try:
            to_tower = invert_binary_columns(columns)
            break
        except ValueError:
            continue
    else:
        raise AssertionError('No cubic-over-GF(4) basis')
    evaluation = [[base.pow(x, k) for k in range(5)] for x in range(4)]
    evaluation.append([0, 0, 0, 0, 1])
    interpolation = invert_field_matrix(evaluation, base)
    terms = []
    for point in range(5):
        evaluated_rows = [0, 0]
        for bit in range(6):
            value = apply_linear(to_tower, 1 << bit)
            if point == 4:
                evaluated = value >> 4
            else:
                evaluated = 0
                for i in range(3):
                    evaluated ^= base.mul((value >> (2 * i)) & 3, base.pow(point, i))
            for out in range(2):
                evaluated_rows[out] |= ((evaluated >> out) & 1) << bit
        def compose(mask):
            return (evaluated_rows[0] if mask & 1 else 0) ^ (evaluated_rows[1] if mask & 2 else 0)
        weight = 0
        for k in range(5):
            weight ^= field.mul(embed(interpolation[k][point]), field.pow(theta, k))
        for left, right, output in symmetric_tensor(2, base):
            terms.append((compose(left), compose(right), field.mul(weight, embed(output))))
    assert len(terms) == 15
    return tuple(terms)


def xor_product(builder, left, right, target):
    accumulate_product(builder, left, right, target, kernel(len(target)))


def phase_linear(builder, source, measured, columns):
    for bit, column in enumerate(columns):
        for out in range(len(measured)):
            if column >> out & 1:
                builder.cz(measured[out], source[bit])


def phase_product(builder, left, right, measured, terms):
    for a, b, output in terms:
        first = parity_pivot(builder, left, a)
        second = parity_pivot(builder, right, b)
        for bit in range(len(measured)):
            if output >> bit & 1:
                builder.ccz(measured[bit], first, second)
        parity_pivot(builder, right, b)
        parity_pivot(builder, left, a)


def erase_product(builder, left, right, target):
    measured = builder.alloc_bits(len(target))
    builder.hmr(target, measured)
    phase_product(builder, left, right, measured, kernel(len(target)))
    builder.free(measured)


@cache
def norm_columns(half, delta):
    field = km.GF2Field(half)
    return (tuple(field.mul(1 << bit, 1 << bit) for bit in range(half)),
            tuple(field.mul(delta, field.mul(1 << bit, 1 << bit)) for bit in range(half)))


def init_norm(builder, left, right, delta):
    target = builder.alloc_qubits(len(left))
    a_columns, b_columns = norm_columns(len(left), delta)
    xor_product(builder, left, right, target)
    xor_linear(builder, left, target, a_columns)
    xor_linear(builder, right, target, b_columns)
    return target


def erase_norm(builder, left, right, target, delta):
    measured = builder.alloc_bits(len(target))
    builder.hmr(target, measured)
    a_columns, b_columns = norm_columns(len(left), delta)
    phase_linear(builder, left, measured, a_columns)
    phase_linear(builder, right, measured, b_columns)
    phase_product(builder, left, right, measured, kernel(len(target)))
    builder.free(measured)


@cache
def inverse_three_anf():
    field = km.GF2Field(3)
    coefficients = [field.invert(x) if x else 0 for x in range(8)]
    for bit in range(3):
        for mask in range(8):
            if mask >> bit & 1:
                coefficients[mask] ^= coefficients[mask ^ (1 << bit)]
    assert coefficients[0] == coefficients[7] == 0
    return tuple((mask, value) for mask, value in enumerate(coefficients) if value)


def init_inverse_three(builder, source, target):
    for mask, output in inverse_three_anf():
        indices = [i for i in range(3) if mask >> i & 1]
        if len(indices) == 1:
            xor_linear(builder, source, target,
                       tuple(output if i == indices[0] else 0 for i in range(3)))
        else:
            xor_same_source_product(builder, source, target,
                                    ((1 << indices[0], 1 << indices[1], output),))


def erase_inverse_three(builder, source, target):
    measured = builder.alloc_bits(3)
    builder.hmr(target, measured)
    for mask, output in inverse_three_anf():
        indices = [i for i in range(3) if mask >> i & 1]
        for bit in range(3):
            if output >> bit & 1:
                if len(indices) == 1:
                    builder.cz(measured[bit], source[indices[0]])
                else:
                    builder.ccz(measured[bit], source[indices[0]], source[indices[1]])
    builder.free(measured)


def init_inverse(builder, source, target):
    degree = len(source)
    if degree == 3:
        init_inverse_three(builder, source, target)
        return None
    info = quadratic_basis(degree)
    half = degree // 2
    apply_inplace_linear(builder, source, info['to_tower'])
    left, right = source[:half], source[half:]
    norm = init_norm(builder, left, right, info['delta'])
    inverse_norm = builder.alloc_qubits(half)
    child = init_inverse(builder, norm, inverse_norm)
    builder.cx(right, left)
    xor_product(builder, left, inverse_norm, target[:half])
    builder.cx(right, left)
    xor_product(builder, right, inverse_norm, target[half:])
    apply_inplace_linear(builder, source, info['from_tower'])
    apply_inplace_linear(builder, target, info['from_tower'])
    return dict(norm=norm, inverse_norm=inverse_norm, child=child)


def erase_inverse(builder, source, target, scaffold):
    degree = len(source)
    if degree == 3:
        erase_inverse_three(builder, source, target)
        return
    info = quadratic_basis(degree)
    half = degree // 2
    apply_inplace_linear(builder, source, info['to_tower'])
    apply_inplace_linear(builder, target, info['to_tower'])
    left, right = source[:half], source[half:]
    norm, inverse_norm = scaffold['norm'], scaffold['inverse_norm']
    builder.cx(right, left)
    erase_product(builder, left, inverse_norm, target[:half])
    builder.cx(right, left)
    erase_product(builder, right, inverse_norm, target[half:])
    erase_inverse(builder, norm, inverse_norm, scaffold['child'])
    builder.free(inverse_norm)
    erase_norm(builder, left, right, norm, info['delta'])
    builder.free(norm)
    apply_inplace_linear(builder, source, info['from_tower'])


def mirrored(scaffold):
    if scaffold is None:
        return None
    return dict(norm=scaffold['inverse_norm'], inverse_norm=scaffold['norm'],
                child=mirrored(scaffold['child']))


def invert_inplace(builder, source, zero_flag=None):
    """Invert a field word, including zero, with all workspace returned to zero."""
    degree = len(source)
    info = quadratic_basis(degree)
    half = degree // 2
    apply_inplace_linear(builder, source, info['to_tower'])
    left, right = source[:half], source[half:]
    norm = init_norm(builder, left, right, info['delta'])
    inverse_norm = builder.alloc_qubits(half)
    child = init_inverse(builder, norm, inverse_norm)
    if zero_flag is not None:
        # Each irreducible quadratic norm vanishes exactly at zero. The
        # already-live GF(8) norm therefore supplies a two-T zero flag.
        value, leaf = norm, child
        while leaf is not None:
            value, leaf = leaf['norm'], leaf['child']
        assert len(value) == 3
        builder.x(value)
        flag_work = builder.alloc_qubits(1)
        builder.init_and(value[0], value[1], flag_work[0])
        builder.ccx(flag_work[0], value[2], zero_flag)
        builder.del_and(value[0], value[1], flag_work[0])
        builder.free(flag_work)
        builder.x(value)
    trimmed = None
    if degree == 24:
        # Remove one 3-bit leaf before the 12-bit multiplication workspace
        # becomes live. Recompute its quadratic inverse after that workspace
        # is free: +3 T, -3 peak qubits.
        trimmed = child['child']
        assert len(trimmed['norm']) == len(trimmed['inverse_norm']) == 3
        erase_inverse_three(builder, trimmed['norm'], trimmed['inverse_norm'])
        builder.free(trimmed['inverse_norm'])
        trimmed['inverse_norm'] = None
    temporary = builder.alloc_qubits(half)
    for word in (left, right):
        xor_product(builder, word, inverse_norm, temporary)
        builder.swap(word, temporary)
        # The zero norm case has a=b=0, so this identity also covers zero.
        erase_product(builder, word, norm, temporary)
    builder.free(temporary)
    builder.cx(right, left)
    if trimmed is not None:
        trimmed['inverse_norm'] = builder.alloc_qubits(3)
        init_inverse_three(builder, trimmed['norm'], trimmed['inverse_norm'])
    # At every level, norm(x^-1)=norm(x)^-1. The retained scaffold is
    # therefore exactly the inverse scaffold with its two branches swapped.
    erase_inverse(builder, inverse_norm, norm, mirrored(child))
    builder.free(norm)
    erase_norm(builder, left, right, inverse_norm, info['delta'])
    builder.free(inverse_norm)
    apply_inplace_linear(builder, source, info['from_tower'])


def extension_inverse(value):
    field = km.GF2Field(12)
    delta = quadratic_basis(24)['delta']
    a, b = value & 4095, value >> 12
    norm = field.mul(a, a) ^ field.mul(a, b) ^ field.mul(delta, field.mul(b, b))
    ni = field.invert(norm) if norm else 0
    return field.mul(a ^ b, ni) | (field.mul(b, ni) << 12)


def build(degree, inplace=True):
    builder = km.CircuitBuilder()
    source = builder.create_quantum_register(degree, 'value')
    if inplace:
        invert_inplace(builder, source)
    else:
        target = builder.alloc_qubits(degree)
        mask = builder.create_classical_register(degree, 'mask')
        scaffold = init_inverse(builder, source, target)
        builder.cz(mask, target)
        erase_inverse(builder, source, target, scaffold)
    return builder.finish_circuit(), source


def run_checks(destination=None):
    rng = np.random.default_rng(2026110803)
    report = dict(status='PASS_component_only', failures=0, base_exhaustive_inputs=4096,
                  field24_representation='a+b*theta over official GF(2^12); theta^2+theta=delta',
                  delta24=quadratic_basis(24)['delta'])
    for degree in (3, 6, 12):
        field = km.GF2Field(degree)
        for i in range(degree):
            for j in range(degree):
                assert tensor_value(kernel(degree), 1 << i, 1 << j) == field.mul(1 << i, 1 << j)
    for degree, inplace in ((6, True), (12, True), (12, False), (24, True)):
        if degree <= 12:
            values = np.arange(1 << degree, dtype=np.int64)
            field = km.GF2Field(degree)
            inverses = np.array([field.invert(int(x)) if x else 0 for x in values])
        else:
            values = rng.integers(0, 1 << 24, size=8192, dtype=np.int64)
            values[:4096] = np.arange(4096)
            values[4096:4120] = 1 << np.arange(24)
            inverses = np.array([extension_inverse(int(x)) for x in values])
        shots = len(values)
        masks = rng.integers(0, 1 << degree, size=shots, dtype=np.int64)
        circuit, source = build(degree, inplace)
        payload = io.BytesIO()
        circuit.to_file(payload, format='kmb')
        repeated = io.BytesIO()
        build(degree, inplace)[0].to_file(repeated, format='kmb')
        assert payload.getvalue() == repeated.getvalue()
        scratch = [km.q(i) for i in range(circuit.num_qubits) if km.q(i) not in source]
        for seed in range(4):
            sim = km.Simulator(batch_size=shots, seed=seed)
            sim.use_same_registers_as(circuit)
            sim.write_across_shots(source, bit_matrix(values, degree))
            expected = inverses if inplace else values
            if not inplace:
                sim.write_across_shots(circuit.register_data['mask'], bit_matrix(masks, degree))
            sim.do(circuit)
            assert np.array_equal(sim.read_across_shots(source), bit_matrix(expected, degree))
            assert not sim.read_across_shots(scratch).any()
            expected_phase = (np.zeros(shots, dtype=bool) if inplace else
                              np.array([int(x & m).bit_count() & 1 for x, m in zip(inverses, masks)], dtype=bool))
            assert np.array_equal(sim.read_phase_flipped_across_shots(), expected_phase)
            if inplace:
                sim.do(circuit)
                assert np.array_equal(sim.read_across_shots(source), bit_matrix(values, degree))
                assert not sim.read_across_shots(scratch).any()
                assert not sim.read_phase_flipped_across_shots().any()
        entry = dict(T=circuit.operation_statistics().num_toffoli_like, Q=circuit.num_qubits,
                     scratch_qubits=circuit.num_qubits-degree, operations=len(circuit),
                     shots_per_seed=shots, seeds=4, byte_identical_fresh_builds=True,
                     sha256=hashlib.sha256(payload.getvalue()).hexdigest())
        report[f'{"inplace" if inplace else "outplace_phase_erase"}_{degree}'] = entry
        if destination:
            path = destination.parent.parent / 'circuits' / f'inverse-{degree}-{inplace}.kmb'
            path.write_bytes(payload.getvalue())
    if destination:
        destination.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    print(json.dumps(run_checks(Path(sys.argv[1]) if len(sys.argv) > 1 else None), indent=2))
