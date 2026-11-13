# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""Small, clean-room quantum prototype of the one-array series reciprocal.

This is a component witness, not a DQI decoder or an economical full-size
schedule. All input coefficients are arbitrary quantum words. The constant
coefficient is the classical value one and occupies no register.
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

from field_tensor import accumulate_product, multiplication_tensor, parity_pivot, symmetric_tensor


@cache
def frobenius_columns(degree, exponent):
    field = km.GF2Field(degree)
    return tuple(field.pow(1 << bit, exponent) for bit in range(degree))


def compose_mask(mask, columns):
    return sum(((mask & column).bit_count() & 1) << bit
               for bit, column in enumerate(columns))


def xor_linear(builder, source, target, columns):
    assert not set(source) & set(target)
    for bit, column in enumerate(columns):
        for out in range(len(target)):
            if column >> out & 1:
                builder.cx(source[bit], target[out])


def xor_same_source_product(builder, source, target, terms):
    """Emit quadratic terms with two linear forms of ONE input register.

    Equal forms are linear in characteristic two. Distinct forms can be
    exposed as two different pivots by reversible changes of basis. The
    second form is transformed into the first pivot's coordinate system.
    """
    assert not set(source) & set(target)
    for a, b, output in terms:
        if a == b:
            for bit in range(len(source)):
                if a >> bit & 1:
                    for out in range(len(target)):
                        if output >> out & 1:
                            builder.cx(source[bit], target[out])
            continue
        first_index = (a & -a).bit_length() - 1
        first = parity_pivot(builder, source, a)
        transformed_b = b ^ ((a ^ (1 << first_index)) if b >> first_index & 1 else 0)
        candidates = transformed_b & ~(1 << first_index)
        assert candidates
        second_index = (candidates & -candidates).bit_length() - 1
        second = source[second_index]
        controls = [wire for bit, wire in enumerate(source)
                    if bit != second_index and transformed_b >> bit & 1]
        for wire in controls:
            builder.cx(wire, second)
        output_index = (output & -output).bit_length() - 1
        fanout = [wire for bit, wire in enumerate(target)
                  if bit != output_index and output >> bit & 1]
        for wire in fanout:
            builder.cx(target[output_index], wire)
        builder.ccx(first, second, target[output_index])
        for wire in reversed(fanout):
            builder.cx(target[output_index], wire)
        for wire in reversed(controls):
            builder.cx(wire, second)
        parity_pivot(builder, source, a)


def xor_frobenius_product(builder, left, right, target, degree, exponent):
    base_terms = multiplication_tensor() if degree == 12 else symmetric_tensor(degree, km.GF2Field(degree))
    columns = frobenius_columns(degree, exponent)
    terms = tuple((a, compose_mask(b, columns), output) for a, b, output in base_terms)
    if tuple(left) == tuple(right):
        xor_same_source_product(builder, left, target, terms)
    else:
        accumulate_product(builder, left, right, target, terms)


