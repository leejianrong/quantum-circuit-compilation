# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Pure deterministic earlier-q28 merge after the separately bound q27 transform.

The target-only value replacement uses affine values at their actual birth
times. Every extra phase is binary and guarded only by unchanged incoming
classical bits. No X-measurement outcome is used as a computational value.
Full native qualification remains external to this deterministic transform.
"""
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shlex

NOTICE = ('Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. '
          'Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, '
          'Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science '
          'supporting the research.')
PARENT_SHA256 = 'd3e823862b9495e55af38ca82f6febcafab7ea1e2abbf1a52c9bac7783657faa'
FIRST, PRODUCT, SECOND = 22535, 22709, 22716
VALUE_PREFIXES = {
    FIRST: ['X q28', 'CX q8 q28', 'CX q26 q28'],
    PRODUCT: ['CX q26 q28'],
}
PRODUCT_GATES = ['CX q33 q8', 'CX q15 q26', 'CX q33 q26',
                 'CCX q8 q26 q28', 'CX q33 q26', 'CX q15 q26', 'CX q33 q8']

# Generated from the full-domain exact coefficient witnesses in
# TIMED_BINARY_PHASE_CORRECTIONS.json. Values are (cut, stage, guard bits, gates).
PHASE_PROGRAM = [(22535, 'after_prefix_edits', ['b366'], ['NEG', 'Z q0', 'Z q8', 'Z q21', 'Z q26', 'Z q28', 'Z q31', 'Z q33', 'Z q34', 'CZ q0 q8', 'CZ q0 q26', 'CZ q0 q33', 'CZ q8 q15', 'CZ q8 q20', 'CZ q8 q21', 'CZ q8 q26', 'CZ q8 q31', 'CZ q8 q34', 'CZ q15 q20', 'CZ q20 q21', 'CZ q20 q31', 'CZ q20 q33', 'CZ q20 q34', 'CZ q26 q33']), (22535, 'after_prefix_edits', ['b367'], ['NEG', 'Z q0', 'Z q8', 'Z q21', 'Z q26', 'Z q28', 'Z q31', 'Z q33', 'Z q34', 'CZ q0 q8', 'CZ q0 q26', 'CZ q0 q33', 'CZ q8 q15', 'CZ q8 q20', 'CZ q8 q21', 'CZ q8 q26', 'CZ q8 q31', 'CZ q8 q34', 'CZ q15 q20', 'CZ q20 q21', 'CZ q20 q31', 'CZ q20 q33', 'CZ q20 q34', 'CZ q26 q33']), (22542, 'after_prefix_edits', ['b366'], ['CZ q15 q34', 'CZ q28 q34']), (22542, 'after_prefix_edits', ['b367'], ['CZ q15 q34', 'CZ q28 q34']), (22638, 'after_prefix_edits', ['b365', 'b367'], ['CZ q0 q26', 'CZ q8 q26', 'CZ q21 q26', 'CZ q26 q28', 'CZ q26 q31']), (22638, 'after_prefix_edits', ['b366'], ['CZ q15 q26', 'CZ q26 q32', 'CZ q26 q33']), (22638, 'after_prefix_edits', ['b367'], ['CZ q15 q26', 'CZ q26 q32', 'CZ q26 q33']), (22709, 'after_prefix_edits', ['b366'], ['CZ q8 q28', 'CZ q20 q28']), (22709, 'after_prefix_edits', ['b367'], ['CZ q8 q28', 'CZ q20 q28'])]


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def phase_lines(cut, stage):
    result = []
    for group_cut, group_stage, guards, gates in PHASE_PROGRAM:
        if (group_cut, group_stage) != (cut, stage):
            continue
        result.extend('PUSH_CONDITION if ' + guard for guard in guards)
        result.extend(gates)
        result.extend('POP_CONDITION' for guard in guards)
    return result


def prefix(cut):
    result = list(VALUE_PREFIXES.get(cut, []))
    if cut == PRODUCT:
        result += phase_lines(cut, 'before_paid_gate')
        result += PRODUCT_GATES
    result += phase_lines(cut, 'after_prefix_edits')
    return result


def transform_text(text):
    from branch_prover import Program
    assert hashlib.sha256(text.encode()).hexdigest() == PARENT_SHA256
    original = Program(text)
    assert (original.operations[FIRST].kind, original.operations[FIRST].arguments) == ('CCX', ('q8', 'q26', 'q28'))
    assert (original.operations[SECOND].kind, original.operations[SECOND].arguments) == ('CCX', ('q26', 'q8', 'q28'))
    for index in range(FIRST, SECOND + 1):
        op = original.operations[index]
        if op.kind in ('X', 'CX', 'CCX', 'HMR'):
            assert op.condition is None
            if op.kind in ('CX', 'CCX'):
                assert 'q28' not in op.arguments[:-1]
            if op.kind == 'HMR':
                assert op.arguments[0] != 'q28'
                assert op.arguments[1] not in ('b365', 'b366', 'b367')
    lines, mapping, deltas = [], {}, {}
    index = count = delta = depth = 0
    metadata = ('REGISTER', 'APPEND_TO_REGISTER', 'INFO_TAG', 'DEBUG_PRINT')
    for line in text.splitlines():
        tokens = shlex.split(line, comments=True)
        if not tokens or tokens[0] in metadata:
            lines.append(line)
            continue
        op = original.operations[index]
        assert op.kind == tokens[0]
        mapping[index], deltas[index] = count, delta
        inserted = prefix(index)
        if inserted or index in (FIRST, SECOND):
            assert depth == 0
        lines.extend(inserted)
        count += len(inserted)
        delta += sum(gate.startswith('CCX ') for gate in inserted)
        if index not in (FIRST, SECOND):
            lines.append(line)
            count += 1
        else:
            delta -= 1
        if op.kind == 'PUSH_CONDITION':
            depth += 1
        elif op.kind == 'POP_CONDITION':
            depth -= 1
        assert depth >= 0
        index += 1
    assert index == len(original.operations) and depth == 0 and delta == -1
    mapping[index], deltas[index] = count, delta
    result = '\n'.join(lines) + '\n'
    candidate = Program(result)
    assert len(candidate.operations) == count
    assert candidate.measurements == original.measurements == 1286
    assert candidate.registers == original.registers
    return result, mapping, deltas


def apply(raw_directory):
    """Apply only pairA; the input must contain the exact q27 parent and earlier qualified later-q28 merge."""
    from branch_prover import Program, generated_text
    from fourier_resource_expectation import exact_expectation
    import arithmetic_variant as variant
    directory = Path(raw_directory)
    text_path, status_path = directory / 'study.kmx', directory / 'study.json'
    parent_status = json.loads(status_path.read_text())
    assert parent_status['Q'] == 44
    assert Fraction(parent_status['expectation']['mean']['toffoli_like']) == Fraction(11545, 8)
    text, mapping, deltas = transform_text(text_path.read_text())
    circuit = variant.old.common.km.Circuit(text)
    canonical = generated_text(circuit)
    resources = exact_expectation(canonical)
    assert circuit.num_qubits == 44 and Program(canonical).measurements == 1286
    assert list(circuit.register_data) == ['x'] and len(circuit.register_data['x']) == 22
    assert Fraction(resources['mean']['toffoli_like']) == Fraction(11537, 8)
    assert resources['mean']['T'] == '4' and resources['mean']['generic_rotations'] == '34'
    assert resources['static']['toffoli_like'] == parent_status['expectation']['static']['toffoli_like'] - 1
    circuit.to_file(str(directory / 'study.kmb'), format='kmb')
    text_path.write_text(canonical)
    status = dict(parent_status)
    status.update(notice=NOTICE, status='Q28_PAIR_A_NATIVE_CANDIDATE_FULL_PROOF_PENDING',
                  expectation=resources, kmb_sha256=sha(directory / 'study.kmb'))
    status['cuts_before_q28_pair_A'] = parent_status['cuts']
    status['cuts'] = []
    for prior in parent_status['cuts']:
        cut = dict(prior)
        old_index = cut['instruction_cut']
        cut['pair_A_parent_instruction_cut'] = old_index
        cut['instruction_cut'] = mapping[old_index]
        if 'cumulative_expected' in cut:
            cut['cumulative_expected'] = dict(cut['cumulative_expected'])
            cut['cumulative_expected']['toffoli_like'] += deltas[old_index]
        status['cuts'].append(cut)
    ledger = dict(
        notice=NOTICE, status='Q28_PAIR_A_NATIVE_CANDIDATE_FULL_PROOF_PENDING',
        parent_raw_sha256=PARENT_SHA256, module_sha256=sha(__file__),
        native_raw_sha256=sha(text_path), native_kmb_sha256=sha(directory / 'study.kmb'),
        removed_CCX_operations=[FIRST, SECOND], inserted_product_cut=PRODUCT,
        value_prefixes=VALUE_PREFIXES, product_gates=PRODUCT_GATES, phase_program=PHASE_PROGRAM,
        raw_resources=resources, modelled_finished_Toffolis='11465/8',
        previous_qualified_expected_Toffolis='11473/8', modelled_saving='1',
        Q=44, HMR_events=1286, all_HMR_values_unchanged=True,
        phase_guards=['b365', 'b366', 'b367'], new_fractional_phases=False,
        qualified=False, qualification_debt='Unchanged official full-domain/all-HMR proof and two byte-identical native builds.')
    status['q28_pair_A'] = ledger
    status_path.write_text(json.dumps(status, indent=2) + '\n')
    (directory.parent / 'Q28_PAIR_A_NATIVE_LEDGER.json').write_text(json.dumps(ledger, indent=2) + '\n')
    return ledger
