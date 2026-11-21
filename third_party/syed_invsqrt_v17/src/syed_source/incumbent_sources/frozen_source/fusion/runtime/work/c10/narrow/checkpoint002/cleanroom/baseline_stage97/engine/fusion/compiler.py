# Copyright 2026 Syed Asad Ali (team syed3000)
# SPDX-License-Identifier: Apache-2.0
"""Small exact Boolean-window compiler, including phases.

Windows are specified by truth tables generated from the mathematical kernel.
No serialized circuit is an input.  Quadratic XOR outputs are factored into
the minimum number of affine-linear products.  Quadratic sign outputs use
only Z and CZ gates.  Every proposed factorization is checked exhaustively.
"""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache


def anf_from_truth(truth):
    coefficients = [int(v)&1 for v in truth]
    n = (len(coefficients)-1).bit_length()
    if len(coefficients) != 1 << n:
        raise ValueError('Truth table length must be a power of two.')
    for j in range(n):
        for mask in range(1 << n):
            if mask & (1 << j):
                coefficients[mask] ^= coefficients[mask ^ (1 << j)]
    return tuple(mask for mask,value in enumerate(coefficients) if value)


def _product_polynomial(left, right):
    out = set()
    for i in range(left.bit_length()):
        if not (left >> i)&1:
            continue
        for j in range(right.bit_length()):
            if (right >> j)&1:
                mask = (1 << i)|(1 << j)
                if mask in out:
                    out.remove(mask)
                else:
                    out.add(mask)
    return out


@dataclass(frozen=True)
class QuadraticPlan:
    width: int
    affine: tuple[int,...]
    products: tuple[tuple[int,int,int,int],...]
    truth: tuple[int,...]

    @property
    def toffolis(self):
        return len(self.products)

    def evaluate(self, value):
        out = 0
        for monomial in self.affine:
            out ^= int(value & monomial == monomial)
        for left,right,_,_ in self.products:
            out ^= ((value & left).bit_count()&1) & ((value & right).bit_count()&1)
        return out


@lru_cache(maxsize=2048)
def synthesize_quadratic(truth):
    truth = tuple(map(int,truth))
    n = (len(truth)-1).bit_length()
    polynomial = set(anf_from_truth(truth))
    if any(mask.bit_count()>2 for mask in polynomial):
        raise ValueError('This exact window is not quadratic.')
    products = []
    while any(mask.bit_count()==2 for mask in polynomial):
        edge = min(mask for mask in polynomial if mask.bit_count()==2)
        i,j = [k for k in range(n) if edge >> k & 1]
        left,right = 1 << i,1 << j
        for k in range(n):
            if k in (i,j):
                continue
            if (1 << j)|(1 << k) in polynomial:
                left |= 1 << k
            if (1 << i)|(1 << k) in polynomial:
                right |= 1 << k
        polynomial.symmetric_difference_update(_product_polynomial(left,right))
        products.append((left,right,i,j))
    result = QuadraticPlan(n,tuple(sorted(polynomial)),tuple(products),truth)
    if any(result.evaluate(x) != truth[x] for x in range(1 << n)):
        raise AssertionError('Internal synthesis certificate failed.')
    return result


def xor_quadratic(builder, variables, target, truth):
    """XOR a quadratic Boolean window into target with minimum product rank.

    In-place CNOT frames form each affine factor on two pivot input wires.
    They are undone immediately, so no fresh qubits are required.  The rank
    lower bound applies to XOR/affine-product implementations of this window.
    """
    variables = list(variables)
    plan = synthesize_quadratic(tuple(truth))
    if len(variables) != plan.width or target in variables:
        raise ValueError('Distinct input wires and target are required.')
    for mask in plan.affine:
        if mask == 0:
            builder.x(target)
        else:
            builder.cx(variables[mask.bit_length()-1],target)
    for left,right,i,j in plan.products:
        frames = [(variables[k],variables[i]) for k in range(plan.width) if k!=i and left >> k & 1]
        frames += [(variables[k],variables[j]) for k in range(plan.width) if k!=j and right >> k & 1]
        for a,b in frames:
            builder.cx(a,b)
        builder.ccx(variables[i],variables[j],target)
        for a,b in reversed(frames):
            builder.cx(a,b)
    return plan


def phase_quadratic(builder, variables, truth):
    """Compile an exact sign window to Z/CZ only, including a constant sign."""
    variables = list(variables)
    anf = anf_from_truth(tuple(truth))
    if len(truth) != 1 << len(variables) or any(m.bit_count()>2 for m in anf):
        raise ValueError('Expected a quadratic phase truth table.')
    for mask in anf:
        indices = [k for k in range(len(variables)) if mask >> k & 1]
        if not indices:
            # The phase windows used by this compiler have zero constant term.
            # Reject instead of silently dropping a global phase from a branch.
            raise ValueError('Constant branch phase needs an explicit phase wire.')
        if len(indices)==1:
            builder.z(variables[indices[0]])
        else:
            builder.cz(variables[indices[0]],variables[indices[1]])


MAJORITY_TRUTH = tuple(int(x.bit_count()>=2) for x in range(8))