def emit_unit_reciprocal(builder, words, degree):
    """Overwrite coefficients 1..n-1 with those of the reciprocal."""
    length = len(words) + 1
    stage = 0
    counts = {'distinct_source_products': 0, 'same_source_products': 0,
              'linear_frobenius_adds': 0}
    while (1 << (1 << stage)) < length:
        stride = 1 << (1 << stage)
        for k in range(length - 1, 0, -1):
            if k % stride == 0:
                xor_linear(builder, words[k // stride - 1], words[k - 1],
                           frobenius_columns(degree, stride))
                counts['linear_frobenius_adds'] += 1
            for j in range(1, (k - 1) // stride + 1):
                i = k - stride * j
                xor_frobenius_product(builder, words[i - 1], words[j - 1],
                                      words[k - 1], degree, stride)
                counts['same_source_products' if i == j else 'distinct_source_products'] += 1
        stage += 1
    return counts


def build_unit_reciprocal(degree, length, twice=False):
    builder = km.CircuitBuilder()
    words = [builder.create_quantum_register(degree, f'c{i}') for i in range(1, length)]
    counts = emit_unit_reciprocal(builder, words, degree)
    if twice:
        emit_unit_reciprocal(builder, words, degree)
    return builder.finish_circuit(), words, counts


def reference_inverse(coefficients, field):
    result = [1]
    for k in range(1, len(coefficients)):
        value = 0
        for j in range(1, k + 1):
            value ^= field.mul(coefficients[j], result[k - j])
        result.append(value)
    return result


def bit_matrix(values, degree):
    return ((np.asarray(values, dtype=np.int64)[:, None] >> np.arange(degree)) & 1).T.astype(bool)


def serialized(circuit):
    stream = io.BytesIO()
    circuit.to_file(stream, format='kmb')
    return stream.getvalue()


def run_checks(destination=None):
    rng = np.random.default_rng(2026110802)
    report = dict(status='PASS_component_only', value_failures=0, phase_failures=0,
                  restoration_failures=0, byte_identical_fresh_builds=True,
                  same_source_exhaustive_inputs=4096, same_source=[], series=[])
    field = km.GF2Field(12)
    left_values = np.arange(4096, dtype=np.int64)
    targets = rng.integers(0, 4096, size=4096, dtype=np.int64)
    for exponent in (2, 4, 16):
        builder = km.CircuitBuilder()
        source = builder.create_quantum_register(12, 'source')
        target = builder.create_quantum_register(12, 'target')
        xor_frobenius_product(builder, source, source, target, 12, exponent)
        circuit = builder.finish_circuit()
        expected = targets ^ np.array([field.mul(int(x), field.pow(int(x), exponent)) for x in left_values])
        sim = km.Simulator(batch_size=4096, seed=20261108)
        sim.use_same_registers_as(circuit)
        sim.write_across_shots(source, bit_matrix(left_values, 12))
        sim.write_across_shots(target, bit_matrix(targets, 12))
        sim.do(circuit)
        assert np.array_equal(sim.read_across_shots(source), bit_matrix(left_values, 12))
        assert np.array_equal(sim.read_across_shots(target), bit_matrix(expected, 12))
        assert not sim.read_phase_flipped_across_shots().any()
        report['same_source'].append(dict(exponent=exponent, T=circuit.operation_statistics().num_toffoli_like,
                                          Q=circuit.num_qubits, shots=4096))
    for degree, length, exhaustive in ((3, 4, True), (3, 8, False), (12, 6, False)):
        shots = (1 << (degree * (length - 1))) if exhaustive else 4096
        if exhaustive:
            inputs = (np.arange(shots, dtype=np.int64)[:, None] >>
                      (degree * np.arange(length - 1))) & ((1 << degree) - 1)
        else:
            inputs = rng.integers(0, 1 << degree, size=(shots, length - 1), dtype=np.int64)
            inputs[0] = 0
        small_field = km.GF2Field(degree)
        expected = np.array([reference_inverse([1] + [int(v) for v in row], small_field)[1:]
                             for row in inputs])
        circuit, words, counts = build_unit_reciprocal(degree, length)
        payload = serialized(circuit)
        assert payload == serialized(build_unit_reciprocal(degree, length)[0])
        assert circuit.num_qubits == degree * (length - 1)
        for seed in range(4):
            sim = km.Simulator(batch_size=shots, seed=seed)
            sim.use_same_registers_as(circuit)
            for i, word in enumerate(words):
                sim.write_across_shots(word, bit_matrix(inputs[:, i], degree))
            sim.do(circuit)
            for i, word in enumerate(words):
                assert np.array_equal(sim.read_across_shots(word), bit_matrix(expected[:, i], degree))
            assert not sim.read_phase_flipped_across_shots().any()
            sim.do(circuit)
            for i, word in enumerate(words):
                assert np.array_equal(sim.read_across_shots(word), bit_matrix(inputs[:, i], degree))
            assert not sim.read_phase_flipped_across_shots().any()
        entry = dict(degree=degree, length=length, shots_per_seed=shots, seeds=4,
                     exhaustive=exhaustive, Q=circuit.num_qubits, scratch_qubits=0,
                     T=circuit.operation_statistics().num_toffoli_like, operations=len(circuit),
                     sha256=hashlib.sha256(payload).hexdigest(), counts=counts)
        report['series'].append(entry)
        if destination:
            path = destination.parent.parent / 'circuits' / f'unit-reciprocal-b{degree}-n{length}.kmb'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
    if destination:
        destination.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    print(json.dumps(run_checks(path), indent=2))
