# Copyright 2026 Syed Asad Ali (team syed3000)
# SPDX-License-Identifier: Apache-2.0
"""Exact synthesis on a mathematical coefficient codebook.

All inputs are truth tables produced by the coefficient fitter, never compiled
circuits. A quadratic representation need only agree on the supplied reachable
codewords. Its emitted XOR circuit is nevertheless an exact Boolean polynomial
on every wire assignment. HMR deletion is exact for either outcome because the
same polynomial is used to repay its complete phase.
"""
from __future__ import annotations

from dataclasses import dataclass
import random


def bits(value):
    while value:
        bit = value & -value
        yield bit.bit_length() - 1
        value ^= bit


class BinarySpan:
    def __init__(self, columns=()):
        self.pivots = {}
        self.columns = []
        self.nullspace = []
        for column in columns:
            self.add(column)

    def add(self, column):
        column = int(column)
        index = len(self.columns)
        self.columns.append(column)
        reduced, expression = column, 1 << index
        while reduced:
            pivot = reduced.bit_length() - 1
            if pivot not in self.pivots:
                self.pivots[pivot] = (reduced, expression)
                return True
            old, mask = self.pivots[pivot]
            reduced ^= old
            expression ^= mask
        self.nullspace.append(expression)
        return False

    def solve(self, target):
        reduced, expression = int(target), 0
        while reduced:
            pivot = reduced.bit_length() - 1
            if pivot not in self.pivots:
                return None
            old, mask = self.pivots[pivot]
            reduced ^= old
            expression ^= mask
        return expression


def pack_bits(values):
    return sum((int(value) & 1) << i for i, value in enumerate(values))


def word_functions(values, width):
    values = list(values)
    return [pack_bits(value >> bit for value in values) for bit in range(width)]


def parity_function(mask, functions):
    out = 0
    for bit in bits(mask):
        out ^= functions[bit]
    return out


@dataclass(frozen=True)
class QuadraticCodePlan:
    width: int
    constant: bool
    linear: int
    edges: tuple[tuple[int, int], ...]
    # Each factorization step supplies pivots i,j. Neither factor includes the
    # other pivot, so their in-place Clifford frames do not interfere.
    products: tuple[tuple[int, int, int, int], ...]
    product_linear: int

    @property
    def and_count(self):
        return len(self.products)

    def evaluate_bits(self, value):
        out = int(self.constant) ^ ((value & self.linear).bit_count() & 1)
        for i, j in self.edges:
            out ^= ((value >> i) & 1) & ((value >> j) & 1)
        return out

    def evaluate_functions(self, functions, full):
        out = full if self.constant else 0
        out ^= parity_function(self.linear, functions)
        for i, j in self.edges:
            out ^= functions[i] & functions[j]
        return out

    def evaluate_factored_functions(self, functions, full):
        out = full if self.constant else 0
        out ^= parity_function(self.product_linear, functions)
        for left, right, i, j in self.products:
            if not (left >> i & 1 and right >> j & 1) or left >> j & 1 or right >> i & 1:
                raise AssertionError('Product factors do not admit the declared CNOT frames.')
            out ^= parity_function(left, functions) & parity_function(right, functions)
        return out


def factor_polynomial(width, constant, linear, edges):
    original_edges = tuple(sorted(edges))
    edges = set(original_edges)
    affine = int(linear)
    products = []
    while edges:
        i, j = min(edges)
        left, right = 1 << i, 1 << j
        for k in range(width):
            if k != i and k != j:
                if tuple(sorted((j, k))) in edges:
                    left |= 1 << k
                if tuple(sorted((i, k))) in edges:
                    right |= 1 << k
        for a in bits(left):
            for b in bits(right):
                if a == b:
                    affine ^= 1 << a
                else:
                    edge = tuple(sorted((a, b)))
                    if edge in edges:
                        edges.remove(edge)
                    else:
                        edges.add(edge)
        products.append((left, right, i, j))
    return QuadraticCodePlan(width, bool(constant), int(linear), original_edges,
                             tuple(products), affine)


