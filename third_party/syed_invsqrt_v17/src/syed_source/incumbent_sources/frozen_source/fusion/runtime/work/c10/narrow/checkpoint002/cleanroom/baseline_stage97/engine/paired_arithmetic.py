# Copyright 2026 Syed Asad Ali (team syed3000)
# SPDX-License-Identifier: Apache-2.0
"""Two-carry forward arithmetic with phase debts repaid during its inverse.

Only a compute/phase/uncompute pair is a complete operation.  A forward
adder intentionally retains classical records of signs caused by measuring
carry wires.  The inverse subtraction recomputes exactly the same Boolean
carry functions and pays those signs by conditional Z before applying its
ordinary, exact carry cleanup.
"""
from __future__ import annotations
from dataclasses import dataclass
import kickmix as km
from fusion.arithmetic import (_Frame, _compute_carry, _erase_carry,
                               _sum_keep_carry, _phase_borrow, partition)
from fusion.compiler import phase_quadratic, MAJORITY_TRUTH
from dirty_terminal import terminal_add, terminal_cost, terminal_dirty_count, dirty_mcz_cost


@dataclass
class CarryDebt:
    measurements: dict
    width: int
    consumed: bool = False


def _finish_top(builder, a, b, incoming, preserve):
    """Two high sum bits; the last carry goes directly into the high bit."""
    aa, bb = a[-2], b[-2]
    if aa == preserve and isinstance(incoming, km.q):
        builder.cx(aa, incoming)
        builder.cx(aa, bb)
        builder.cx(aa, b[-1])
        builder.ccx(incoming, bb, b[-1])
        builder.cx(aa, incoming)
        builder.cx(incoming, bb)
    elif aa is False:
        builder.ccx(incoming, bb, b[-1])
        builder.cx(incoming, bb)
    else:
        builder.cx(incoming, aa)
        builder.cx(incoming, bb)
        builder.cx(incoming, b[-1])
        builder.ccx(aa, bb, b[-1])
        builder.cx(incoming, aa)
        builder.cx(aa, bb)
    builder.cx(a[-1], b[-1])


def _inputs(source, target, carry_in, signed_source):
    source, target = list(source), list(target)
    width = len(target)
    source = source[:width]
    if any(not isinstance(q, km.q) for q in source):
        raise ValueError("Source must contain quantum wires.")
    if len(set(source+target)) != len(source)+len(target):
        raise ValueError("Source and target must be disjoint distinct wires.")
    if isinstance(carry_in, km.q) and carry_in in source+target:
        raise ValueError("Carry-in must be disjoint from the data words.")
    if carry_in is not False and not isinstance(carry_in, km.q):
        raise ValueError("Carry-in must be a quantum wire or False.")
    preserve = source[-1] if signed_source and source else None
    source += [preserve if preserve is not None else False]*(width-len(source))
    return source, target, preserve


def forward_add(builder, source, target, *, carry_in=False, signed_source=False):
    """target += source+carry_in, with two clean carries and deferred signs.

    The returned debt is mandatory: consume it in `inverse_add` after all
    changes to this target have been reversed.  Arbitrary diagonal phases
    and further reversible classical computation may intervene.
    """
    a, b, preserve = _inputs(source, target, carry_in, signed_source)
    width = len(b)
    debts = {}
    if not width:
        return CarryDebt(debts, width)
    if width == 1:
        builder.cx(a[0], b[0])
        builder.cx(carry_in, b[0])
        return CarryDebt(debts, width)

    def measure(carry, position):
        if carry is False:
            return
        outcome = builder.alloc_bits(1)[0]
        builder.hmr(carry, outcome)
        builder.free(carry)
        debts[position] = outcome

    carry = carry_in
    for index, (aa, bb) in enumerate(zip(a[:-2], b[:-2])):
        frame = _compute_carry(builder, aa, bb, carry, preserve=preserve)
        _sum_keep_carry(builder, frame)
        if index:
            measure(carry, index)
        carry = frame.outgoing
    _finish_top(builder, a, b, carry, preserve)
    if width > 2:
        measure(carry, width-2)
    return CarryDebt(debts, width)


