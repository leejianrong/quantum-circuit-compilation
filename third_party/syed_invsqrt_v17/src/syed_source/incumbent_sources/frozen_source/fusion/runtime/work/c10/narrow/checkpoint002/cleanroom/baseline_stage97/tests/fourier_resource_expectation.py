# Copyright 2026 Syed Asad Ali (team syed3000)
# SPDX-License-Identifier: Apache-2.0
"""Exact branch probabilities without assuming independent nested guards.

This is a test/accounting utility, never an input to circuit generation.  Each
syntactic HMR gets an independent fair bit; an inactive HMR retains its old
classical destination.  Affine leaves are evaluated on their exact GF(2) rank,
so (odd OR twice) AND odd has probability 1/2, not 1/4.  A bounded rank cap
rejects a larger expression instead of guessing its expectation.
"""
from __future__ import annotations

from fractions import Fraction
from functools import lru_cache
from branch_prover import Program


ZERO = ('affine', 0, 0)
ONE = ('affine', 1, 0)


def xor(*values):
    constant, mask, terms = 0, 0, set()
    pending = list(values)
    while pending:
        value = pending.pop()
        if value[0] == 'xor':
            pending.extend(value[1])
        elif value[0] == 'affine':
            constant ^= value[1]; mask ^= value[2]
        elif value in terms:
            terms.remove(value)
        else:
            terms.add(value)
    if constant or mask:
        terms.add(('affine', constant, mask))
    if not terms: return ZERO
    if len(terms) == 1: return next(iter(terms))
    return ('xor', tuple(sorted(terms, key=repr)))


def product(*values):
    terms = set()
    pending = list(values)
    while pending:
        value = pending.pop()
        if value == ZERO: return ZERO
        if value == ONE: continue
        if value[0] == 'and': pending.extend(value[1])
        else: terms.add(value)
    # This common simplification also prevents a stale inactive outcome from
    # inflating a later guard that explicitly requires its active branch.
    for value in tuple(terms):
        if xor(value, ONE) in terms: return ZERO
    if not terms: return ONE
    if len(terms) == 1: return next(iter(terms))
    return ('and', tuple(sorted(terms, key=repr)))


def choose(condition, yes, no):
    if yes == no: return yes
    return xor(no, product(condition, xor(yes, no)))


def affine_leaves(value, result):
    if value[0] == 'affine': result.add(value)
    else:
        for child in value[1]: affine_leaves(child, result)


def probability(value, *, rank_cap=12):
    leaves = set(); affine_leaves(value, leaves)
    basis, pivots, coordinates = [], {}, {}
    for leaf in sorted(leaves):
        remaining, representation = leaf[2], 0
        while remaining:
            pivot = remaining.bit_length()-1
            if pivot not in pivots:
                if len(basis) >= rank_cap:
                    raise ValueError('Exact branch-probability rank exceeds the explicit cap.')
                bit = 1 << len(basis)
                basis.append(remaining)
                pivots[pivot] = (remaining, bit)
                representation ^= bit
                remaining = 0
                break
            row, coordinate = pivots[pivot]
            remaining ^= row; representation ^= coordinate
        coordinates[leaf] = representation

    def evaluate(node, assignment):
        kind = node[0]
        if kind == 'affine':
            return node[1] ^ ((coordinates[node] & assignment).bit_count() & 1)
        if kind == 'xor':
            return sum(evaluate(child, assignment) for child in node[1]) & 1
        return int(all(evaluate(child, assignment) for child in node[1]))

    return Fraction(sum(evaluate(value, assignment) for assignment in range(1 << len(basis))),
                    1 << len(basis)), len(basis)


