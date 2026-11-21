# Copyright 2026 Syed Asad Ali (team syed3000)
# SPDX-License-Identifier: Apache-2.0
"""Segmented measurement-carry addition, derived for this generator.

A carry boundary is kept while the interior carries of a segment are erased.
After every sum bit is final, the boundary is measured and the resulting sign
is repaid by a borrow comparator in the measurement-one branch.  The identity
is carry(a+b+c) = borrow((a+b+c) mod 2**n - a - c).

Only the comparator's interior carries are computed.  Its last carry is phased
by the exact quadratic identity majority(a,b,c) = ab XOR ac XOR bc, so that
last step needs only CZ gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
import kickmix as km
from .compiler import phase_quadratic, MAJORITY_TRUTH


@dataclass
class _Frame:
    a: object
    b: object
    incoming: object
    outgoing: object
    preserve_sign: bool = False


def _as_array(wires):
    return km.array(list(wires))


def _compute_carry(builder, a, b, incoming, *, preserve=None):
    if a is False and incoming is False:
        return _Frame(a, b, incoming, False)
    outgoing = builder.alloc_qubits(1)[0]
    if a is False:
        builder.ccx(incoming, b, outgoing)
    elif a == preserve and isinstance(incoming, km.q):
        builder.cx(a, incoming)
        builder.cx(a, b)
        builder.ccx(incoming, b, outgoing)
        builder.cx(a, outgoing)
        return _Frame(a, b, incoming, outgoing, True)
    else:
        builder.cx(incoming, a)
        builder.cx(incoming, b)
        builder.ccx(a, b, outgoing)
        builder.cx(incoming, outgoing)
    return _Frame(a, b, incoming, outgoing)


def _erase_carry(builder, frame, *, write_sum):
    a, b, incoming, outgoing = frame.a, frame.b, frame.incoming, frame.outgoing
    if outgoing is False:
        return
    if frame.preserve_sign:
        builder.cx(a, outgoing)
        builder.del_and(incoming, b, outgoing)
        builder.cx(a, incoming)
        builder.cx(incoming if write_sum else a, b)
    elif a is False:
        builder.del_and(incoming, b, outgoing)
        if write_sum:
            builder.cx(incoming, b)
    else:
        builder.cx(incoming, outgoing)
        builder.del_and(a, b, outgoing)
        builder.cx(incoming, a)
        if write_sum:
            builder.cx(a, b)
        else:
            builder.cx(incoming, b)
    builder.free(outgoing)


def _sum_keep_carry(builder, frame):
    if frame.preserve_sign:
        builder.cx(frame.a, frame.incoming)
        builder.cx(frame.incoming, frame.b)
    elif frame.a is False:
        builder.cx(frame.incoming, frame.b)
    else:
        builder.cx(frame.incoming, frame.a)
        builder.cx(frame.a, frame.b)


def _segment(builder, a, b, incoming, *, retain_outgoing, preserve=None):
    n = len(b)
    if retain_outgoing:
        frames = []
        carry = incoming
        for aa, bb in zip(a, b):
            frame = _compute_carry(builder, aa, bb, carry, preserve=preserve)
            frames.append(frame)
            carry = frame.outgoing
        _sum_keep_carry(builder, frames[-1])
        for frame in reversed(frames[:-1]):
            _erase_carry(builder, frame, write_sum=True)
        return carry
    if n == 1:
        builder.cx(a[0], b[0])
        builder.cx(incoming, b[0])
        return False
    frames = []
    carry = incoming
    for aa, bb in zip(a[:-2], b[:-2]):
        frame = _compute_carry(builder, aa, bb, carry, preserve=preserve)
        frames.append(frame)
        carry = frame.outgoing
    aa, bb = a[-2], b[-2]
    if aa == preserve and isinstance(carry, km.q):
        builder.cx(aa, carry)
        builder.cx(aa, bb)
        builder.cx(aa, b[-1])
        builder.ccx(carry, bb, b[-1])
        builder.cx(aa, carry)
        builder.cx(carry, bb)
    elif aa is False:
        builder.ccx(carry, bb, b[-1])
        builder.cx(carry, bb)
    else:
        builder.cx(carry, aa)
        builder.cx(carry, bb)
        builder.cx(carry, b[-1])
        builder.ccx(aa, bb, b[-1])
        builder.cx(carry, aa)
        builder.cx(aa, bb)
    builder.cx(a[-1], b[-1])
    for frame in reversed(frames):
        _erase_carry(builder, frame, write_sum=True)
    return False


def _phase_carry(builder, a, b, incoming, *, preserve=None):
    """Apply (-1)**carry_out(a+b+incoming), restoring all operands."""
    frames = []
    carry = incoming
    for aa, bb in zip(a[:-1], b[:-1]):
        frame = _compute_carry(builder, aa, bb, carry, preserve=preserve)
        frames.append(frame)
        carry = frame.outgoing
    # A majority is a quadratic Boolean form.  This is exact even with
    # coherent superpositions and never costs a three-control phase gate.
    phase_quadratic(builder, [a[-1], b[-1], carry], MAJORITY_TRUTH)
    for frame in reversed(frames):
        _erase_carry(builder, frame, write_sum=False)


def _phase_borrow(builder, a, final_sum, incoming, *, preserve=None):
    # The borrow recurrence for s-a-c is majority(a, NOT s, c).
    builder.x(_as_array(final_sum))
    _phase_carry(builder, a, final_sum, incoming, preserve=preserve)
    builder.x(_as_array(final_sum))


def partition(width: int, clean: int) -> list[int]:
    """Choose deterministic segment sizes without exceeding ``clean`` wires.

    Earlier segments keep one carry each.  A nonfinal segment of length l
    needs l fresh carries; the final segment needs only max(0,l-2), because
    the last carry goes directly into the target's most significant bit.
    """
    if width <= 0:
        return []
    if clean < 0:
        raise ValueError('clean must be nonnegative.')
    if width <= clean + 2:
        return [width]
    for boundaries in range(1, clean + 1):
        final = clean - boundaries + 2
        capacity = sum(clean-j for j in range(boundaries)) + final
        if capacity < width:
            continue
        remaining = width - final
        sizes = []
        for j in range(boundaries):
            length = min(clean-j, remaining-(boundaries-j-1))
            if length <= 0:
                break
            sizes.append(length)
            remaining -= length
        if len(sizes) == boundaries and remaining == 0:
            return sizes + [final]
    raise ValueError(f'{width}-bit segmented adder needs more than {clean} clean carry wires.')


def add(builder: km.CircuitBuilder, source: Sequence, target: Sequence,
        *, carry_in=False, subtract: bool = False, signed_source: bool = False,
        carry_budget: int | None = None) -> None:
    """target += (+/-)(source+carry_in), with zero extension and clean erasure.

    All source wires, including carry_in, are preserved.  Source bits may be
    shorter than target; omitted high bits are zero, with no physical padding.
    With signed_source=True, high source positions reuse the actual sign
    wire.  An alternate majority frame preserves that shared wire throughout.
    carry_in can be a quantum bit or False.  Subtraction subtracts both terms.

    With n ordinary source bits and k carry wires, the expected Toffoli count
    is n-1 + max(0,n-2-k)/2 whenever ``partition(n,k)`` exists.  Literal zero
    bits and compile-time carry values can make actual cost lower.  All
    measurement outcomes have identical data outputs and identical phase.
    """
    source, target = list(source), list(target)
    n = len(target)
    if not n:
        return
    source = source[:n]
    if any(not isinstance(q, km.q) for q in source):
        raise ValueError('Source must contain quantum wires; high zeros are implicit.')
    if len(set(source + target)) != len(source) + len(target):
        raise ValueError('Source and target must be disjoint distinct wires.')
    if isinstance(carry_in, km.q) and carry_in in source + target:
        raise ValueError('carry_in must be disjoint from source and target.')
    if carry_in is not False and not isinstance(carry_in, km.q):
        raise ValueError('carry_in must be a quantum wire or False.')
    available = builder.max_qubits - builder.num_allocated_qubits
    desired = max(0, n-2) if carry_budget is None else carry_budget
    clean = int(min(available, desired, max(0,n-2)))
    sizes = partition(n, clean)
    preserve = source[-1] if signed_source and source else None
    source += [preserve if preserve is not None else False] * (n-len(source))
    if subtract:
        builder.x(_as_array(target))
    boundaries = []
    start = 0
    carry = carry_in
    for number, length in enumerate(sizes):
        aa, bb = source[start:start+length], target[start:start+length]
        retain = number + 1 < len(sizes)
        outgoing = _segment(builder, aa, bb, carry, retain_outgoing=retain, preserve=preserve)
        if retain:
            boundaries.append((aa, bb, carry, outgoing))
        carry = outgoing
        start += length
    for aa, bb, incoming, outgoing in reversed(boundaries):
        if outgoing is False:
            continue
        result = builder.alloc_bits(1)[0]
        builder.hmr(outgoing, result)
        builder.free(outgoing)  # X measurement reset it, so reuse is exact.
        builder.push_condition(result)
        _phase_borrow(builder, aa, bb, incoming, preserve=preserve)
        builder.pop_condition()
        builder.free(result)
    if subtract:
        builder.x(_as_array(target))


def signed_row(builder: km.CircuitBuilder, source: Sequence, target: Sequence,
               *, shift: int, sign, inverse: bool = False,
               nearest: bool = False, signed_source: bool = False, carry_budget: int | None = None) -> None:
    """Add (1-2sign)*scaled_source, with optional rounding before the sign.

    At negative shift -s, nearest uses exactly (source>>s)+bit(source,s-1).
    With signed_source=True the shift is arithmetic.  Ties round toward
    positive infinity for both signs.  The discarded rounding
    bit is the carry-in of the adder; it costs no additional quantum wire and
    no additional carry product versus the corresponding full-width addition.
    """
    source, target = list(source), list(target)
    carry = False
    if shift >= 0:
        target = target[shift:]
    else:
        cut = -shift
        if signed_source and cut >= len(source):
            if nearest:
                return
            source = source[-1:]
            cut = 0
        if nearest and cut-1 < len(source):
            carry = source[cut-1]
        source = source[cut:]
    if not target or (not source and carry is False):
        return
    source = source[:len(target)]
    if isinstance(sign, km.q) and sign in source + target + ([carry] if isinstance(carry, km.q) else []):
        raise ValueError('Sign must be disjoint from row data and rounding bit.')
    for q in target:
        builder.cx(sign, q)
    add(builder, source, target, carry_in=carry,
        subtract=inverse, signed_source=signed_source, carry_budget=carry_budget)
    for q in target:
        builder.cx(sign, q)


def horner_rows(builder, residual, source, target, *, source_fraction,
                target_fraction, inverse=False, nearest=None, rounding="floor", signed_source=False, carry_budget=None):
    if rounding not in ("floor", "nearest"):
        raise ValueError("rounding must be floor or nearest")
    if nearest is None:
        nearest = rounding == "nearest"
    residual = list(residual)
    indices = reversed(range(len(residual))) if inverse else range(len(residual))
    for i in indices:
        signed_row(builder, source, target,
                   shift=i-len(residual)-1+target_fraction-source_fraction,
                   sign=residual[i], inverse=inverse, nearest=nearest, signed_source=signed_source,
                   carry_budget=carry_budget)