def _segment_repay(builder, a, b, incoming, *, retain_outgoing, preserve,
                    start, debt, overflow_phase=None):
    def compute(aa, bb, carry, position):
        frame = _compute_carry(builder, aa, bb, carry, preserve=preserve)
        outcome = debt.measurements.pop(position, None)
        if outcome is not None:
            if frame.outgoing is not False:
                builder.push_condition(outcome)
                builder.z(frame.outgoing)
                builder.pop_condition()
            builder.free(outcome)
        return frame

    n = len(b)
    if retain_outgoing:
        frames, carry = [], incoming
        for index, (aa, bb) in enumerate(zip(a, b)):
            frame = compute(aa, bb, carry, start+index+1)
            frames.append(frame)
            carry = frame.outgoing
        _sum_keep_carry(builder, frames[-1])
        for frame in reversed(frames[:-1]):
            _erase_carry(builder, frame, write_sum=True)
        return carry
    if n == 1:
        if overflow_phase is not None:
            builder.push_condition(overflow_phase)
            phase_quadratic(builder, [a[0], b[0], incoming], MAJORITY_TRUTH)
            builder.pop_condition()
        builder.cx(a[0], b[0])
        builder.cx(incoming, b[0])
        return False
    frames, carry = [], incoming
    for index, (aa, bb) in enumerate(zip(a[:-2], b[:-2])):
        frame = compute(aa, bb, carry, start+index+1)
        frames.append(frame)
        carry = frame.outgoing
    if overflow_phase is not None:
        # The two high source bits are literal zero.  Their carry-out is
        # carry * b[-2] * b[-1] before the existing two-bit increment.
        # A classically conditioned CCZ pays that sign without workspace.
        if a[-2] is not False or a[-1] is not False:
            raise ValueError('Overflow phase currently requires two high source zeros.')
        builder.push_condition(overflow_phase)
        builder.ccz(carry, b[-2], b[-1])
        builder.pop_condition()
    _finish_top(builder, a, b, carry, preserve)
    for frame in reversed(frames):
        _erase_carry(builder, frame, write_sum=True)
    return False


def _terminal_partition(a, b, incoming, clean, external_dirty, *,
                        release_input=False, ordinary_final=False,
                        allow_dirty_terminal=True, overflow_phase=False):
    """Cost a no-clean final segment only when the ordinary partition fails.

    Earlier target bits have already received their final values and can be
    borrowed as arbitrary dirty workspace. All borrowed bits are restored
    before the boundary-carry phase comparators execute.
    """
    width = len(b)
    states = {(0,0):(0.0,())}
    candidates = []
    original_source = [wire for wire in a if isinstance(wire,km.q)]
    for used in range(clean+1+int(release_input)):
        for (start,count), (cost,sizes) in list(states.items()):
            if count != used:
                continue
            capacity=clean-used+int(release_input and used>0)
            release_cost=0.5 if release_input and used>0 else 0.0
            if ordinary_final and width-start<=capacity+2:
                phase_cost=0.5 if overflow_phase and width-start>=2 else 0.0
                candidates.append((cost+width-start-1+release_cost+phase_cost,
                                   sizes+(width-start,),None))
            tail = a[start:]
            real = next((i for i,wire in enumerate(tail) if wire is False),len(tail))
            prefix = tail[:real]
            distinct = len(set(prefix)) == len(prefix)
            unsigned = all(wire is False for wire in tail[real:])
            has_carry = isinstance(incoming,km.q) or any(wire is not False for wire in a[:start])
            if (allow_dirty_terminal and has_carry and distinct and unsigned
                    and (not overflow_phase or real<len(tail))):
                forbidden = set(prefix+b[start:])
                if not start and isinstance(incoming,km.q):
                    forbidden.add(incoming)
                pool = list(b[:start])+original_source+list(external_dirty)
                if start and isinstance(incoming,km.q) and not release_input:
                    pool.append(incoming)
                pool = list(dict.fromkeys(wire for wire in pool
                                          if isinstance(wire,km.q) and wire not in forbidden))
                needed = terminal_dirty_count(width-start,real)
                if len(pool) >= needed:
                    terminal = terminal_cost(width-start,real)
                    if overflow_phase:
                        terminal += 0.5*dirty_mcz_cost(width-start-real+1)
                    candidates.append((cost+terminal+release_cost,sizes+(width-start,),pool))
            if used == clean+int(release_input):
                continue
            for length in range(1,min(capacity,width-start-1)+1):
                key = (start+length,used+1)
                value = (cost+length+0.5*(length-1),sizes+(length,))
                if key not in states or value < states[key]:
                    states[key] = value
    if not candidates:
        raise ValueError(f'{width}-bit inverse adder has no valid {clean}-carry terminal partition.')
    cost,sizes,pool = min(candidates,key=lambda item:(item[0],item[1]))
    return list(sizes),pool