class Codebook:
    def __init__(self, functions, size=256):
        self.functions = tuple(map(int, functions))
        self.width = len(self.functions)
        self.size = int(size)
        self.full = (1 << self.size) - 1
        if any(function & ~self.full for function in self.functions):
            raise ValueError('Function extends beyond the codebook domain.')
        self.monomials = [()] + [(i,) for i in range(self.width)]
        self.monomials += [(i, j) for i in range(self.width)
                          for j in range(i + 1, self.width)]
        self.columns = [self.full] + list(self.functions)
        self.columns += [self.functions[i] & self.functions[j]
                         for i in range(self.width)
                         for j in range(i + 1, self.width)]
        self.span = BinarySpan(self.columns)

    def decode_expression(self, expression):
        constant, linear, edges = False, 0, []
        for index in bits(expression):
            monomial = self.monomials[index]
            if not monomial:
                constant = not constant
            elif len(monomial) == 1:
                linear ^= 1 << monomial[0]
            else:
                edges.append(monomial)
        return factor_polynomial(self.width, constant, linear, edges)

    def represent(self, target, *, trials=0, seed=0, initial_plan=None):
        """Find a certified quadratic representation, optionally lower its rank.

        The deterministic search samples factorizations with fewer left factors.
        It is a heuristic over reachable codewords, not a claim of global
        multiplicative optimality. Every accepted result is checked exactly.
        """
        target = int(target)
        expression = self.span.solve(target)
        if expression is None:
            return None
        plan = self.decode_expression(expression)
        if initial_plan is not None:
            if (initial_plan.width != self.width
                    or initial_plan.evaluate_factored_functions(self.functions, self.full) != target):
                raise ValueError('The supplied initial representation is not certified on this codebook.')
            if initial_plan.and_count < plan.and_count:
                plan = initial_plan
        rng = random.Random(seed)
        for _ in range(trials):
            count = plan.and_count - 1
            if count <= 0:
                break
            # The current factorization supplies useful structured candidates;
            # independent random factors cover other subspaces reproducibly.
            if rng.randrange(3):
                factors = [item[rng.randrange(2)] for item in plan.products]
                rng.shuffle(factors)
                factors = factors[:count]
                if rng.randrange(2):
                    factors[rng.randrange(count)] = rng.getrandbits(self.width)
            else:
                factors = [rng.getrandbits(self.width) for _ in range(count)]
            columns = [self.full] + list(self.functions)
            left_functions = [parity_function(mask, self.functions) for mask in factors]
            columns += [left & right for left in left_functions for right in self.functions]
            solution = BinarySpan(columns).solve(target)
            if solution is None:
                continue
            constant = bool(solution & 1)
            linear = (solution >> 1) & ((1 << self.width) - 1)
            edge_set = set()
            for i, left in enumerate(factors):
                right = (solution >> (1 + self.width + i * self.width)) & ((1 << self.width)-1)
                for a in bits(left):
                    for b in bits(right):
                        if a == b:
                            linear ^= 1 << a
                        else:
                            edge = tuple(sorted((a, b)))
                            if edge in edge_set:
                                edge_set.remove(edge)
                            else:
                                edge_set.add(edge)
            candidate = factor_polynomial(self.width, constant, linear, edge_set)
            if candidate.and_count < plan.and_count:
                plan = candidate
        if (plan.evaluate_functions(self.functions, self.full) != target
                or plan.evaluate_factored_functions(self.functions, self.full) != target):
            raise AssertionError('Codebook synthesis certificate failed.')
        return plan

    def represent_kernel(self, target, *, trials=10000, seed=0, exhaustive=False):
        """Search the exact affine space of quadratic representations.

        Every nullspace vector is a polynomial vanishing on ALL codewords.
        Toggling it preserves the truth table. Alternating matrix rank divided
        by two equals the number of affine products for that representation.
        An exhaustive search is supported for small nullspaces; otherwise the
        result is explicitly a deterministic heuristic, with no optimality
        claim about representations not visited.
        """
        expression = self.span.solve(int(target))
        if expression is None:
            return None, {'status': 'not_quadratic_on_codebook'}
        relations = list(self.span.nullspace)
        rng = random.Random(seed)
        rng.shuffle(relations)
        width = self.width

        def adjacency(value):
            rows = [0]*width
            for index in bits(value):
                edge = self.monomials[index]
                if len(edge) == 2:
                    i, j = edge
                    rows[i] ^= 1 << j
                    rows[j] ^= 1 << i
            return rows

        def rank_below(matrix, limit):
            rows = list(matrix)
            remaining = (1 << width)-1
            products = 0
            while remaining:
                i = (remaining & -remaining).bit_length()-1
                remaining ^= 1 << i
                partners = rows[i] & remaining
                if not partners:
                    continue
                j = (partners & -partners).bit_length()-1
                remaining ^= 1 << j
                products += 1
                if products >= limit:
                    return products
                ri, rj = rows[i], rows[j]
                for k in bits(remaining):
                    old = rows[k]
                    if old >> j & 1:
                        rows[k] ^= ri
                    if old >> i & 1:
                        rows[k] ^= rj
            return products

        initial = self.decode_expression(expression)
        best, best_expression = initial.and_count, expression
        current = expression
        rows = adjacency(current)
        relation_rows = [adjacency(relation) for relation in relations]
        total = (1 << len(relations)) if exhaustive else min(trials, 1 << len(relations))
        examined = 1
        for step in range(1, total):
            if exhaustive:
                changed = (step & -step).bit_length()-1
            else:
                changed = rng.randrange(len(relations))
            current ^= relations[changed]
            delta = relation_rows[changed]
            rows = [row ^ change for row, change in zip(rows, delta)]
            score = rank_below(rows, best)
            examined += 1
            if score < best:
                best, best_expression = score, current
                if best == 0:
                    break
        plan = self.decode_expression(best_expression)
        if (plan.and_count != best
                or plan.evaluate_functions(self.functions, self.full) != int(target)
                or plan.evaluate_factored_functions(self.functions, self.full) != int(target)):
            raise AssertionError('Nullspace rank-search certificate failed.')
        return plan, {'status': 'PROVED' if exhaustive else 'certified_heuristic',
                      'representations_examined': examined,
                      'nullspace_dimension': len(relations),
                      'initial_products': initial.and_count,
                      'products': plan.and_count,
                      'optimal_among_quadratic_representations': bool(exhaustive)}

    def improve_preserving_kernel(self, plan, *, rounds=64, subspace_bits=9, seed=0):
        """Reduce a certified polynomial rank inside relation subspaces.

        Randomly retain part of the current alternating matrix's kernel. The
        nullspace of those linear constraints gives truth-table relations that
        preserve it. Exhausting a small deterministic subspace of those moves
        can find lower rank without randomizing away the current structure.
        This remains a heuristic, and every returned factorization is checked.
        """
        if plan.width != self.width:
            raise ValueError('Wrong polynomial width.')
        if not self.span.nullspace or plan.and_count == 0:
            return plan
        target = plan.evaluate_functions(self.functions, self.full)
        lookup = {monomial: i for i, monomial in enumerate(self.monomials)}
        current = int(plan.constant)
        for bit in bits(plan.linear):
            current ^= 1 << lookup[(bit,)]
        for edge in plan.edges:
            current ^= 1 << lookup[edge]
        width = self.width
        rng = random.Random(seed)

        def adjacency(expression):
            rows = [0]*width
            for index in bits(expression):
                monomial = self.monomials[index]
                if len(monomial) == 2:
                    a, b = monomial
                    rows[a] ^= 1 << b
                    rows[b] ^= 1 << a
            return rows

        def products_below(matrix, limit):
            rows = list(matrix)
            remaining, count = (1 << width)-1, 0
            while remaining:
                i = (remaining & -remaining).bit_length()-1
                remaining ^= 1 << i
                partners = rows[i] & remaining
                if not partners:
                    continue
                j = (partners & -partners).bit_length()-1
                remaining ^= 1 << j
                count += 1
                if count >= limit:
                    return count
                ri, rj = rows[i], rows[j]
                for k in bits(remaining):
                    old = rows[k]
                    if old >> j & 1:
                        rows[k] ^= ri
                    if old >> i & 1:
                        rows[k] ^= rj
            return count

        relations = list(self.span.nullspace)
        relation_matrices = [adjacency(relation) for relation in relations]
        best_count = plan.and_count
        for _ in range(rounds):
            matrix = adjacency(current)
            kernel = BinarySpan(matrix).nullspace
            if not kernel:
                break
            k = min(len(kernel), max(1, width//2))
            # An invertible random row frame makes the retained kernel
            # subspace independent of Gaussian elimination's coordinate order.
            mixed = list(kernel)
            for __ in range(3*len(mixed)):
                if len(mixed) < 2:
                    break
                a, b = rng.sample(range(len(mixed)), 2)
                mixed[a] ^= mixed[b]
            rng.shuffle(mixed)
            columns = []
            for relation_matrix in relation_matrices:
                column = 0
                for i, vector in enumerate(mixed[:k]):
                    product = sum(((row & vector).bit_count() & 1) << bit
                                  for bit, row in enumerate(relation_matrix))
                    column |= product << (width*i)
                columns.append(column)
            moves = []
            while k >= 1:
                mask = (1 << (width*k))-1
                moves = BinarySpan([column & mask for column in columns]).nullspace
                if len(moves) >= 3:
                    break
                k -= 1
            if not moves:
                continue
            if len(moves) > subspace_bits:
                # Choose a reproducible random small subspace of the allowed
                # relation moves, rather than only its first basis vectors.
                compressed, span = [], BinarySpan()
                while len(compressed) < subspace_bits:
                    coefficients = rng.getrandbits(len(moves))
                    if not coefficients or not span.add(coefficients):
                        continue
                    value = 0
                    for bit in bits(coefficients):
                        value ^= moves[bit]
                    compressed.append(value)
                moves = compressed
            deltas = []
            delta_rows = []
            for move in moves:
                expression = 0
                for bit in bits(move):
                    expression ^= relations[bit]
                deltas.append(expression)
                delta_rows.append(adjacency(expression))
            trial_expression, trial_rows = current, list(matrix)
            round_best, round_expression = best_count, current
            for step in range(1, 1 << len(moves)):
                changed = (step & -step).bit_length()-1
                trial_expression ^= deltas[changed]
                trial_rows = [row ^ delta for row, delta in zip(trial_rows, delta_rows[changed])]
                count = products_below(trial_rows, round_best)
                if count < round_best:
                    round_best, round_expression = count, trial_expression
            if round_best < best_count:
                best_count, current = round_best, round_expression
                if best_count == 0:
                    break
        result = self.decode_expression(current)
        if (result.and_count != best_count
                or result.evaluate_functions(self.functions, self.full) != target
                or result.evaluate_factored_functions(self.functions, self.full) != target):
            raise AssertionError('Kernel-preserving rank-search certificate failed.')
        return result


def emit_xor(builder, variables, target, plan):
    """Emit a factored decoder with zero additional qubits."""
    variables = list(variables)
    if len(variables) != plan.width or target in variables:
        raise ValueError('Distinct input and target wires are required.')
    if plan.constant:
        builder.x(target)
    for bit in bits(plan.product_linear):
        builder.cx(variables[bit], target)
    for left, right, i, j in plan.products:
        frame = [(variables[k], variables[i]) for k in bits(left) if k != i]
        frame += [(variables[k], variables[j]) for k in bits(right) if k != j]
        for a, b in frame:
            builder.cx(a, b)
        builder.ccx(variables[i], variables[j], target)
        for a, b in reversed(frame):
            builder.cx(a, b)


def emit_phase(builder, variables, outcome, plan):
    """Repay (-1)^(outcome * polynomial) using Clifford gates only."""
    variables = list(variables)
    if len(variables) != plan.width:
        raise ValueError('Wrong codebook wire count.')
    # A Z on a classical condition represents its deterministic branch sign.
    # Preserve this constant explicitly; it is part of exact branch equality.
    if plan.constant:
        builder.z(outcome)
    builder.push_condition(outcome)
    for bit in bits(plan.linear):
        builder.z(variables[bit])
    for i, j in plan.edges:
        builder.cz(variables[i], variables[j])
    builder.pop_condition()


def emit_erase(builder, variables, targets, plans):
    """Erase known codebook functions, exactly for all measurement outcomes.

    The retained variables must have the certified codebook values throughout.
    Targets are reset to zero but remain allocated for caller reuse.
    """
    variables, targets, plans = list(variables), list(targets), list(plans)
    if len(targets) != len(plans) or set(variables) & set(targets):
        raise ValueError('Erasure requires disjoint retained and target wires.')
    outcomes = builder.alloc_bits(len(targets))
    for target, outcome, plan in zip(targets, outcomes, plans):
        builder.hmr(target, outcome)
        emit_phase(builder, variables, outcome, plan)
    builder.free(outcomes)

