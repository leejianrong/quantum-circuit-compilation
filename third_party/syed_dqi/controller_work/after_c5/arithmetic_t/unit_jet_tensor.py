# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Consuming length-two/three Taylor multiplication with 24 helper bits.

The source constant is a unit. Source and target words are disjoint and
preserved/restored by the paired API. The prefixes cost 99/168 T; their
locally phase-exact returns cost 218/344 T. No native result is asserted
by this source. The length-three prefix does NOT allocate 36 clean bits.

The polynomial construction uses the supplied GF16 embedding and its
nine-product multiplier, but derives its interpolation tensor here. The
length-three old high-target debt is in an explicitly sheared chart.
"""
from dataclasses import dataclass
from functools import cache

import kickmix as km
from compact_inverse import compact_inverse_twelve
from field_tensor import (accumulate_product, apply_linear,
                          invert_binary_columns, invert_field_matrix,
                          tensor_value)
from inverse_phase27 import gf16_kernel
from monic_forney import flat
from projective_carry import erase_inverse_word
from quantum_reciprocal import xor_linear
from tower_inverse import xor_product, phase_product, kernel

F = km.GF2Field(12)
SMALL = km.GF2Field(4)
BETA, THETA = 1970, 937


def embed(value):
    result = 0
    for bit in range(4):
        if value >> bit & 1:
            result ^= F.pow(BETA, bit)
    return result


def jet_power(exponent, size):
    """(THETA+t)^exponent modulo t^size, in ascending Taylor order."""
    return tuple(F.pow(THETA, exponent-j)
                 if exponent >= j and (exponent & j) == j else 0
                 for j in range(size))


def polynomial_jet(coefficients, size):
    result = [0]*size
    for exponent, coefficient in enumerate(coefficients):
        embedded = embed(coefficient)
        for j, value in enumerate(jet_power(exponent, size)):
            result[j] ^= F.mul(embedded, value)
    return sum(value << (12*j) for j, value in enumerate(result))


@cache
def polynomial_basis(size):
    assert size in (2, 3)
    assert F.modulus == 0x1053 and SMALL.modulus == 0x13
    assert F.pow(BETA, 4) ^ BETA ^ 1 == 0
    assert F.pow(THETA, 3) ^ THETA ^ 1 == 0
    columns = tuple(polynomial_jet([0]*i+[1 << bit], size)
                    for i in range(3*size) for bit in range(4))
    return dict(columns=columns, to_polynomial=invert_binary_columns(columns))


def _coefficient_list(value, size):
    return [(value >> (4*j)) & 15 for j in range(3*size)]


@cache
def high_lift_columns():
    """B0,B1 -> B2 for the unique degree<6 GF16 Hermite polynomial."""
    rows = polynomial_basis(2)['to_polynomial']
    return tuple(polynomial_jet(_coefficient_list(apply_linear(rows, 1 << bit), 2), 3) >> 24
                 for bit in range(24))


def _evaluation_rows(size, point):
    rows = [0]*4
    basis = polynomial_basis(size)['to_polynomial']
    for bit in range(12*size):
        coefficients = _coefficient_list(apply_linear(basis, 1 << bit), size)
        value = 0
        for exponent, coefficient in enumerate(coefficients):
            value ^= SMALL.mul(coefficient, SMALL.pow(point, exponent))
        for k in range(4):
            rows[k] |= ((value >> k) & 1) << bit
    return rows


def _compose(rows, mask):
    result = 0
    for i, row in enumerate(rows):
        if mask >> i & 1:
            result ^= row
    return result


@cache
def product_tensor(source_size, target_size, output_size):
    """Multiply the two canonical GF16 polynomials and return its jet.

    target_size=2, output_size=3 intentionally includes the lifted third
    coefficient. Its complement is consumed separately by the prefix.
    """
    assert (source_size, target_size, output_size) in ((2, 2, 2), (3, 2, 3))
    count = 3*(source_size+target_size)-1
    assert count <= 16
    interpolation = invert_field_matrix(
        [[SMALL.pow(point, exponent) for exponent in range(count)]
         for point in range(count)], SMALL)
    terms = []
    for point in range(count):
        left_rows = _evaluation_rows(source_size, point)
        right_rows = _evaluation_rows(target_size, point)
        for left, right, output in gf16_kernel():
            coefficients = [SMALL.mul(interpolation[k][point], output)
                            for k in range(count)]
            weight = polynomial_jet(coefficients, output_size)
            terms.append((_compose(left_rows, left), _compose(right_rows, right), weight))
    assert len(terms) == 9*count and all(all(term) for term in terms)
    return tuple(terms)


def jet_product(left, right, size):
    out = [0]*size
    for i in range(size):
        for j in range(i+1):
            out[i] ^= F.mul((left >> (12*j)) & 4095,
                            (right >> (12*(i-j))) & 4095)
    return sum(value << (12*i) for i, value in enumerate(out))


def certify_tensors():
    """Exact binary-basis identities; no stochastic or native evaluation."""
    receipts = []
    for source_size, target_size, output_size in ((2, 2, 2), (3, 2, 3)):
        terms = product_tensor(source_size, target_size, output_size)
        tests = 0
        for a in range(12*source_size):
            for b in range(12*target_size):
                right = 1 << b
                if output_size == 3:
                    right |= high_lift_columns()[b] << 24
                assert tensor_value(terms, 1 << a, 1 << b) == jet_product(1 << a, right, output_size)
                tests += 1
        receipts.append(dict(source_size=source_size, target_size=target_size,
                             output_size=output_size, terms=len(terms), binary_basis_checks=tests))
    return receipts


@dataclass
class Record:
    builder_id: int
    size: int
    source: tuple
    targets: tuple
    masks: list
    sheared_high: bool
    closed: bool = False


def emit_prefix(builder, source_words, target_words):
    source_words, target_words = list(source_words), list(target_words)
    m = len(source_words)
    assert m in (2, 3) and len(target_words) == m
    assert len(set(flat(source_words+target_words))) == 24*m
    masks = [None]*m
    if m == 3:
        # The high remainder is consumed before the lower inputs change.
        xor_linear(builder, flat(target_words[:2]), target_words[2], high_lift_columns())
        temporary = builder.alloc_qubits(12)
        xor_product(builder, source_words[0], target_words[2], temporary)
        builder.swap(target_words[2], temporary)
        masks[2] = builder.alloc_bits(12)
        builder.hmr(temporary, masks[2])
        builder.free(temporary)
    temporary = builder.alloc_qubits(24)
    output = km.array([*temporary, *(target_words[2] if m == 3 else [])])
    accumulate_product(builder, flat(source_words), flat(target_words[:2]), output,
                       product_tensor(m, 2, m))
    builder.swap(flat(target_words[:2]), temporary)
    for i in range(2):
        masks[i] = builder.alloc_bits(12)
        builder.hmr(temporary[12*i:12*(i+1)], masks[i])
    builder.free(temporary)
    return Record(id(builder), m, tuple(tuple(w) for w in source_words),
                  tuple(tuple(w) for w in target_words), masks, m == 3)


def emit_closing(builder, source_words, target_words, record, *, keep_inverse=False):
    """Restore every target, repay all target debts; optionally keep 1/S0.

    A retained reciprocal has no escaped classical HMR mask. The caller
    must preserve S0, or transform it and the reciprocal consistently, and
    finally erase the reciprocal through the original source-aware API.
    """
    assert record.builder_id == id(builder) and not record.closed
    assert record.source == tuple(tuple(w) for w in source_words)
    assert record.targets == tuple(tuple(w) for w in target_words)
    reciprocal = compact_inverse_twelve(builder, source_words[0])
    temporary = builder.alloc_qubits(12)
    for i in range(record.size):
        for j in range(1, i+1):
            xor_product(builder, source_words[j], target_words[i-j], target_words[i])
        xor_product(builder, reciprocal, target_words[i], temporary)
        builder.swap(target_words[i], temporary)
        mask = builder.alloc_bits(12)
        builder.hmr(temporary, mask)
        phase_product(builder, source_words[0], target_words[i], mask, kernel(12))
        builder.free(mask)
    builder.free(temporary)
    if not keep_inverse:
        erase_inverse_word(builder, source_words[0], reciprocal)
    for i, (word, mask) in enumerate(zip(target_words, record.masks)):
        if i == 2 and record.sheared_high:
            xor_linear(builder, flat(target_words[:2]), word, high_lift_columns())
        builder.cz(mask, word)
        if i == 2 and record.sheared_high:
            xor_linear(builder, flat(target_words[:2]), word, high_lift_columns())
        builder.free(mask)
    record.closed = True
    return reciprocal if keep_inverse else None
