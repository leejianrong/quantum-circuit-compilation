# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Rebuild the staged incumbent, then merge its later native q28 pair.

At the first gate let A=q8, B=q21, C=q34, D=q15. The original
two products are AB+(A+B+1+D)C. On native inputs B(A+C)=0,
so together with the intervening CX C->q28 they equal C(A+D).
The target is not read or phased between the two products.
This source is a deterministic candidate transform; qualification is external.
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
PARENT_SHA256 = '9a7198f62bc2bf1f16c22b004ec0f52ad2d65e368b245980e0cd86e266aa98b8'
FIRST = 25458
LATER_CX = 25484
SECOND = 25485
REPLACEMENT = ['CX q15 q8', 'CCX q34 q8 q28', 'CX q15 q8']


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def apply(raw_directory):
    import staged_bank_native_v3_causal
    from branch_prover import Program, generated_text
    from fourier_resource_expectation import exact_expectation
    import arithmetic_variant as variant

    raw_directory = Path(raw_directory)
    staged_bank_native_v3_causal.apply(raw_directory)
    text_path = raw_directory / 'study.kmx'
    status_path = raw_directory / 'study.json'
    assert sha(text_path) == PARENT_SHA256
    parent_text = text_path.read_text()
    parent = Program(parent_text)
    parent_status = json.loads(status_path.read_text())
    assert parent_status['Q'] == 44
    assert Fraction(parent_status['expectation']['mean']['toffoli_like']) == Fraction(11561, 8)
    expected = {
        FIRST: ('CCX', ('q21', 'q8', 'q28')),
        LATER_CX: ('CX', ('q34', 'q28')),
        SECOND: ('CCX', ('q8', 'q34', 'q28')),
    }
    for index, (kind, owners) in expected.items():
        op = parent.operations[index]
        assert (op.kind, op.arguments, op.condition) == (kind, owners, None)

    # Inspect actual target use, not just equal target/control wire names.
    allowed_target_writes = []
    for index in range(FIRST + 1, SECOND):
        op = parent.operations[index]
        if 'q28' not in op.arguments:
            continue
        assert op.kind in ('X', 'CX', 'CCX') and op.arguments[-1] == 'q28'
        assert op.condition is None
        allowed_target_writes.append(dict(operation=index, kind=op.kind, owners=list(op.arguments)))

    output = []
    index = 0
    count = 0
    op_map = {}
    stack_depth = 0
    metadata = ('APPEND_TO_REGISTER', 'REGISTER', 'INFO_TAG', 'DEBUG_PRINT')
    for line in parent_text.splitlines():
        tokens = shlex.split(line, comments=True)
        if not tokens or tokens[0] in metadata:
            output.append(line)
            continue
        op = parent.operations[index]
        assert tokens[0] == op.kind
        op_map[index] = count
        if index == FIRST:
            assert stack_depth == 0
            output.extend(REPLACEMENT)
            count += len(REPLACEMENT)
        elif index in (LATER_CX, SECOND):
            assert stack_depth == 0
        else:
            output.append(line)
            count += 1
        if op.kind == 'PUSH_CONDITION':
            stack_depth += 1
        elif op.kind == 'POP_CONDITION':
            stack_depth -= 1
        assert stack_depth >= 0
        index += 1
    op_map[index] = count
    assert index == len(parent.operations) and stack_depth == 0
    assert count == len(parent.operations)
    circuit = variant.old.common.km.Circuit('\n'.join(output) + '\n')
    canonical = generated_text(circuit)
    program = Program(canonical)
    resources = exact_expectation(canonical)
    assert circuit.num_qubits == 44 and program.measurements == parent.measurements == 1286
    assert len(program.operations) == count
    assert list(circuit.register_data) == ['x'] and len(circuit.register_data['x']) == 22
    assert Fraction(resources['mean']['toffoli_like']) == Fraction(11553, 8)
    assert resources['mean']['T'] == '4' and resources['mean']['generic_rotations'] == '34'
    assert resources['static']['toffoli_like'] == parent_status['expectation']['static']['toffoli_like'] - 1
    circuit.to_file(str(raw_directory / 'study.kmb'), format='kmb')
    text_path.write_text(canonical)

    status = dict(parent_status)
    status.update(notice=NOTICE, status='DISTRIBUTIVE_Q28_NATIVE_CANDIDATE_FULL_PROOF_PENDING',
                  expectation=resources, kmb_sha256=sha(raw_directory / 'study.kmb'))
    status['staged_cuts_before_distributive_merge'] = parent_status['cuts']
    status['cuts'] = []
    for prior in parent_status['cuts']:
        cut = dict(prior)
        old_index = cut['instruction_cut']
        cut['staged_instruction_cut'] = old_index
        cut['instruction_cut'] = op_map[old_index]
        if 'cumulative_expected' in cut:
            cut['cumulative_expected'] = dict(cut['cumulative_expected'])
            if old_index > SECOND:
                cut['cumulative_expected']['toffoli_like'] -= 1
        status['cuts'].append(cut)
    ledger = dict(
        notice=NOTICE, status='DISTRIBUTIVE_Q28_NATIVE_CANDIDATE_FULL_PROOF_PENDING',
        module_sha256=sha(__file__), parent_raw_sha256=PARENT_SHA256,
        native_raw_sha256=sha(text_path), native_kmb_sha256=sha(raw_directory / 'study.kmb'),
        first_operation=FIRST, deleted_later_operations=[LATER_CX, SECOND],
        replacement_lines=REPLACEMENT, target='q28', target_unread_interval=True,
        retained_target_writes=[x for x in allowed_target_writes if x['operation'] != LATER_CX],
        native_identity='B*(A+C)=0, with A=q8,B=q21,C=q34,D=q15 before operation25458',
        net_target_identity='A*B+(A+B+1+D)*C+C = C*(A+D)',
        raw_resources=resources, expected_finished_Toffolis='11481/8',
        previous_qualified_expected_Toffolis='11489/8', modelled_saving='1',
        Q=44, HMR_events=1286, qualified=False)
    status['distributive_merge'] = ledger
    status_path.write_text(json.dumps(status, indent=2) + '\n')
    (raw_directory.parent / 'DISTRIBUTIVE_Q28_NATIVE_LEDGER.json').write_text(json.dumps(ledger, indent=2) + '\n')
    print(json.dumps(ledger, indent=2), flush=True)
    return ledger
