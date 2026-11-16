# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Public rank-42 tensor for the dual-number algebra over the supplied GF64.

An algebra element is the twelve-bit pair (constant, epsilon coefficient),
with epsilon squared zero. The construction interpolates cubic products
at seven GF8 points and then evaluates in this algebra. It uses no circuit
library, stored tensor, input profile, or sampled arithmetic data.
"""
from __future__ import annotations

from functools import cache
import hashlib
import json

SMALL_MODULUS = 0xB
BASE_MODULUS = 0x43


def mul(left, right, modulus=BASE_MODULUS):
    """Independent polynomial reduction in a specified binary field."""
    degree = modulus.bit_length() - 1
    result = 0
    while right:
        if right & 1:
            result ^= left
        right >>= 1
        left <<= 1
        if left >> degree:
            left ^= modulus
    return result


def power(value, exponent, modulus=BASE_MODULUS):
    result = 1
    while exponent:
        if exponent & 1:
            result = mul(result, value, modulus)
        value = mul(value, value, modulus)
        exponent >>= 1
    return result


def trace(value, modulus=BASE_MODULUS):
    result = 0
    for _ in range(modulus.bit_length() - 1):
        result ^= value
        value = mul(value, value, modulus)
    assert result in (0, 1)
    return result


def dual_product(left, right):
    """(a+u epsilon)(b+v epsilon) = ab+(av+ub) epsilon."""
    a, u = left & 63, left >> 6
    b, v = right & 63, right >> 6
    return mul(a, b) | ((mul(a, v) ^ mul(u, b)) << 6)


def dual_power(value, exponent):
    result = 1
    while exponent:
        if exponent & 1:
            result = dual_product(result, value)
        value = dual_product(value, value)
        exponent >>= 1
    return result


def apply(rows, value):
    return sum(((row & value).bit_count() & 1) << i
               for i, row in enumerate(rows))


def invert_columns(columns):
    size = len(columns)
    rows = [sum(((value >> bit) & 1) << col
                for col, value in enumerate(columns)) | (1 << (size + bit))
            for bit in range(size)]
    for col in range(size):
        pivot = next((row for row in range(col, size)
                      if rows[row] >> col & 1), None)
        if pivot is None:
            raise ValueError('dependent algebra basis')
        rows[col], rows[pivot] = rows[pivot], rows[col]
        for row in range(size):
            if row != col and rows[row] >> col & 1:
                rows[row] ^= rows[col]
    assert all(row & ((1 << size) - 1) == 1 << i
               for i, row in enumerate(rows))
    return tuple(row >> size for row in rows)


def invert_small_matrix(matrix):
    size = len(matrix)
    rows = [list(row) + [int(i == j) for j in range(size)]
            for i, row in enumerate(matrix)]
    for col in range(size):
        pivot = next(row for row in range(col, size) if rows[row][col])
        rows[col], rows[pivot] = rows[pivot], rows[col]
        reciprocal = power(rows[col][col], 6, SMALL_MODULUS)
        rows[col] = [mul(value, reciprocal, SMALL_MODULUS)
                     for value in rows[col]]
        for row in range(size):
            if row != col and rows[row][col]:
                scale = rows[row][col]
                rows[row] = [a ^ mul(scale, b, SMALL_MODULUS)
                             for a, b in zip(rows[row], rows[col])]
    assert all(row[:size] == [int(i == j) for j in range(size)]
               for i, row in enumerate(rows))
    return tuple(tuple(row[size:]) for row in rows)


def small_tensor():
    """Six binary products for the three-bit field, freshly derived."""
    terms = []
    for i in range(3):
        weight = power(2, 2*i, SMALL_MODULUS)
        for j in range(3):
            if i != j:
                weight ^= power(2, i+j, SMALL_MODULUS)
        if weight:
            terms.append((1 << i, 1 << i, weight))
    for i in range(3):
        for j in range(i+1, 3):
            mask = (1 << i) | (1 << j)
            terms.append((mask, mask, power(2, i+j, SMALL_MODULUS)))
    assert len(terms) == 6
    return tuple(terms)


def tensor_value(terms, left, right):
    result = 0
    for a, b, output in terms:
        if (a & left).bit_count() & 1 and (b & right).bit_count() & 1:
            result ^= output
    return result


@cache
def construction():
    beta = next(value for value in range(2, 64)
                if power(value, 3) ^ value ^ 1 == 0)
    subcolumns = tuple(power(beta, i) for i in range(3))

    def embed(value):
        result = 0
        for bit, column in enumerate(subcolumns):
            if value >> bit & 1:
                result ^= column
        return result

    for zeta in range(2, 64):
        generator = zeta | (1 << 6)
        columns = tuple(dual_product(dual_power(generator, degree), column)
                        for degree in range(4) for column in subcolumns)
        try:
            to_polynomial = invert_columns(columns)
            break
        except ValueError:
            continue
    else:
        raise AssertionError('no dual-number generator over the subfield')
    interpolation = invert_small_matrix(
        [[power(point, degree, SMALL_MODULUS) for degree in range(7)]
         for point in range(7)])
    terms = []
    for point in range(7):
        evaluation_rows = [0, 0, 0]
        for bit in range(12):
            coordinates = apply(to_polynomial, 1 << bit)
            value = 0
            for degree in range(4):
                value ^= mul((coordinates >> (3*degree)) & 7,
                             power(point, degree, SMALL_MODULUS), SMALL_MODULUS)
            for out in range(3):
                evaluation_rows[out] |= ((value >> out) & 1) << bit
        weight = 0
        for degree in range(7):
            weight ^= dual_product(embed(interpolation[degree][point]),
                                   dual_power(generator, degree))

        def compose(mask):
            value = 0
            for bit, row in enumerate(evaluation_rows):
                if mask >> bit & 1:
                    value ^= row
            return value

        for left, right, output in small_tensor():
            terms.append((compose(left), compose(right),
                          dual_product(weight, embed(output))))
    assert len(terms) == 42 and all(all(term) for term in terms)
    assert all(value < 4096 for term in terms for value in term)
    return dict(beta=beta, zeta=zeta, generator=generator,
                subfield_columns=subcolumns, algebra_columns=columns,
                to_polynomial=to_polynomial, interpolation=interpolation,
                terms=tuple(terms))


def multiplication_tensor():
    return construction()['terms']


def certificate():
    """Small exhaustive basis certificate, with no native imports or builds."""
    data = construction()
    terms = data['terms']
    small = small_tensor()
    for left in range(8):
        for right in range(8):
            assert tensor_value(small, left, right) == mul(left, right, SMALL_MODULUS)
    for i, column in enumerate(data['algebra_columns']):
        assert apply(data['to_polynomial'], column) == 1 << i
    for left in range(12):
        for right in range(12):
            assert tensor_value(terms, 1 << left, 1 << right) == dual_product(1 << left, 1 << right)
    serialized = json.dumps(data, sort_keys=True, separators=(',', ':')).encode()
    return dict(status='PASS_EXACT_DUAL_NUMBER_BILINEAR_CERTIFICATE_ONLY',
                base_modulus=BASE_MODULUS, subfield_modulus=SMALL_MODULUS,
                binary_products=len(terms), full_algebra_basis_pairs=144,
                small_field_input_pairs=64, beta=data['beta'],
                zeta=data['zeta'], generator=data['generator'],
                tensor_and_chart_sha256=hashlib.sha256(serialized).hexdigest(),
                native_circuit_checked=False)


if __name__ == '__main__':
    print(json.dumps(certificate(), indent=2, sort_keys=True))
