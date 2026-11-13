# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""Reversible classical mask gauge for moments S_1,...,S_n.

Selected E words temporarily hold trace-Gram images of G's coefficients;
they are not zero registers. Only their *logical scan weights* are zero,
so the caller must omit precisely those selected point tests. No quantum
scratch or extra classical scratch is allocated by this module.
"""
from dataclasses import dataclass
from functools import cache

import kickmix as km

from field_tensor import apply_linear, invert_binary_columns, invert_field_matrix
from tower_inverse import rows_from_columns, sum_trace


def linear_network(rows):
    """Return an in-place CNOT/SWAP network for a nonsingular binary map."""
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
    return tuple(reversed(operations))


def emit_network(builder, words, operations, inverse=False):
    bits = [bit for word in words for bit in word]
    for name, left, right in reversed(operations) if inverse else operations:
        getattr(builder, name)(bits[left], bits[right])


@dataclass(frozen=True)
class Plan:
    bits: int
    selected: tuple
    points: tuple
    selected_indices: tuple
    interpolation: tuple
    advance: tuple
    gram_rows: tuple
    inverse_gram_rows: tuple


@cache
def make_plan(bits, selected):
    """Public fixed plan; no quantum/classical mask value chooses a branch."""
    selected = tuple(selected)
    field = km.GF2Field(bits)
    count = len(selected)
    assert count and len(set(selected)) == count
    assert all(0 < x < 1 << bits for x in selected)
    points = tuple(field.pow(field.primitive_element, i) for i in range((1 << bits) - 1))
    index = {x: i for i, x in enumerate(points)}
    assert len(index) == len(points)
    gram_columns = tuple(sum(sum_trace(field.mul(1 << i, 1 << j), field) << j
                             for j in range(bits)) for i in range(bits))
    gram_rows = rows_from_columns(gram_columns)
    inverse_gram = invert_binary_columns(gram_columns)
    inverse = invert_field_matrix([[field.pow(x, j + 1) for j in range(count)] for x in selected], field)
    # selected bit masks -> alpha_i -> g_j -> Gram*g_j. The field matrix
    # uses powers 1..n, deliberately excluding a constant coefficient.
    columns = []
    for i in range(count):
        for bit in range(bits):
            dual = apply_linear(inverse_gram, 1 << bit)
            columns.append(sum(apply_linear(gram_rows, field.mul(inverse[j][i], dual)) << (bits * j)
                               for j in range(count)))
    interpolation = linear_network(rows_from_columns(columns))
    advance = []
    for j in range(count):
        multiplier = field.pow(field.primitive_element, j + 1)
        columns = [apply_linear(gram_rows, field.mul(multiplier, apply_linear(inverse_gram, 1 << bit)))
                   for bit in range(bits)]
        advance.extend((name, bits * j + a, bits * j + b)
                       for name, a, b in linear_network(rows_from_columns(columns)))
    return Plan(bits, selected, points, tuple(index[x] for x in selected),
                interpolation, tuple(advance), gram_rows, inverse_gram)


@cache
def physical_plan():
    """70 fixed nonzero positions, including all 34 extraction nodes."""
    from node_query import nodes
    field = km.GF2Field(12)
    selected = list(nodes())
    point = 1
    while len(selected) < 70:
        if point not in selected:
            selected.append(point)
        point = field.mul(point, field.primitive_element)
    return make_plan(12, tuple(selected))


def adjust_nonselected(builder, masks, plan):
    """XOR Gram*G(x) into every unselected mask using a full Chien cycle.

    At physical point x the selected words contain Gram*(g_j*x**j).
    Advancing through the complete nonzero field returns every coefficient
    to its starting representation. Thus this entire map is an involution.
    """
    assert len(masks) == len(plan.points)
    words = [masks[i] for i in plan.selected_indices]
    chosen = set(plan.selected_indices)
    flat = km.array([bit for word in words for bit in word])
    for i in range(len(plan.points)):
        if i not in chosen:
            builder.cx(flat, km.array([bit for _ in words for bit in masks[i]]))
        emit_network(builder, words, plan.advance)


def open_gauge(builder, syndromes, masks, plan=None):
    """Apply the compensating phase once and expose adjusted scan masks."""
    plan = physical_plan() if plan is None else plan
    assert len(syndromes) == len(plan.selected)
    assert all(len(word) == plan.bits for word in syndromes + list(masks))
    assert len(masks) == len(plan.points)
    live = builder.num_allocated_qubits
    words = [masks[i] for i in plan.selected_indices]
    emit_network(builder, words, plan.interpolation)
    for coefficient, syndrome in zip(words, syndromes):
        builder.cz(coefficient, syndrome)
    adjust_nonselected(builder, masks, plan)
    assert builder.num_allocated_qubits == live
    return plan


def close_gauge(builder, masks, plan=None):
    """Restore all E words without repeating/cancelling the compensation."""
    plan = physical_plan() if plan is None else plan
    live = builder.num_allocated_qubits
    adjust_nonselected(builder, masks, plan)
    emit_network(builder, [masks[i] for i in plan.selected_indices], plan.interpolation, inverse=True)
    assert builder.num_allocated_qubits == live
