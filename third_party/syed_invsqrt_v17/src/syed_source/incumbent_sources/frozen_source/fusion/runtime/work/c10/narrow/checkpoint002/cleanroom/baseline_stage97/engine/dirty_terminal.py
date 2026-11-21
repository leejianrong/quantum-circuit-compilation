# Copyright 2026 Syed Asad Ali (team syed3000)
# SPDX-License-Identifier: Apache-2.0
"""Exact unsigned adder terminals using restored dirty workspace.

These kernels are a width fallback, not a claimed free-space adder.  A
Cuccaro majority/unmajority frame stores carries in real source bits.  The
remaining zero-source suffix is a controlled increment whose multiple
controls use restored dirty wires.  No clean quantum wire is allocated.

Measured forward carries can be repaid without extra Toffolis: phase a
majority while it occupies a source wire, or apply conditional Z before
and after the controlled X whose toggle is the required carry.  The latter
echo is (-1)**(m*(b XOR (b XOR carry))) = (-1)**(m*carry).
"""
from __future__ import annotations

import kickmix as km


def dirty_mcx_cost(controls):
    if controls < 2:
        return 0
    return 1 if controls == 2 else 4*controls-8


def increment_cost(width):
    return sum(dirty_mcx_cost(position+1) for position in range(width))


def terminal_cost(width, source_width):
    prefix = min(source_width, max(0, width-1))
    return 2*prefix + (0 if source_width == width else increment_cost(width-prefix))


def terminal_dirty_count(width, source_width):
    return max(0, width-source_width-2)


def dirty_mcz_cost(controls):
    if controls < 3:
        return 0
    return 1 if controls == 3 else 4*controls-12


def dirty_mcz(builder, controls, dirty=()):
    """Phase the product of controls, restoring every borrowed dirty bit.

    Replacing the final target toggle of each dirty-MCX ladder with CCZ
    gives two diagonal phases whose dirty contributions cancel.  Their
    remaining phase is exactly the AND of all controls, including on every
    arbitrary dirty-wire input.  No clean quantum wire is allocated.
    """
    controls, dirty = list(controls), list(dirty)
    if not controls or not all(isinstance(w, km.q) for w in controls+dirty):
        raise ValueError('Dirty MCZ requires nonempty quantum controls.')
    needed = max(0, len(controls)-3)
    dirty = dirty[:needed]
    if len(dirty) != needed:
        raise ValueError(f'{len(controls)} phase controls require {needed} dirty wires.')
    if len(set(controls+dirty)) != len(controls)+len(dirty):
        raise ValueError('Phase controls and borrowed wires must be disjoint.')
    if len(controls) == 1:
        builder.z(controls[0]);return
    if len(controls) == 2:
        builder.cz(*controls);return
    if len(controls) == 3:
        builder.ccz(*controls);return

    def ladder(include_first):
        if include_first:
            builder.ccx(controls[0], controls[1], dirty[0])
        for index in range(1, len(dirty)):
            builder.ccx(dirty[index-1], controls[index+1], dirty[index])
        builder.ccz(dirty[-1], controls[-2], controls[-1])
        for index in reversed(range(1, len(dirty))):
            builder.ccx(dirty[index-1], controls[index+1], dirty[index])
        if include_first:
            builder.ccx(controls[0], controls[1], dirty[0])
    ladder(True)
    ladder(False)


def dirty_mcx(builder, controls, target, dirty=()):
    """Toggle target by the AND of controls; restore every arbitrary dirty bit.

    For n >= 3, n-2 borrowed wires and 4n-8 Toffolis suffice.  A complete
    AND ladder and a ladder omitting its first product have identical dirty
    contributions; their target toggles differ by precisely the full AND.
    Each ladder is reversed after its target operation.
    """
    controls, dirty = list(controls), list(dirty)
    if not all(isinstance(wire, km.q) for wire in controls+[target]+dirty):
        raise ValueError('Dirty MCX operands must be quantum wires.')
    need = max(0, len(controls)-2)
    dirty = dirty[:need]
    if len(dirty) != need:
        raise ValueError(f'{len(controls)} controls require {need} dirty wires.')
    if len(set(controls+[target]+dirty)) != len(controls)+1+len(dirty):
        raise ValueError('Dirty MCX controls, target, and borrowed wires must be disjoint.')
    if not controls:
        builder.x(target)
        return
    if len(controls) == 1:
        builder.cx(controls[0], target)
        return
    if len(controls) == 2:
        builder.ccx(controls[0], controls[1], target)
        return

    def ladder(include_first):
        if include_first:
            builder.ccx(controls[0], controls[1], dirty[0])
        for index in range(1, len(dirty)):
            builder.ccx(dirty[index-1], controls[index+1], dirty[index])
        builder.ccx(dirty[-1], controls[-1], target)
        for index in reversed(range(1, len(dirty))):
            builder.ccx(dirty[index-1], controls[index+1], dirty[index])
        if include_first:
            builder.ccx(controls[0], controls[1], dirty[0])
    ladder(True)
    ladder(False)


