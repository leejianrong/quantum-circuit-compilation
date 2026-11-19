# Copyright 2026 Syed Asad Ali (team syed3000)
# SPDX-License-Identifier: Apache-2.0
"""Exact product-rank compilation from quadratic ANF, without large tables."""
from __future__ import annotations
from dataclasses import dataclass


def product_terms(left, right):
    terms = set()
    for i in range(left.bit_length()):
        if not (left >> i)&1:
            continue
        for j in range(right.bit_length()):
            if (right >> j)&1:
                key = (1 << i)|(1 << j)
                terms.symmetric_difference_update((key,))
    return terms


def gf2_rank(rows):
    pivots = {}
    for row in rows:
        while row:
            pivot = row.bit_length()-1
            if pivot not in pivots:
                pivots[pivot] = row
                break
            row ^= pivots[pivot]
    return len(pivots)


@dataclass(frozen=True)
class PolynomialPlan:
    width: int
    affine: tuple[int, ...]
    products: tuple[tuple[int, int, int, int], ...]
    original: tuple[int, ...]
    alternating_rank: int


def compile_polynomial(width, terms):
    """Factor with exact coefficient comparison and the rank lower bound.

    An ANF coefficient is indexed by the set of its variables, as a bit mask.
    Duplicate input terms cancel.  This polynomial representation is exact
    on the entire Boolean cube, with no sampling and no truth-table limit.
    """
    remaining = set()
    for term in terms:
        term = int(term)
        if term < 0 or term >> width or term.bit_count() > 2:
            raise ValueError("Expected constant, linear, or quadratic ANF terms.")
        remaining.symmetric_difference_update((term,))
    original = tuple(sorted(remaining))
    matrix = [0]*width
    for term in original:
        if term.bit_count() == 2:
            i, j = [k for k in range(width) if (term >> k)&1]
            matrix[i] ^= 1 << j
            matrix[j] ^= 1 << i
    rank = gf2_rank(matrix)
    products = []
    while any(term.bit_count() == 2 for term in remaining):
        edge = min(term for term in remaining if term.bit_count() == 2)
        i, j = [k for k in range(width) if (edge >> k)&1]
        left, right = 1 << i, 1 << j
        for k in range(width):
            if k == i or k == j:
                continue
            if ((1 << j)|(1 << k)) in remaining:
                left |= 1 << k
            if ((1 << i)|(1 << k)) in remaining:
                right |= 1 << k
        remaining.symmetric_difference_update(product_terms(left, right))
        products.append((left, right, i, j))
    recovered = set(remaining)
    for left, right, _, _ in products:
        recovered.symmetric_difference_update(product_terms(left, right))
    if recovered != set(original) or len(products)*2 != rank:
        raise AssertionError("Quadratic synthesis certificate failed.")
    return PolynomialPlan(width, tuple(sorted(remaining)), tuple(products),
                          original, rank)


def xor_polynomial(builder, variables, target, terms):
    """Emit a rank-minimal AND/XOR realization, preserving all input wires."""
    variables = list(variables)
    if len(set(variables)) != len(variables) or target in variables:
        raise ValueError("Input variables and target must be distinct.")
    plan = compile_polynomial(len(variables), terms)
    for term in plan.affine:
        if term:
            builder.cx(variables[term.bit_length()-1], target)
        else:
            builder.x(target)
    for left, right, i, j in plan.products:
        frames = [(variables[k], variables[i]) for k in range(plan.width)
                  if k != i and (left >> k)&1]
        frames += [(variables[k], variables[j]) for k in range(plan.width)
                   if k != j and (right >> k)&1]
        for a, b in frames:
            builder.cx(a, b)
        builder.ccx(variables[i], variables[j], target)
        for a, b in reversed(frames):
            builder.cx(a, b)
    return plan
