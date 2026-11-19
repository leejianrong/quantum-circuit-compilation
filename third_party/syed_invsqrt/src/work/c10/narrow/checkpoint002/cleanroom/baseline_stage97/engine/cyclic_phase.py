# Copyright 2026 Syed Asad Ali (team syed3000)
# SPDX-License-Identifier: Apache-2.0
"""Unsigned scaled phase by cyclic rotation, with no shift-padding register.

For a W-bit unsigned value v and any nonnegative k,

    2**k*v = r + (2**W-1)*sum(2**j*r[j mod W] for j in range(k)),
    r = ROL_W(v,k mod W).

This needs W ordinary bit rotations and at most max_k extra rotations on
AND(bit[j], k>j).  The bit routing is a cyclic permutation of the original
word.  Its width is W rather than W+max_k.  Comparator windows are compiled
from their mathematical truth functions on the certified k range.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
import itertools
import math

import kickmix as km
from quadratic_terms import compile_polynomial, xor_polynomial


def _monomials(width, degree):
    return tuple(mask for mask in range(1 << width) if mask.bit_count() <= degree)


def _truth_of_terms(terms, size):
    return sum((sum(int(value & term == term) for term in terms)&1) << value
               for value in range(size))


def _restricted_anf(truth, max_value):
    """ANF on the downward-closed domain 0..max_value, with zero unused terms."""
    values = [(truth >> value)&1 for value in range(16)]
    for bit in range(4):
        for mask in range(16):
            if mask >> bit & 1:
                values[mask] ^= values[mask ^ (1 << bit)]
    terms = tuple(mask for mask, coefficient in enumerate(values)
                  if coefficient and mask <= max_value)
    full = (1 << (max_value+1))-1
    if _truth_of_terms(terms, max_value+1) != truth & full:
        raise AssertionError("Range-restricted ANF certificate failed.")
    return terms


def _span_solution(columns, target):
    pivots, null = {}, []
    for index, column in enumerate(columns):
        value, expression = column, 1 << index
        while value:
            bit = value.bit_length()-1
            if bit not in pivots:
                pivots[bit] = (value, expression)
                break
            old, old_expression = pivots[bit]
            value ^= old
            expression ^= old_expression
        if not value:
            null.append(expression)
    value, expression = target, 0
    while value:
        bit = value.bit_length()-1
        if bit not in pivots:
            return None, ()
        old, old_expression = pivots[bit]
        value ^= old
        expression ^= old_expression
    return expression, tuple(null)


@dataclass(frozen=True)
class ThresholdPlan:
    threshold: int
    max_k: int
    truth: int
    phase_terms: tuple[int, ...]
    helper_terms: tuple[int, ...] | None
    output_terms: tuple[int, ...]
    products: int


@lru_cache(maxsize=16)
def _helper_candidates(max_k):
    """Every distinct one-product quadratic helper on the valid flag domain."""
    monomials = tuple(mask for mask in _monomials(4, 2) if mask and mask <= max_k)
    best = {}
    for selection in range(1 << len(monomials)):
        terms = tuple(mask for i, mask in enumerate(monomials) if selection >> i & 1)
        plan = compile_polynomial(4, terms)
        if len(plan.products) != 1:
            continue
        truth = _truth_of_terms(terms, max_k+1)
        key = (len(terms), terms)
        if truth not in best or key < best[truth][0]:
            best[truth] = (key, terms)
    return tuple((truth, item[1]) for truth, item in
                 sorted(best.items(), key=lambda item: (item[1][0], item[0])))


@lru_cache(maxsize=128)
def threshold_plan(threshold, max_k=10):
    """Compile [k>=threshold] with exact truth/ANF certificates.

    The valid range max_k<=10 admits degree<=3 with only one possible cubic
    monomial.  Quadratic comparators use a minimum product-rank realization.
    Cubic comparators are exhaustively searched for a one-product helper and
    one-product final expression.  Two products are then optimal because a
    one-product XOR/affine circuit cannot contain a cubic term.
    """
    threshold, max_k = int(threshold), int(max_k)
    if not 0 <= max_k <= 10 or not 1 <= threshold <= max_k:
        raise ValueError("Expected 1<=threshold<=max_k<=10.")
    size, full = max_k+1, (1 << (max_k+1))-1
    truth = sum(int(k >= threshold) << k for k in range(size))
    phase_terms = _restricted_anf(truth, max_k)
    if max((term.bit_count() for term in phase_terms), default=0) <= 2:
        plan = compile_polynomial(4, phase_terms)
        return ThresholdPlan(threshold, max_k, truth, phase_terms, None,
                              phase_terms, len(plan.products))
    flags = [sum(((k >> bit)&1) << k for k in range(size)) for bit in range(4)]
    monomials = _monomials(5, 2)
    for helper_truth, helper_terms in _helper_candidates(max_k):
        variables = flags+[helper_truth]
        columns = []
        for term in monomials:
            column = full
            for bit in range(5):
                if term >> bit & 1:
                    column &= variables[bit]
            columns.append(column)
        expression, null = _span_solution(columns, truth)
        if expression is None:
            continue
        previous_gray, current = 0, expression
        for selection in range(1 << len(null)):
            gray = selection ^ (selection >> 1)
            changed = gray ^ previous_gray
            if changed:
                current ^= null[changed.bit_length()-1]
            previous_gray = gray
            terms = tuple(term for i, term in enumerate(monomials) if current >> i & 1)
            output = compile_polynomial(5, terms)
            if len(output.products) > 1:
                continue
            actual = 0
            for term in terms:
                column = full
                for bit in range(5):
                    if term >> bit & 1:
                        column &= variables[bit]
                actual ^= column
            if actual != truth:
                raise AssertionError("Threshold synthesis truth certificate failed.")
            return ThresholdPlan(threshold, max_k, truth, phase_terms,
                                  helper_terms, terms, 1+len(output.products))
    raise ValueError("No two-product comparator was found in the exhaustive helper search.")


def _erase_polynomial(builder, target, variables, terms):
    """Measure a degree<=3 function and repay its entire sign, constants too."""
    outcome = builder.alloc_bits(1)[0]
    builder.hmr(target, outcome)
    builder.free(target)
    if 0 in terms:
        builder.z(outcome)
    builder.push_condition(outcome)
    for term in terms:
        bits = [variables[i] for i in range(len(variables)) if term >> i & 1]
        if len(bits) == 1:
            builder.z(bits[0])
        elif len(bits) == 2:
            builder.cz(*bits)
        elif len(bits) == 3:
            builder.ccz(*bits)
        elif len(bits) > 3:
            raise ValueError("This cleanup accepts degree at most three.")
    builder.pop_condition()
    builder.free(outcome)


@contextmanager
def threshold_control(builder, flags, threshold, *, max_k=10, compact=None):
    """Expose a comparator bit using at most two quantum helper wires.

    The caller may use one additional AND temporary.  When three free wires
    are available, retaining the comparator's helper avoids all CCZ cleanup.
    With only two free wires, a cubic comparator releases its helper early
    and repays its one cubic phase term on the HMR-one branch.
    """
    flags = list(flags)
    if len(flags) != 4 or len(set(flags)) != 4:
        raise ValueError("Four distinct binary shift flags are required.")
    plan = threshold_plan(threshold, max_k)
    if not plan.products:
        # Pure affine comparator: form it directly on a pivot flag and undo
        # the Clifford frame after use, rather than allocating a target.
        linear = [term.bit_length()-1 for term in plan.output_terms if term]
        if not linear:
            yield bool(0 in plan.output_terms), plan, False
            return
        pivot, other = flags[linear[0]], [flags[i] for i in linear[1:]]
        for wire in other:
            builder.cx(wire, pivot)
        if 0 in plan.output_terms:
            builder.x(pivot)
        try:
            yield pivot, plan, False
        finally:
            if 0 in plan.output_terms:
                builder.x(pivot)
            for wire in reversed(other):
                builder.cx(wire, pivot)
        return
    available = builder.max_qubits-builder.num_allocated_qubits
    compact = available < 3 if compact is None else bool(compact)
    helper = None
    variables = list(flags)
    if plan.helper_terms is not None:
        helper = builder.alloc_qubits(1)[0]
        xor_polynomial(builder, flags, helper, plan.helper_terms)
        variables.append(helper)
    target = builder.alloc_qubits(1)[0]
    xor_polynomial(builder, variables, target, plan.output_terms)
    if helper is not None and compact:
        _erase_polynomial(builder, helper, flags, plan.helper_terms)
        helper = None
    try:
        yield target, plan, bool(plan.helper_terms is not None and compact)
    finally:
        if helper is None:
            _erase_polynomial(builder, target, flags, plan.phase_terms)
        else:
            _erase_polynomial(builder, target, variables, plan.output_terms)
            _erase_polynomial(builder, helper, flags, plan.helper_terms)


def rotation_pairs(width, amount):
    """A minimal-SWAP cycle decomposition of left rotation by amount."""
    amount %= width
    visited, pairs = set(), []
    for start in range(width):
        if start in visited:
            continue
        cycle, at = [], start
        while at not in visited:
            visited.add(at)
            cycle.append(at)
            at = (at+amount) % width
        pairs += [(start, other) for other in cycle[1:]]
    if len(pairs) != width-math.gcd(width, amount):
        raise AssertionError("Rotation cycle-count certificate failed.")
    return tuple(pairs)


def _pow2(exponent):
    return Fraction(1 << exponent) if exponent >= 0 else Fraction(1, 1 << -exponent)


def cyclic_scale_phase(builder, value, flags, fractional_bits, *, beta=1,
                        source_width=None, compact_thresholds=None,
                        turn_offsets=None, complement_overflow=False):
    """Apply beta*unsigned(value)*2**k/2**fractional_bits turns exactly.

    Requires four binary flag wires and certified 0<=k<=max_k<=10.
    `source_width` may certify initially zero high padding within the W-bit
    word; this prunes the corresponding impossible overflow terms. All
    value and flag wires are restored and all helpers return to zero.

    `turn_offsets` is an optional sequence of W+max_k exact rational values:
    first the W ordinary bit features, then the max_k overflow features.
    Each value is an additive phase in turns, independently of beta. Use
    Fraction objects, integers, or exact Fraction strings; floating-point
    offsets are rejected. Any pruned, known-zero feature must have offset
    zero. These offsets deliberately change the numerical phase function;
    its model-level approximation must be verified separately.

    With `complement_overflow=True`, each overflow feature is instead
    bit[j mod W] AND [k<j+padding+1]. Its mathematical angle is negated and
    its former angle is added to that bit's baseline. This is an exact
    change of phase basis. For W8/K10/F18 it turns three baseline angles
    into S, Z, and T, leaving fifteen generic rotations. Fitted offsets
    refer to the selected basis; keep those three offsets zero to retain
    the synthesis saving.

    For an originally signed W-bit low word, the caller can flip its top bit
    around this function and decrease the earlier coarse anchor by one unit
    of 2**(W-1). That conversion must be made in both parts of the design.
    """
    range_bound = getattr(flags, "max_k", None)
    value, flags = list(value), list(flags)
    width = len(value)
    max_k = 10 if range_bound is None else int(range_bound)
    source_width = width if source_width is None else int(source_width)
    if len(flags) != 4 or not 0 < source_width <= width or not 0 <= max_k <= 10:
        raise ValueError("Requires four flags and 0<source_width<=W with max_k<=10.")
    if len(set(value+flags)) != width+4:
        raise ValueError("Phase word and flags must use distinct wires.")
    beta = Fraction(beta)
    if turn_offsets is None:
        offsets = (Fraction(0),)*(width+max_k)
    else:
        entries = tuple(turn_offsets)
        if len(entries) != width+max_k:
            raise ValueError(f"Expected {width+max_k} turn offsets in base/overflow order.")
        if any(isinstance(entry, float) for entry in entries):
            raise TypeError("Frozen turn offsets must be exact rationals, not floats.")
        offsets = tuple(Fraction(entry) for entry in entries)
    ordinary_count = min(width, source_width+max_k)
    padding = width-source_width
    overflow_count = max(0, max_k-padding)
    if any(offsets[ordinary_count:width]) or any(offsets[width+overflow_count:]):
        raise ValueError("Pruned, known-zero phase features must have zero offsets.")
    routing = []
    swaps = 0
    for bit in reversed(range(4)):
        amount = 1 << bit
        if amount > max_k:
            continue
        pairs = rotation_pairs(width, amount)
        for a, b in pairs:
            builder.cswap(flags[bit], value[a], value[b])
        routing.append((flags[bit], pairs))
        swaps += len(pairs)
    ordinary = []
    mathematical_base=[beta*_pow2(bit-fractional_bits+1) for bit in range(width)]
    mathematical_overflow=[beta*((1 << width)-1)*_pow2(bit-fractional_bits+1)
                            for bit in range(overflow_count)]
    if complement_overflow:
        for bit,angle in enumerate(mathematical_overflow):
            mathematical_base[bit % width]+=angle
    # No initially nonzero bit can reach positions >=source_width+max_k
    # if the combined range is shorter than the cyclic word.
    for bit in range(ordinary_count):
        angle = mathematical_base[bit]+2*offsets[bit]
        builder.z_pow(value[bit], angle)
        ordinary.append(angle)
    corrections = []
    products, conditioned_ccz = 0, 0
    for bit in range(overflow_count):
        threshold = bit+padding+1
        with threshold_control(builder, flags, threshold, max_k=max_k,
                               compact=compact_thresholds) as (control, plan, compact_used):
            if complement_overflow:
                builder.x(control)
            temporary = builder.alloc_qubits(1)[0]
            builder.ccx(control, value[bit % width], temporary)
            angle = mathematical_overflow[bit]*(-1 if complement_overflow else 1)+2*offsets[width+bit]
            builder.z_pow(temporary, angle)
            builder.del_and(control, value[bit % width], temporary)
            builder.free(temporary)
            if complement_overflow:
                builder.x(control)
            corrections.append(angle)
            products += plan.products+1
            conditioned_ccz += int(compact_used)*sum(term.bit_count() == 3 for term in plan.phase_terms)
    for flag, pairs in reversed(routing):
        for a, b in reversed(pairs):
            builder.cswap(flag, value[a], value[b])
    return dict(width=width, max_k=max_k, source_width=source_width,
                complement_overflow=bool(complement_overflow),
                cswaps=2*swaps, comparator_and_products=products,
                hmr_conditioned_ccz=conditioned_ccz,
                expected_toffolis=2*swaps+products+conditioned_ccz/2,
                z_pow_calls=len(ordinary)+len(corrections),
                half_turn_angles=[str(angle) for angle in ordinary+corrections],
                turn_offsets=[str(offset) for offset in offsets])