def inverse_add(builder, source, target, debt: CarryDebt, *, carry_in=False,
                signed_source=False, carry_budget=None, dirty_wires=(),
                carry_lifecycle=None, overflow_phase=None,
                allow_dirty_overflow=False):
    """Undo the matching forward add and repay every recorded carry phase.

    If overflow_phase is a classical bit, additionally phase the final
    borrow carry by (-1)**overflow_phase.  The supported multi-bit case has
    two literal high source zeros.  Its final borrow is a three-bit product
    already exposed at the ordinary two-bit terminal, so one conditioned
    CCZ suffices without an additional clean wire.  This optional mode
    excludes dirty terminal fallbacks by default.  The optional
    allow_dirty_overflow mode compares exact sparse terminals too, paying
    their final product phase with an independently proved dirty-MCZ echo.
    """
    a, b, preserve = _inputs(source, target, carry_in, signed_source)
    n = len(b)
    if overflow_phase is not None and (signed_source or
            (n>=2 and (a[-2] is not False or a[-1] is not False))):
        raise ValueError('Overflow-phase inverse needs an unsigned source with two high zeros.')
    if debt.width != n:
        raise ValueError("This carry debt belongs to a different adder width.")
    if debt.consumed:
        raise ValueError("This forward adder's phase debt has already been consumed.")
    debt.consumed = True
    if not n:
        return
    available = builder.max_qubits-builder.num_allocated_qubits
    desired = max(0, n-2) if carry_budget is None else carry_budget
    clean = int(min(available, desired, max(0, n-2)))
    terminal_dirty = None
    if carry_lifecycle is not None:
        if signed_source or not isinstance(carry_in,km.q):
            raise ValueError('Disposable incoming carry requires an unsigned quantum-carry adder.')
        sizes,terminal_dirty = _terminal_partition(a,b,carry_in,clean,dirty_wires,
                                                   release_input=True,ordinary_final=True,
                                                   allow_dirty_terminal=overflow_phase is None or allow_dirty_overflow,
                                                   overflow_phase=overflow_phase is not None and allow_dirty_overflow)
    elif overflow_phase is not None and allow_dirty_overflow:
        sizes,terminal_dirty = _terminal_partition(a,b,carry_in,clean,dirty_wires,
                                                   ordinary_final=True,overflow_phase=True)
    else:
        try:
            sizes = partition(n, clean)
        except ValueError:
            if signed_source or overflow_phase is not None:
                raise
            sizes,terminal_dirty = _terminal_partition(a,b,carry_in,clean,dirty_wires)
    builder.x(km.array(b))
    boundaries = []
    start, carry = 0, carry_in
    released_input=False
    for number, length in enumerate(sizes):
        aa, bb = a[start:start+length], b[start:start+length]
        retain = number+1 < len(sizes)
        if not retain and terminal_dirty is not None:
            terminal_add(builder,aa,bb,carry,dirty=terminal_dirty,debt=debt,start=start,
                         overflow_phase=overflow_phase)
            outgoing = False
        else:
            outgoing = _segment_repay(builder, aa, bb, carry, retain_outgoing=retain,
                                      preserve=preserve, start=start, debt=debt,
                                      overflow_phase=overflow_phase if not retain else None)
        if retain:
            recorded_incoming=carry
            if number==0 and carry_lifecycle is not None:
                carry_lifecycle[0](carry_in)
                recorded_incoming=None
                released_input=True
            boundaries.append((aa, bb, recorded_incoming, outgoing))
        carry = outgoing
        start += length
    for aa, bb, incoming, outgoing in reversed(boundaries):
        if outgoing is False:
            continue
        result = builder.alloc_bits(1)[0]
        builder.hmr(outgoing, result)
        builder.free(outgoing)
        builder.push_condition(result)
        recreated = incoming is None
        if recreated:
            incoming=carry_lifecycle[1]()
        _phase_borrow(builder, aa, bb, incoming, preserve=preserve)
        if recreated:
            carry_lifecycle[0](incoming)
        builder.pop_condition()
        builder.free(result)
    builder.x(km.array(b))
    if debt.measurements:
        raise AssertionError(f"Unpaid carry positions: {sorted(debt.measurements)}")
    return released_input


