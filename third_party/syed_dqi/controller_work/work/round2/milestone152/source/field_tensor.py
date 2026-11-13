# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""Derive a rank-42 multiplication tensor for the specified degree-12 field.

No downloaded implementation, literal tensor, or input sample is used.
The construction evaluates a cubic over GF(8) at seven field points,
multiplies with the six symmetric bilinear products for a three-bit
polynomial, interpolates, and maps to Kickmix's polynomial basis.
"""
from __future__ import annotations

from functools import cache
import kickmix as km


def parity(value: int) -> int:
    return value.bit_count() & 1


def apply_linear(rows: tuple[int, ...], value: int) -> int:
    return sum(parity(row & value) << i for i, row in enumerate(rows))


def invert_binary_columns(columns: list[int]) -> tuple[int, ...]:
    n = len(columns)
    rows = [sum(((c >> i) & 1) << j for j, c in enumerate(columns))
            | (1 << (n + i)) for i in range(n)]
    for j in range(n):
        pivot = next((i for i in range(j, n) if rows[i] >> j & 1), None)
        if pivot is None:
            raise ValueError('singular basis')
        rows[j], rows[pivot] = rows[pivot], rows[j]
        for i in range(n):
            if i != j and rows[i] >> j & 1:
                rows[i] ^= rows[j]
    return tuple(row >> n for row in rows)


def invert_field_matrix(matrix: list[list[int]], field) -> list[list[int]]:
    n = len(matrix)
    rows = [row[:] + [int(i == j) for j in range(n)]
            for i, row in enumerate(matrix)]
    for j in range(n):
        pivot = next(i for i in range(j, n) if rows[i][j])
        rows[j], rows[pivot] = rows[pivot], rows[j]
        inverse = field.invert(rows[j][j])
        rows[j] = [field.mul(v, inverse) for v in rows[j]]
        for i in range(n):
            if i != j and rows[i][j]:
                factor = rows[i][j]
                rows[i] = [a ^ field.mul(factor, b)
                           for a, b in zip(rows[i], rows[j])]
    return [row[n:] for row in rows]


def symmetric_tensor(degree: int, field) -> tuple[tuple[int, int, int], ...]:
    """Schoolbook symmetric cross terms, with each bit product used once."""
    terms = []
    for i in range(degree):
        w = field.pow(2, 2 * i)
        for j in range(degree):
            if j != i:
                w ^= field.pow(2, i + j)
        if w:
            terms.append((1 << i, 1 << i, w))
    for i in range(degree):
        for j in range(i + 1, degree):
            mask = (1 << i) | (1 << j)
            terms.append((mask, mask, field.pow(2, i + j)))
    return tuple(terms)


@cache
def multiplication_tensor() -> tuple[tuple[int, int, int], ...]:
    field, small = km.GF2Field(12), km.GF2Field(3)
    assert small.modulus == (1 << 3) | (1 << 1) | 1
    beta = next(v for v in range(2, 1 << field.degree)
                if field.pow(v, 3) ^ v ^ 1 == 0)
    sub_basis = [field.pow(beta, i) for i in range(small.degree)]

    def embed(value):
        result = 0
        for i, column in enumerate(sub_basis):
            if value >> i & 1:
                result ^= column
        return result

    for theta in range(2, 1 << field.degree):
        columns = [field.mul(field.pow(theta, i), column)
                   for i in range(4) for column in sub_basis]
        try:
            to_tower = invert_binary_columns(columns)
            break
        except ValueError:
            continue
    else:
        raise AssertionError('no quartic tower basis')

    points = range(7)
    interpolation = invert_field_matrix(
        [[small.pow(point, k) for k in points] for point in points], small)
    terms = []
    for point in points:
        eval_rows = [0] * small.degree
        for j in range(field.degree):
            tower_value = apply_linear(to_tower, 1 << j)
            evaluated = 0
            for i in range(4):
                coefficient = tower_value >> (small.degree * i) & 7
                evaluated ^= small.mul(coefficient, small.pow(point, i))
            for bit in range(small.degree):
                eval_rows[bit] |= ((evaluated >> bit) & 1) << j
        weight = 0
        for k in points:
            weight ^= field.mul(embed(interpolation[k][point]), field.pow(theta, k))

        def compose(mask):
            value = 0
            for bit, row in enumerate(eval_rows):
                if mask >> bit & 1:
                    value ^= row
            return value

        for left, right, output in symmetric_tensor(3, small):
            terms.append((compose(left), compose(right), field.mul(weight, embed(output))))
    assert len(terms) == 42 and all(all(term) for term in terms)
    return tuple(terms)


def tensor_value(terms, left: int, right: int) -> int:
    result = 0
    for a, b, output in terms:
        if parity(a & left) and parity(b & right):
            result ^= output
    return result


def parity_pivot(builder, register, mask: int):
    pivot = (mask & -mask).bit_length() - 1
    for i, wire in enumerate(register):
        if i != pivot and mask >> i & 1:
            builder.cx(wire, register[pivot])
    return register[pivot]


def accumulate_product(builder, left, right, target, terms=None):
    """XOR a field product into any target; all three registers disjoint."""
    if terms is None:
        terms = multiplication_tensor()
    if len(set(left) | set(right) | set(target)) != len(left) + len(right) + len(target):
        raise ValueError('product registers overlap')
    for a, b, output in terms:
        x = parity_pivot(builder, left, a)
        y = parity_pivot(builder, right, b)
        pivot = (output & -output).bit_length() - 1
        fanout = [wire for i, wire in enumerate(target) if i != pivot and output >> i & 1]
        for wire in fanout:
            builder.cx(target[pivot], wire)
        builder.ccx(x, y, target[pivot])
        for wire in reversed(fanout):
            builder.cx(target[pivot], wire)
        parity_pivot(builder, right, b)
        parity_pivot(builder, left, a)
