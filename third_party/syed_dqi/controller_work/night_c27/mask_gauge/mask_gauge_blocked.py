# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""The existing mask gauge with a streamed public binary-linear shear.

Only the implementation of adjust_nonselected changes. Selected interpolation,
the original-syndrome compensation phase and inverse interpolation are copied
unchanged from mask_gauge135. No original module or production emitter is edited.

The preferred public block width is12: one complete selected coefficient word.
It emits exactly3,667,720 classical CX items plus one zero-store per adjustment
for the production70-selected/4095-position plan. One classical scratch bit,
zero quantum scratch and zero T are used. Native counts require the component
receipt; this module's ledger is an exact source-operation count.
"""
from __future__ import annotations

from functools import cache
import kickmix as km

import mask_gauge135 as Original
from field_tensor import apply_linear


@cache
def conjugated_rows(bits, gram_rows, inverse_gram_rows):
    """Rows of Gram * Mul(c) * Gram^-1, derived for every public scalar c."""
    field = km.GF2Field(bits)
    input_columns = [apply_linear(inverse_gram_rows, 1 << bit) for bit in range(bits)]
    rows_by_scalar = []
    for scalar in range(1 << bits):
        columns = [apply_linear(gram_rows, field.mul(scalar, value))
                   for value in input_columns]
        rows = tuple(sum(((column >> out) & 1) << source
                         for source, column in enumerate(columns))
                     for out in range(bits))
        if scalar:
            assert all(rows), 'An invertible field multiplication has no zero row'
        rows_by_scalar.append(rows)
    return tuple(rows_by_scalar)


def block_groups(plan, *, block_bits=12):
    """Yield one public pattern-to-destination table at a time.

    Destination indices are little-endian bit indices in all4095 mask words.
    The selected words are always excluded as destinations. At most two
    consecutive field-power vectors and one block's grouping are retained.
    """
    assert plan.bits == 12
    assert block_bits in (8, 12)
    field = km.GF2Field(plan.bits)
    chosen = frozenset(plan.selected_indices)
    active = tuple((index, point) for index, point in enumerate(plan.points)
                   if index not in chosen)
    assert len(chosen) == len(plan.selected)
    assert all(point for _, point in active)
    matrices = conjugated_rows(plan.bits, tuple(plan.gram_rows), tuple(plan.inverse_gram_rows))
    powers = tuple(point for _, point in active)  # power for coefficient0 is a**1.
    next_powers = None
    coefficient = 0
    total_sources = plan.bits*len(plan.selected)
    target_bits = plan.bits*len(active)
    for start in range(0, total_sources, block_bits):
        word, offset = divmod(start, plan.bits)
        width = min(block_bits, total_sources-start)
        while coefficient < word:
            powers = (next_powers if next_powers is not None else
                      tuple(field.mul(power, point) for power, (_, point) in zip(powers, active)))
            next_powers = None
            coefficient += 1
        assert coefficient == word
        groups = [[] for _ in range(1 << width)]
        if offset+width <= plan.bits:
            mask = (1 << width)-1
            for (physical_index, _), power in zip(active, powers):
                rows = matrices[power]
                base = plan.bits*physical_index
                for out, row in enumerate(rows):
                    groups[(row >> offset) & mask].append(base+out)
        else:
            assert word+1 < len(plan.selected)
            if next_powers is None:
                next_powers = tuple(field.mul(power, point)
                                    for power, (_, point) in zip(powers, active))
            low_width = plan.bits-offset
            low_mask = (1 << low_width)-1
            high_mask = (1 << (width-low_width))-1
            for (physical_index, _), power, following in zip(active, powers, next_powers):
                low_rows, high_rows = matrices[power], matrices[following]
                base = plan.bits*physical_index
                for out, (low, high) in enumerate(zip(low_rows, high_rows)):
                    pattern = ((low >> offset) & low_mask) | ((high & high_mask) << low_width)
                    groups[pattern].append(base+out)
        assert sum(map(len, groups)) == target_bits
        if block_bits == plan.bits:
            assert offset == 0 and width == plan.bits and not groups[0]
        yield start, width, groups


def source_ledger(plan, *, block_bits=12):
    """Public source ledger; no native build or input values are inspected."""
    assert plan.bits == 12 and block_bits in (8, 12)
    source_bits = len(plan.selected)*plan.bits
    target_bits = (len(plan.points)-len(plan.selected))*plan.bits
    widths = [min(block_bits, source_bits-start)
              for start in range(0, source_bits, block_bits)]
    updates = sum(1 << width for width in widths)
    exact_fanouts = target_bits*len(widths) if block_bits == plan.bits else None
    return {'status': 'EXACT_PUBLIC_SOURCE_LEDGER' if exact_fanouts is not None else
                      'PUBLIC_SOURCE_LEDGER_WITH_FANOUT_UPPER_BOUND',
            'block_bits': block_bits, 'blocks': len(widths),
            'source_bits': source_bits, 'target_bits': target_bits,
            'gray_temporary_CX': updates,
            'target_fanout_CX': exact_fanouts,
            'target_fanout_CX_upper_bound': target_bits*len(widths),
            'classical_CX_per_adjust': None if exact_fanouts is None else updates+exact_fanouts,
            'initial_classical_zero_stores_per_adjust': 1,
            'classical_scratch_bits': 1, 'quantum_scratch': 0,
            'static_T_per_adjust': 0, 'mean_T_per_adjust': 0,
            'unchanged_interpolation_network_operations': len(plan.interpolation),
            'unchanged_compensation_CZ_items_at_open': source_bits,
            'native_measurement_claim': False}


def adjust_nonselected(builder, masks, plan, *, block_bits=12, stage=None):
    """Apply the same involutory shear as the original Chien implementation.

    A selected coefficient word w_j represents Gram*g_j. At a nonselected
    point a, target E_a receives Gram*sum(g_j*a**(j+1)). Selected words remain
    unchanged. The temporary follows a complete reflected Gray cycle and
    therefore returns to zero independently of all source/target values.
    """
    assert len(masks) == len(plan.points)
    assert all(len(word) == plan.bits for word in masks)
    assert plan.bits == 12 and block_bits in (8, 12)
    live_quantum = builder.num_allocated_qubits
    source = tuple(bit for index in plan.selected_indices for bit in masks[index])
    targets = tuple(bit for word in masks for bit in word)
    temporary = builder.alloc_bits(1)
    builder.bit_store(temporary, False)
    gray_updates = fanout_items = blocks = 0
    for start, width, groups in block_groups(plan, block_bits=block_bits):
        previous = 0
        for ordinal in range(1, 1 << width):
            pattern = ordinal ^ (ordinal >> 1)
            difference = previous ^ pattern
            assert difference and difference & (difference-1) == 0
            builder.cx(source[start+difference.bit_length()-1], temporary[0])
            gray_updates += 1
            destinations = groups[pattern]
            if destinations:
                builder.cx(km.array([temporary[0]]*len(destinations)),
                           km.array([targets[index] for index in destinations]))
                fanout_items += len(destinations)
            previous = pattern
        # Reflected Gray order ends at its highest bit; close the cycle to0.
        assert previous == 1 << (width-1)
        builder.cx(source[start+width-1], temporary[0])
        gray_updates += 1
        blocks += 1
        if stage is not None:
            stage({'stage': 'blocked_mask_shear', 'blocks': blocks,
                   'source_bits_consumed': start+width,
                   'gray_temporary_CX': gray_updates, 'target_fanout_CX': fanout_items})
    builder.free(temporary)
    assert builder.num_allocated_qubits == live_quantum
    expected = source_ledger(plan, block_bits=block_bits)
    assert gray_updates == expected['gray_temporary_CX']
    if expected['target_fanout_CX'] is not None:
        assert fanout_items == expected['target_fanout_CX']
    return {'status': 'EMITTED_NOT_NATIVE_CHECKED', 'block_bits': block_bits,
            'blocks': blocks, 'gray_temporary_CX': gray_updates,
            'target_fanout_CX': fanout_items,
            'classical_CX': gray_updates+fanout_items,
            'initial_classical_zero_stores': 1, 'classical_scratch_bits': 1,
            'quantum_scratch': 0, 'static_T': 0, 'mean_T': 0}


def open_gauge(builder, syndromes, masks, plan=None, *, block_bits=12, stage=None):
    """Original interpolation/phase, followed by the new equivalent shear."""
    plan = Original.physical_plan() if plan is None else plan
    assert len(syndromes) == len(plan.selected)
    assert all(len(word) == plan.bits for word in list(syndromes)+list(masks))
    assert len(masks) == len(plan.points)
    live = builder.num_allocated_qubits
    words = [masks[index] for index in plan.selected_indices]
    Original.emit_network(builder, words, plan.interpolation)
    for coefficient, syndrome in zip(words, syndromes):
        builder.cz(coefficient, syndrome)
    adjust_nonselected(builder, masks, plan, block_bits=block_bits, stage=stage)
    assert builder.num_allocated_qubits == live
    return plan


def close_gauge(builder, masks, plan=None, *, block_bits=12, stage=None):
    """Restore all E words without repeating the original compensation phase."""
    plan = Original.physical_plan() if plan is None else plan
    live = builder.num_allocated_qubits
    adjust_nonselected(builder, masks, plan, block_bits=block_bits, stage=stage)
    Original.emit_network(builder, [masks[index] for index in plan.selected_indices],
                          plan.interpolation, inverse=True)
    assert builder.num_allocated_qubits == live