def _row_inputs(source, target, *, shift, nearest, signed_source):
    source, target = list(source), list(target)
    carry = False
    if shift >= 0:
        target = target[shift:]
    else:
        cut = -shift
        if signed_source and cut >= len(source):
            if nearest:
                return [], [], False
            source, cut = source[-1:], 0
        if nearest and cut-1 < len(source):
            carry = source[cut-1]
        source = source[cut:]
    if not target or (not source and carry is False):
        return [], [], False
    return source[:len(target)], target, carry


def forward_signed_row(builder, source, target, *, shift, sign,
                        nearest=True, signed_source=False):
    source, target, carry = _row_inputs(source, target, shift=shift,
                                       nearest=nearest, signed_source=signed_source)
    if isinstance(sign, km.q) and sign in source+target+([carry] if isinstance(carry, km.q) else []):
        raise ValueError("Sign must be disjoint from row operands and rounding bit.")
    for wire in target:
        builder.cx(sign, wire)
    debt = forward_add(builder, source, target, carry_in=carry,
                       signed_source=signed_source)
    for wire in target:
        builder.cx(sign, wire)
    return debt


def inverse_signed_row(builder, source, target, debt, *, shift, sign,
                        nearest=True, signed_source=False, carry_budget=None,
                        overflow_phase=None, allow_dirty_overflow=False):
    source, target, carry = _row_inputs(source, target, shift=shift,
                                       nearest=nearest, signed_source=signed_source)
    if isinstance(sign, km.q) and sign in source+target+([carry] if isinstance(carry, km.q) else []):
        raise ValueError("Sign must be disjoint from row operands and rounding bit.")
    for wire in target:
        builder.cx(sign, wire)
    inverse_add(builder, source, target, debt, carry_in=carry,
                signed_source=signed_source, carry_budget=carry_budget,
                overflow_phase=overflow_phase,allow_dirty_overflow=allow_dirty_overflow)
    for wire in target:
        builder.cx(sign, wire)


@dataclass
class DeferredProductToken:
    plan: object
    row_debts: list


def forward_growing_product(builder, residual, source, plan, *, initial=()):
    """Increasing-width product with only two forward carry temporaries."""
    residual, source = list(residual), list(source)
    accumulator = list(initial)
    if len(residual) != len(plan.shifts) or len(accumulator) != plan.initial_width:
        raise ValueError("Input widths do not match the growing-product plan.")
    debts = []
    for sign, shift, width in zip(residual, plan.shifts, plan.widths):
        if width > len(accumulator):
            more = list(builder.alloc_qubits(width-len(accumulator)))
            if accumulator:
                for wire in more:
                    builder.cx(accumulator[-1], wire)
            accumulator.extend(more)
        debt = forward_signed_row(builder, source, accumulator, shift=shift,
                                   sign=sign, nearest=plan.nearest,
                                   signed_source=plan.signed_source)
        debts.append(debt)
    return km.array(accumulator), DeferredProductToken(plan, debts)


def inverse_growing_product(builder, residual, source, accumulator, token, *,
                             carry_budget=None):
    """Repay row debts while reversing and shrinking the product word."""
    residual, source, accumulator = list(residual), list(source), list(accumulator)
    plan = token.plan
    for index in reversed(range(len(residual))):
        width = plan.widths[index]
        inverse_signed_row(builder, source, accumulator, token.row_debts[index],
                            shift=plan.shifts[index], sign=residual[index],
                            nearest=plan.nearest, signed_source=plan.signed_source,
                            carry_budget=carry_budget)
        previous = plan.widths[index-1] if index else plan.initial_width
        if previous < width:
            dead = accumulator[previous:]
            if previous:
                for wire in dead:
                    builder.cx(accumulator[previous-1], wire)
            builder.free(km.array(dead))
            accumulator = accumulator[:previous]
    return km.array(accumulator)