def exact_expectation(text, *, rank_cap=12, include_gates=False):
    program = Program(text)
    classical = {'0': ZERO, '1': ONE, 'False': ZERO, 'True': ONE}
    stack = [ONE]
    measured = set()
    cached = {}
    totals = dict(toffoli_like=Fraction(0), T=Fraction(0), generic_rotations=Fraction(0))
    static = dict(toffoli_like=0, T=0, generic_rotations=0)
    records = []
    max_rank = 0

    def read(wire):
        if wire.startswith('q'):
            raise ValueError('A quantum wire was used as a classical accounting condition.')
        return classical.get(wire, ZERO)

    for index, op in enumerate(program.operations):
        kind, args = op.kind, op.arguments
        active = product(stack[-1], ONE if op.condition is None else read(op.condition))
        if kind == 'PUSH_CONDITION': stack.append(active); continue
        if kind == 'POP_CONDITION':
            if len(stack) == 1: raise AssertionError('Unmatched condition pop.')
            stack.pop(); continue
        category = None
        if kind in ('CCX', 'CCZ', 'CSWAP'):
            if not all(wire.startswith('q') for wire in args):
                raise ValueError('Resource accounting requires quantum Toffoli-like operands.')
            category = 'toffoli_like'
        elif kind == 'Z_POW':
            angle = op.half_turns % 2
            if angle.denominator == 4: category = 'T'
            elif angle.denominator > 4: category = 'generic_rotations'
        if category is not None:
            if active not in cached: cached[active] = probability(active, rank_cap=rank_cap)
            chance, rank = cached[active]
            max_rank = max(max_rank, rank)
            totals[category] += chance; static[category] += 1
            if include_gates:
                records.append(dict(instruction=index, operation=kind, category=category,
                                    probability=str(chance), affine_rank=rank))
        if kind == 'HMR':
            if op.event in measured: raise AssertionError('A syntactic outcome was reused.')
            measured.add(op.event)
            variable = ('affine', 0, 1 << op.event)
            classical[args[1]] = choose(active, variable, read(args[1]))
        elif kind in ('BIT_STORE0', 'BIT_STORE1'):
            classical[args[0]] = choose(active, ONE if kind == 'BIT_STORE1' else ZERO, read(args[0]))
        elif kind == 'BIT_INVERT' or (kind == 'X' and args[0].startswith('b')):
            classical[args[0]] = xor(read(args[0]), active)
        elif kind == 'CX' and args[1].startswith('b'):
            classical[args[1]] = xor(read(args[1]), product(active, read(args[0])))
        elif kind == 'SWAP' and any(wire.startswith('b') for wire in args):
            raise ValueError('Classical SWAP needs an explicit accounting rule.')
    if len(stack) != 1: raise AssertionError('Unclosed accounting condition.')
    report = dict(status='EXACT_EXPECTATION_FROM_CLASSICAL_GUARDS',
        assumptions=['Every active HMR measures a computational-basis wire and has a fair independent outcome.',
                     'Conditional costs count instruction execution, independently of quantum control values.'],
        accounting='exact Boolean guards; GF2-rank enumeration of affine leaves',
        rank_cap=rank_cap, maximum_rank_used=max_rank,
        syntactic_measurements=program.measurements, static=static,
        mean={key: str(value) for key, value in totals.items()},
        mean_numeric={key: float(value) for key, value in totals.items()},
        mean_Toffoli_plus_T_quarter=str(totals['toffoli_like']+totals['T']/4),
        independent_condition_depth_not_assumed=True,
        official_verified=False)
    if include_gates: report['charged_gates'] = records
    return report


def unit_cases():
    o = ('affine', 0, 1); t = ('affine', 0, 2)
    either = xor(o, t, product(o, t))
    assert probability(product(either, o))[0] == Fraction(1, 2)
    assert probability(either)[0] == Fraction(3, 4)
    assert probability(xor(o, t))[0] == Fraction(1, 2)
    assert probability(product(o, xor(o, ONE)))[0] == 0
    # Conditional overwrite with a stale old destination is not a new fair bit.
    m = ('affine', 0, 4)
    assert probability(choose(o, m, ONE))[0] == Fraction(3, 4)
    assert probability(product(o, choose(o, m, ONE)))[0] == Fraction(1, 4)
    return dict(status='PASS', cases=6, correlated_OR_nested_guard_checked=True,
                conditional_HMR_old_destination_checked=True)


if __name__ == '__main__':
    import json
    print(json.dumps(unit_cases(), sort_keys=True))
