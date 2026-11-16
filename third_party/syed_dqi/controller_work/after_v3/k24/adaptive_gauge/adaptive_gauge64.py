# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Separate capped64 classical gauge candidate; native qualification pending.

The seventy selected physical mask words retain their old interpolation
coefficients. A separate twelve-bit classical word represents the released
pivot at field point70. All selector work is classical. No selected provider
is patched by this module and no caller profile selects a quantum schedule.
"""
from dataclasses import dataclass
from functools import cache

import kickmix as km
import mask_gauge_blocked as OriginalMasks
import zero_mask_scan as OriginalScan

F = OriginalScan.F
BITS = 12
POINTS = 4095
RESIDUALS = 4025
LABEL_BITS = 6
LABELS = 64
CAP = 7
SELECTOR_PEAK_BITS = 322


class Classical:
    """Explicit scalar classical instructions, counted before native emission.

The AND targets supplied here are known zero. A classical AND is a conditional
classical XOR, with one push, one XOR, and one pop; it is not a quantum CCX.
"""
    def __init__(self, builder):
        self.builder = builder
        self.instructions = 0

    def store(self, targets, value, *, control=None):
        if isinstance(targets, km.b):
            targets = km.array([targets])
        assert all(isinstance(bit, km.b) for bit in targets)
        assert type(value) is bool
        if control is None:
            self.builder.bit_store(targets, value)
            self.instructions += len(targets)
        else:
            assert len(targets) == 1 and isinstance(control, km.b)
            self.builder.bit_store(targets[0], value, control=control)
            self.instructions += 1

    def cx(self, control, target):
        assert isinstance(control, km.b) or type(control) is bool
        assert isinstance(target, km.b)
        self.builder.cx(control, target)
        self.instructions += 1

    def push(self, bit):
        assert isinstance(bit, km.b)
        self.builder.push_condition(bit)
        self.instructions += 1

    def pop(self):
        self.builder.pop_condition()
        self.instructions += 1

    def and_into_zero(self, left, right, target):
        self.push(left)
        self.cx(right, target)
        self.pop()


def _masks_contract(masks):
    if len(masks) != POINTS or any(len(word) != BITS for word in masks):
        raise ValueError('exactly4095 twelve-bit classical mask words are required')
    wires = [bit for word in masks for bit in word]
    if any(not isinstance(bit, km.b) for bit in wires):
        raise TypeError('adaptive selection reads classical masks only')
    if len(wires) != len(set(wires)):
        raise ValueError('mask words must be physically disjoint')


def _syndromes_contract(syndromes):
    if len(syndromes) != 70 or any(len(word) != BITS for word in syndromes):
        raise ValueError('the original seventy quantum syndromes are required')
    wires = [bit for word in syndromes for bit in word]
    if any(not isinstance(bit, km.q) for bit in wires):
        raise TypeError('syndrome compensation acts on quantum values')
    if len(wires) != len(set(wires)):
        raise ValueError('syndrome words must be physically disjoint')


@cache
def geometry():
    plan = OriginalScan.syndrome_gauge_plan()
    assert plan.bits == BITS and tuple(plan.selected) == tuple(range(1, 71))
    polynomial = [0, 1]
    for root in range(1, 70):
        result = [0]*(len(polynomial)+1)
        for degree, value in enumerate(polynomial):
            result[degree] ^= F.mul(value, root)
            result[degree+1] ^= value
        polynomial = result
    assert len(polynomial) == 71 and polynomial[0] == 0 and polynomial[-1] == 1
    values = tuple(OriginalScan.evaluate(polynomial, point) for point in plan.points)
    fixed = frozenset(range(1, 70))
    selected_indices = frozenset(plan.selected_indices)
    residual_indices = tuple(i for i in range(POINTS) if i not in selected_indices)
    pivot_index = plan.points.index(70)
    assert len(residual_indices) == RESIDUALS and values[pivot_index]
    assert all((value == 0) == (point in fixed)
               for point, value in zip(plan.points, values))
    return dict(plan=plan, coefficients=tuple(polynomial[1:]), values=values,
                inverses=tuple(F.invert(v) if v else 0 for v in values),
                fixed_points=fixed, residual_indices=residual_indices,
                pivot_index=pivot_index)


@cache
def mask_network(scalar):
    """The same transpose multiplication ABI as the selected mask_scale."""
    assert 0 < scalar < 4096
    rows = tuple(F.mul(scalar, 1 << bit) for bit in range(BITS))
    return OriginalMasks.Original.linear_network(rows)


def scale_mask(builder, word, scalar, *, inverse=False):
    """Emit explicit classical CXs, including three for each public SWAP."""
    ops = mask_network(scalar)
    count = 0
    for kind, left, right in reversed(ops) if inverse else ops:
        if kind == 'cx':
            builder.cx(word[left], word[right])
            count += 1
        else:
            assert kind == 'swap'
            builder.cx(word[left], word[right])
            builder.cx(word[right], word[left])
            builder.cx(word[left], word[right])
            count += 3
    return count


def _increment_saturated(code, counter, enabled, work):
    """counter=min(7,counter+enabled), preserving enabled and clearing work."""
    low, middle, high = counter
    one, two, three = work
    code.and_into_zero(enabled, low, one)
    code.and_into_zero(one, middle, two)
    code.and_into_zero(two, high, three)
    code.cx(enabled, low)
    code.cx(three, low)
    code.cx(one, middle)
    code.cx(three, middle)
    code.cx(two, high)
    code.cx(three, high)
    code.store(work, False)


def _replace_if_larger(code, counter, best, label, candidate, comparison):
    equal, greater, different = comparison
    code.store(equal, True)
    code.store(greater, False)
    code.store(different, False)
    for bit in (2, 1, 0):
        code.cx(counter[bit], different)
        code.cx(best[bit], different)
        code.cx(True, best[bit])
        code.push(equal)
        code.push(counter[bit])
        code.store(greater, True, control=best[bit])
        code.pop()
        code.pop()
        code.cx(True, best[bit])
        code.store(equal, False, control=different)
        code.store(different, False)
    code.push(greater)
    code.store(best, False)
    for source, target in zip(counter, best):
        code.cx(source, target)
    for bit in range(LABEL_BITS):
        code.store(label[bit], bool(candidate >> bit & 1))
    code.pop()
    code.store(equal, False)
    code.store(greater, False)


def select_capped64(builder, normalized_words, *, stage=lambda _: None):
    """Return a live twelve-bit label; all other owned classical bits are zero.