@dataclass
class DeferredBoundedToken:
    plan: object
    saved_bit: object
    window: int
    row_debts: list
    overflow_debt: object = None


def release_saved_bit(builder, saved):
    """Release a saved original bit; repay it after the original is restored."""
    outcome = builder.alloc_bits(1)[0]
    builder.hmr(saved, outcome)
    builder.free(saved)
    return outcome


def repay_saved_bit(builder, restored, outcome):
    """Cancel the release sign using the now-restored original bit."""
    builder.push_condition(outcome)
    builder.z(restored)
    builder.pop_condition()
    builder.free(outcome)


def _deferred_overflow(builder, residual, source, target, token, *,
                       inverse, carry_budget=None, overflow_phase=None,
                       allow_dirty_overflow=False):
    if token.saved_bit is None:
        return
    sigma = residual[token.plan.last-1]
    if token.plan.signed_source:
        builder.cx(source[-1], sigma)
    top, saved = target[token.window-1], token.saved_bit
    builder.cx(sigma, saved)
    builder.cx(sigma, top)
    builder.x(top)
    wrap = builder.alloc_qubits(1)[0]
    builder.ccx(saved, top, wrap)
    high = target[token.window:]
    for wire in high:
        builder.cx(sigma, wire)
    if inverse:
        inverse_add(builder, [], high, token.overflow_debt, carry_in=wrap,
                    carry_budget=carry_budget,dirty_wires=target[:token.window],
                    overflow_phase=overflow_phase,allow_dirty_overflow=allow_dirty_overflow)
    else:
        token.overflow_debt = forward_add(builder, [], high, carry_in=wrap)
    for wire in high:
        builder.cx(sigma, wire)
    builder.del_and(saved, top, wrap)
    builder.free(wrap)
    builder.x(top)
    builder.cx(sigma, top)
    builder.cx(sigma, saved)
    if token.plan.signed_source:
        builder.cx(source[-1], sigma)


def forward_bounded_rows(builder, residual, source, target, plan):
    """Bounded modular rows with deferred phases and two forward carries."""
    residual, source, target = list(residual), list(source), list(target)
    if len(residual) != plan.digits:
        raise ValueError("Residual width does not match the bounded-row plan.")
    width = min(plan.window, len(target))
    saved = None
    if 0 < width < len(target):
        saved = builder.alloc_qubits(1)[0]
        builder.cx(target[width-1], saved)
    token = DeferredBoundedToken(plan, saved, width, [])
    if width:
        for index, shift in zip(range(plan.first, plan.last), plan.shifts):
            token.row_debts.append(forward_signed_row(
                builder, source, target[:width], shift=shift, sign=residual[index],
                signed_source=plan.signed_source))
        _deferred_overflow(builder, residual, source, target, token, inverse=False)
    return token


def inverse_bounded_rows(builder, residual, source, target, token, *, carry_budget=None):
    """Reverse bounded rows, repaying the recorded signs before releasing them."""
    residual, source, target = list(residual), list(source), list(target)
    plan = token.plan
    saved_debt = None
    if token.window:
        _deferred_overflow(builder, residual, source, target, token, inverse=True,
                           carry_budget=carry_budget)
        # The old window MSB was only needed to undo the high correction.
        # Its value will reappear after reversing the low rows, so release
        # it now and use the extra quantum wire for their carry workspace.
        if token.saved_bit is not None:
            saved_debt = release_saved_bit(builder, token.saved_bit)
        for j in reversed(range(plan.last-plan.first)):
            index, shift = plan.first+j, plan.shifts[j]
            inverse_signed_row(builder, source, target[:token.window], token.row_debts[j],
                                shift=shift, sign=residual[index],
                                signed_source=plan.signed_source, carry_budget=carry_budget)
    if saved_debt is not None:
        repay_saved_bit(builder, target[token.window-1], saved_debt)