def _phase(builder, measurement, wire):
    if measurement is not None:
        builder.push_condition(measurement)
        builder.z(wire)
        builder.pop_condition()


def terminal_add(builder, source, target, incoming, *, dirty=(),
                 debt=None, start=0, overflow_phase=None):
    """Add an unsigned source prefix and a quantum incoming carry in place.

    `source` contains distinct quantum low bits followed by literal False
    padding, matching `target` in length.  `debt`, if supplied, owns a dict
    `measurements` keyed by the full adder's carry positions.  Repaid entries
    are popped and their classical bits freed.  All data and borrowed wires
    are restored except the modular target sum.
    """
    source, target, dirty = list(source), list(target), list(dirty)
    width = len(target)
    if len(source) != width or not width:
        raise ValueError('The nonempty source and target widths must match.')
    if not isinstance(incoming, km.q):
        raise ValueError('The sparse terminal requires a quantum incoming carry.')
    count = next((i for i, wire in enumerate(source) if wire is False), width)
    if any(wire is not False for wire in source[count:]):
        raise ValueError('Only an unsigned source prefix with high zero padding is supported.')
    if overflow_phase is not None and count == width:
        raise ValueError('Overflow-phase terminals require a nonempty high zero-source suffix.')
    real_source = source[:count]
    if not all(isinstance(wire, km.q) for wire in real_source+target+dirty):
        raise ValueError('All nonconstant operands must be quantum wires.')
    operands = real_source+target+[incoming]
    if len(set(operands)) != len(operands):
        raise ValueError('Source, target, and incoming carry must be disjoint.')
    required = terminal_dirty_count(width, count)
    dirty = [wire for wire in dict.fromkeys(dirty) if wire not in operands]
    if len(dirty) < required:
        raise ValueError(f'The terminal requires {required} restored dirty wires.')

    def take(position):
        return None if debt is None else debt.measurements.pop(start+position, None)

    def repay(position, wire):
        measurement = take(position)
        _phase(builder, measurement, wire)
        if measurement is not None:
            builder.free(measurement)

    prefix = min(count, width-1)
    frames = []
    carry = incoming
    for index in range(prefix):
        a, b = source[index], target[index]
        builder.cx(a, b)
        builder.cx(a, carry)
        builder.ccx(b, carry, a)
        repay(index+1, a)
        frames.append((a, b, carry))
        carry = a

    if count == width:
        builder.cx(source[-1], target[-1])
        builder.cx(carry, target[-1])
    else:
        high = target[prefix:]
        if overflow_phase is not None:
            # Source-prefix MAJ frames already expose the incoming suffix
            # carry.  Before the increment, overflow is its product with
            # every suffix target bit.  The existing dirty pool suffices.
            builder.push_condition(overflow_phase)
            dirty_mcz(builder, [carry]+high, dirty)
            builder.pop_condition()
        for position in reversed(range(len(high))):
            measurement = take(prefix+position) if position else None
            _phase(builder, measurement, high[position])
            dirty_mcx(builder, [carry]+high[:position], high[position], dirty)
            _phase(builder, measurement, high[position])
            if measurement is not None:
                builder.free(measurement)

    for a, b, carry in reversed(frames):
        builder.ccx(b, carry, a)
        builder.cx(a, carry)
        builder.cx(carry, b)
    phase_cost=dirty_mcz_cost(width-prefix+1) if overflow_phase is not None else 0
    return dict(toffolis=terminal_cost(width, count)+phase_cost, clean_workspace=0,
                dirty_workspace=required, source_prefix=count)