Input masks remain unchanged. Counter zero starts at one for the virtual
pivot. Strict comparisons keep zero first on ties, including saturation.
The three zeroed histogram carry bits are reused as the best-count word.
"""
    if len(normalized_words) != RESIDUALS or any(len(w) != BITS for w in normalized_words):
        raise ValueError('the4025 normalized residual words are required')
    flat = [bit for word in normalized_words for bit in word]
    if any(not isinstance(bit, km.b) for bit in flat):
        raise TypeError('the histogram has only classical inputs')
    if len(flat) != len(set(flat)):
        raise ValueError('histogram input words must be disjoint')
    entry_q = builder.num_allocated_qubits
    code = Classical(builder)
    counters = builder.alloc_bits(3*LABELS)
    decoder = builder.alloc_bits(2*LABELS-1)
    work = builder.alloc_bits(3)
    assert len(counters)+len(decoder)+len(work) == SELECTOR_PEAK_BITS
    code.store(counters, False)
    code.store(counters[0], True)
    # These initial stores are additional to the certificate's loop ledger.
    code.store(decoder[1:], False)
    code.store(work, False)
    assert code.instructions == 322
    begin_histogram = code.instructions
    for ordinal, word in enumerate(normalized_words):
        code.store(decoder[0], True)
        for high in word[6:]:
            code.store(decoder[0], False, control=high)
        # Read the most significant candidate bit first, so leaves are
        # naturally ordered by the numerical labels0,...,63.
        for depth in range(LABEL_BITS):
            for parent in range((1 << depth)-1, (1 << (depth+1))-1):
                left, right = 2*parent+1, 2*parent+2
                code.and_into_zero(decoder[parent], word[5-depth], decoder[right])
                code.cx(decoder[parent], decoder[left])
                code.cx(decoder[right], decoder[left])
        for candidate in range(LABELS):
            _increment_saturated(code, counters[3*candidate:3*candidate+3],
                                 decoder[LABELS-1+candidate], work)
        code.store(decoder, False)
        if (ordinal+1) % 256 == 0:
            stage(dict(stage='adaptive64_histogram', words=ordinal+1,
                       classical_instructions=code.instructions-begin_histogram))
    histogram = code.instructions-begin_histogram
    assert histogram == RESIDUALS*1601 == 6444025
    builder.free(decoder)
    # work is zero after the final saturated increment; reuse it directly.
    best = work
    label = builder.alloc_bits(BITS)
    comparison = builder.alloc_bits(3)
    code.store(label, False)
    for source, target in zip(counters[:3], best):
        code.cx(source, target)
    for candidate in range(1, LABELS):
        _replace_if_larger(code, counters[3*candidate:3*candidate+3],
                           best, label, candidate, comparison)
    builder.free(comparison)
    code.store(counters, False)
    code.store(best, False)
    builder.free(counters)
    builder.free(best)
    assert code.instructions == 6447833
    assert builder.num_allocated_qubits == entry_q
    return label, dict(histogram_instructions=histogram,
        histogram_instructions_per_word=1601,
        initialize_select_retire_instructions=3808,
        initial_zero_store_addendum=129,
        total_selector_instructions=code.instructions,
        maximum_additional_classical_bits=SELECTOR_PEAK_BITS,
        remaining_classical_bits=BITS, additional_qubits=0,
        static_T=0, cap=CAP, candidate_count=LABELS,
        zero_first_strict_tie_policy=True, native_count_checked=False)


@dataclass
class Record:
    builder_id: int
    masks: tuple
    pivot: object
    selector_ledger: dict
    normalization_instructions: int
    entry_qubits: int
    kind: str = 'transport'
    compensation_instructions: int = 0
    compensated: bool = False
    scans: int = 0
    closed: bool = False


def _check_record(builder, masks, record, *, kind=None):
    if (not isinstance(record, Record) or record.closed or
            record.builder_id != id(builder) or
            record.masks != tuple(tuple(word) for word in masks) or
            (kind is not None and record.kind != kind)):
        raise ValueError('wrong, closed, aliased, or foreign adaptive-gauge record')


def open_transport(builder, masks, *, stage=lambda _: None):
    """Input is the old opened70-point gauge; output is shifted/normalized."""
    _masks_contract(masks)
    entry_q = builder.num_allocated_qubits
    spec = geometry()
    count = sum(scale_mask(builder, masks[index], spec['inverses'][index])
                for index in spec['residual_indices'])
    label, ledger = select_capped64(builder,
        [masks[index] for index in spec['residual_indices']], stage=stage)
    for index in spec['residual_indices']:
        for bit in range(LABEL_BITS):
            builder.cx(label[bit], masks[index][bit])
    assert builder.num_allocated_qubits == entry_q
    return Record(id(builder), tuple(tuple(word) for word in masks), label,
                  ledger, count, entry_q)


def compensate(builder, syndromes, masks, record):
    """Apply Tr(lambda*sum_j(g_j*S_j)) once on the original syndromes."""
    _check_record(builder, masks, record)
    _syndromes_contract(syndromes)
    if record.compensated:
        raise ValueError('adaptive syndrome compensation must not be repeated')
    count = 0
    for scalar, syndrome in zip(geometry()['coefficients'], syndromes):
        for output in range(BITS):
            column = F.mul(scalar, 1 << output)
            for source in range(LABEL_BITS):
                if column >> source & 1:
                    builder.cz(record.pivot[source], syndrome[output])
                    count += 1
    record.compensation_instructions = count
    record.compensated = True
    return count


def _close_transport(builder, masks, record):
    _check_record(builder, masks, record)
    spec = geometry()
    entry_q = builder.num_allocated_qubits
    for index in spec['residual_indices']:
        for bit in range(LABEL_BITS):
            builder.cx(record.pivot[bit], masks[index][bit])
    count = sum(scale_mask(builder, masks[index], spec['inverses'][index], inverse=True)
                for index in spec['residual_indices'])
    assert count == record.normalization_instructions
    builder.bit_store(record.pivot, False)
    builder.free(record.pivot)
    record.closed = True
    assert builder.num_allocated_qubits == entry_q
    return dict(normalization_instructions=count, shift_instructions=6*RESIDUALS,
                pivot_reset_instructions=BITS, all_owned_classical_bits_retired_zero=True)


def close_transport(builder, masks, record):
    _check_record(builder, masks, record, kind='transport')
    return _close_transport(builder, masks, record)


def open_gauge(builder, syndromes, masks, *, stage=lambda _: None):
    _masks_contract(masks)
    _syndromes_contract(syndromes)
    OriginalMasks.open_gauge(builder, syndromes, masks, geometry()['plan'], stage=stage)
    record = open_transport(builder, masks, stage=stage)
    record.kind = 'gauge'
    compensate(builder, syndromes, masks, record)
    return record


def close_gauge(builder, masks, record, *, stage=lambda _: None):
    _check_record(builder, masks, record, kind='gauge')
    if not record.compensated:
        raise ValueError('the full opened gauge requires its compensation phase')
    receipt = _close_transport(builder, masks, record)
    OriginalMasks.close_gauge(builder, masks, geometry()['plan'], stage=stage)
    assert builder.num_allocated_qubits == record.entry_qubits
    return receipt


def emit_scan(builder, D, K, masks, record, *, start_index=0, positions=4095,
              stage=lambda _: None):
    """Unchanged quantum FFT views;69 omitted points and one separate pivot.

The selected Finish provider is read dynamically from OriginalScan. The
4026 candidate cell masks are correlated; the old independent-cell mean
formula must not be applied to this circuit.
"""
    _check_record(builder, masks, record)
    assert len(D) == 36 and len(K) == 35
    assert all(len(word) == BITS for word in (*D, *K))
    assert 0 <= start_index < POINTS and 0 < positions <= POINTS-start_index
    spec, adaptive = OriginalScan.fft_geometry(), geometry()
    U, M = OriginalScan.geometry()['U'], OriginalScan.Finish.geometry()['M']
    stop = start_index+positions
    entry_q = builder.num_allocated_qubits
    ladder = builder.alloc_qubits(10)
    OriginalScan.emit_basis(builder, D)
    OriginalScan.emit_basis(builder, K)
    active = covered = cosets = scaling = 0
    for coset in spec['cosets']:
        points = [(offset, coset ^ offset, spec['log'][coset ^ offset])
                  for offset in range(32)
                  if coset ^ offset and start_index <= spec['log'][coset ^ offset] < stop]
        if not points:
            continue
        cosets += 1
        OriginalScan.emit_coset_view(builder, D, coset)
        OriginalScan.emit_coset_view(builder, K, coset)
        for offset, point, index in points:
            covered += 1
            if point in adaptive['fixed_points']:
                continue
            mask = record.pivot if index == adaptive['pivot_index'] else masks[index]
            divisor = F.mul(point, F.mul(OriginalScan.evaluate(U, point),
                                        OriginalScan.evaluate(M, point)))
            assert divisor and adaptive['values'][index]
            factor = F.mul(adaptive['values'][index], F.invert(divisor))
            scaling += scale_mask(builder, mask, factor)
            OriginalScan.point_cell(builder, D[offset], K[offset], mask, ladder)
            scaling += scale_mask(builder, mask, factor, inverse=True)
            active += 1
        OriginalScan.emit_coset_view(builder, K, coset, inverse=True)
        OriginalScan.emit_coset_view(builder, D, coset, inverse=True)
        stage(dict(stage='adaptive64_scan', cosets=cosets,
                   public_positions=covered, point_tests=active))
    assert covered == positions
    OriginalScan.emit_basis(builder, K, inverse=True)
    OriginalScan.emit_basis(builder, D, inverse=True)
    builder.free(ladder)
    assert builder.num_allocated_qubits == entry_q
    record.scans += 1
    return dict(physical_positions=positions, point_tests=active,
                full_cycle=start_index == 0 and positions == POINTS,
                static_T=11*active, actual_T_law='11 times the nonzero selected masks',
                uniform_original_mask_mean_T=None,
                independent_cell_expectation_valid=False,
                expected_gain_certificate='adaptive_gauge_occupancy.py capped64',
                classical_mask_scaling_instructions=scaling,
                quantum_helpers=10, additional_adaptive_qubits=0,
                admitted_domain_change=False, native_checked=False)


def source_ledger():
    """Exact public classical count model, without building a circuit."""
    spec = geometry()
    normalization = sum(sum(1 if kind == 'cx' else 3
                            for kind, _, _ in mask_network(spec['inverses'][index]))
                        for index in spec['residual_indices'])
    interpolation = sum(1 if kind == 'cx' else 3
                        for kind, _, _ in spec['plan'].interpolation)
    old_shear = OriginalMasks.source_ledger(spec['plan'])['classical_CX_per_adjust']+1
    compensation = sum((F.mul(scalar, 1 << out) & 63).bit_count()
                       for scalar in spec['coefficients'] for out in range(BITS))
    transport_prefix = normalization+6447833+6*RESIDUALS
    transport_closing = normalization+6*RESIDUALS+BITS
    return dict(status='SOURCE_COUNT_MODEL_NATIVE_PENDING',
        histogram_instructions=6444025, explicit_initialization_addendum=129,
        total_selector_instructions=6447833,
        normalization_instructions_per_direction=normalization,
        adaptive_compensation_CZ=compensation,
        old_gauge_prefix_instructions=old_shear+interpolation+840,
        old_gauge_close_instructions=old_shear+interpolation,
        transport_prefix_instructions=transport_prefix,
        transport_close_instructions=transport_closing,
        full_gauge_prefix_instructions=old_shear+interpolation+840+transport_prefix+compensation,
        full_gauge_pair_instructions=2*(old_shear+interpolation)+840+transport_prefix+transport_closing+compensation,
        adaptive_peak_classical_bits=SELECTOR_PEAK_BITS,
        retained_virtual_pivot_bits=BITS, additional_quantum_bits=0,
        non_scan_static_T=0, scan_static_T=44286, old_scan_static_T=44275,
        native_instruction_count_checked=False)
