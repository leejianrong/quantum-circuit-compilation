# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Retire first-pass D11, explicitly undoing the D11-reading q35 merge.

Parent: qualified temporal1114-only native. The separate q9 merge is retained.
The four original q35 products replace the two merged ones (+2); D10/D11
restoration uses three products instead of two (+1). The extra D11 HMR debt
is repaid on the reconstructed value. This is an exact local transformation;
the full circuit remains Q44 until the other peak regions are addressed.
"""
from dataclasses import replace
from pathlib import Path
from collections import Counter
from fractions import Fraction
import argparse
import gzip
import json
import pickle
import sys
import time
import numpy as np
from temporal_core import NOTICE, Program, captures, advance, bits, mul, sha, xor

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT_SHA = '8e07ebd2460869a5a364629debec7d53de1cc1f357e1a5f63cdb00f51406d5b0'
START, STOP = 2924, 3336


def plan_lines(variables, target, plan):
    result = []
    if plan['constant']:
        result.append(f'X {target}')
    result += [f'CX {variables[i]} {target}' for i in bits(plan['product_linear'])]
    for a, b, i, j in plan['products']:
        assert a >> i & 1 and b >> j & 1 and not (a >> j & 1) and not (b >> i & 1)
        frame = [f'CX {variables[k]} {variables[i]}' for k in bits(a) if k != i]
        frame += [f'CX {variables[k]} {variables[j]}' for k in bits(b) if k != j]
        result += frame + [f'CCX {variables[i]} {variables[j]} {target}'] + frame[::-1]
    return result


def simulate(initial, ops, full, origin, parent, fresh_event, collect=False):
    state = {q: dict(v) for q, v in initial.items()}
    state.setdefault('b374', {})
    one = {0: full}
    stack = [one]
    phase = {}
    rotations = []
    masks = []
    event_map = []
    def record():
        masks.append(sum((bool(state[f'q{q}']) << q) for q in range(44)))
    record()
    for op, source in zip(ops, origin):
        if op.kind == 'PUSH_CONDITION':
            stack.append(stack[-1] if op.condition is None else mul(stack[-1], state[op.condition]))
        elif op.kind == 'POP_CONDITION':
            stack.pop()
        else:
            if op.kind == 'HMR':
                event = fresh_event if source is None else parent.operations[source].event
                assert event is not None
                event_map.append(dict(local_operation=len(masks)-1, native_origin=source, formal_event=event))
                op = replace(op, event=event)
            guard = stack[-1] if op.condition is None else mul(stack[-1], state[op.condition])
            ph, ro = advance(state, op, guard, one, formal=True)
            phase = xor(phase, ph)
            if ro is not None:
                rotations.append(ro)
        record()
    assert stack == [one]
    return state, phase, rotations, masks, event_map


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--native', type=Path, default=ROOT/'root/window1114_qualification_v1/first/candidate_text.kmx')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--inputs', choices=('full', 'witness'), default='full')
    args = ap.parse_args()
    began = time.monotonic()
    assert sha(args.native) == PARENT_SHA
    text = args.native.read_text()
    parent = Program(text)
    assert len(parent.operations) == 33981 and parent.measurements == 1289
    assert max(int(q[1:]) for q in parent.wires if q.startswith('b')) == 373
    metadata_path = ROOT/'incumbent_sources/frozen_source/fusion64/metadata_A10_swap.json'
    metadata = json.loads(metadata_path.read_text())
    local_contract = HERE/'q43_first_coefficient_contract_v1/CONTRACT.json'
    contract = json.loads(local_contract.read_text())
    assert contract['exact_table_rows'] == 64
    assert contract['metadata_sha256'] == sha(metadata_path)
    # q35 mutation from the authenticated original four-to-two transformation,
    # translated to this finished native operation frame. No other saving is
    # removed and the q9 merge is far outside this interval.
    omit = set(range(3016, 3037)) | {3088, 3149} | set(range(3217, 3237)) | set(range(3316, 3333))
    inserts = {
        START: ['HMR q26 b374'],
        3016: ['CCX q20 q28 q35'],
        3094: ['CCX q20 q28 q35'],
        3155: ['CCX q20 q28 q35'],
        3239: ['CCX q20 q28 q35'],
    }
    held = ['q33','q31','q37','q38','q39','q40','q41','q42','q27','q29']
    restore = plan_lines(held, 'q20', metadata['second']['plan'])
    restore += ['X q26','CX q42 q20','CX q42 q27','CCX q20 q27 q26',
                'CX q42 q27','CX q42 q20','Z q26 if b374']
    assert sum(x.startswith('CCX ') for x in restore) == 3
    inserts[3316] = restore
    expected = {
        2923: ('HMR', ('q29','b9')),
        3088: ('CX', ('q43','q35')), 3149: ('CX', ('q43','q35')),
        3094: ('CX', ('q20','q28')), 3155: ('CX', ('q20','q28')),
        3239: ('CX', ('q20','q28')),
        3316: ('X', ('q20',)), 3332: ('CX', ('q26','q31')),
    }
    for index, pair in expected.items():
        op = parent.operations[index]
        assert (op.kind, op.arguments) == pair and op.condition is None
    for index in range(START, 3316):
        if index not in omit:
            assert 'q26' not in parent.operations[index].arguments
    for index in range(3016, 3240):
        op = parent.operations[index]
        if 'q35' in op.arguments:
            assert op.kind in ('X','CX','CCX') and op.arguments[-1] == 'q35' and op.condition is None
    # Preserve all text metadata and unchanged lines exactly. The origin map
    # labels old HMRs with their old formal variables during the local proof.
    by_line = {op.line: i for i, op in enumerate(parent.operations)}
    output = ['# '+NOTICE]
    origin = []
    cut_map = {}
    emitted = 0
    for line_number, line in enumerate(text.splitlines(), 1):
        index = by_line.get(line_number)
        if index is None:
            output.append(line)
            continue
        cut_map[index] = emitted
        added = inserts.get(index, [])
        output.extend(added)
        origin.extend([None]*len(added))
        emitted += len(added)
        if index not in omit:
            output.append(line)
            origin.append(index)
            emitted += 1
    cut_map[len(parent.operations)] = emitted
    candidate_text = '\n'.join(output)+'\n'
    candidate = Program(candidate_text)
    assert len(candidate.operations) == emitted == len(origin)
    assert candidate.measurements == parent.measurements+1
    assert candidate.registers == parent.registers
    assert sum(o.kind=='CCX' for o in candidate.operations)-sum(o.kind=='CCX' for o in parent.operations) == 3
    if args.inputs == 'full':
        xs = np.arange(1, 3133453, dtype=np.uint64)
    else:
        with gzip.open(HERE/'window2216_joined_contract_v1/JOINED_BINDINGS.pkl.gz','rb') as f:
            xs = pickle.load(f)['xs']
    full = (1 << len(xs))-1
    captured = captures(parent, [START], xs, formal=True, include_classical=True)[START]
    old_ops = parent.operations[START:STOP]
    a, b = cut_map[START], cut_map[STOP]
    new_ops = candidate.operations[a:b]
    before = simulate(captured, old_ops, full, list(range(START,STOP)), parent, parent.measurements)
    after = simulate(captured, new_ops, full, origin[a:b], parent, parent.measurements)
    old_state, old_phase, old_rotations, old_masks, old_events = before
    new_state, new_phase, new_rotations, new_masks, new_events = after
    assert not old_rotations and not new_rotations
    assert old_phase == new_phase
    assert all(old_state[q] == new_state[q] for q in parent.wires)
    assert new_state['b374'] == {1 << parent.measurements: full}
    args.out.mkdir(exist_ok=False)
    native_out = args.out/'candidate_text.kmx'
    native_out.write_text(candidate_text)
    (args.out/'restoration_block.kmx').write_text('# '+NOTICE+'\n'+'\n'.join(restore)+'\n')
    with gzip.open(args.out/'OPERATION_MAP.json.gz','wt',compresslevel=9) as f:
        json.dump(dict(notice=NOTICE,parent_sha256=PARENT_SHA,candidate_sha256=sha(native_out),
                       old_cut_to_new_cut=cut_map,new_operation_origin=origin),f,separators=(',',':'))
    with gzip.open(args.out/'LOCAL_OCCUPANCY.json.gz','wt',compresslevel=9) as f:
        json.dump(dict(notice=NOTICE,inputs=len(xs),all_HMR_formal=True,
                       parent_start_cut=START,parent_occupied_owner_masks=old_masks,
                       candidate_start_cut=a,candidate_occupied_owner_masks=new_masks),f,separators=(',',':'))
    old_hist = Counter(x.bit_count() for x in old_masks)
    new_hist = Counter(x.bit_count() for x in new_masks)
    # Price using the unchanged exact native guard evaluator.
    engine = ROOT/'incumbent_sources/frozen_source/fusion/runtime/work/c10/narrow/checkpoint002/cleanroom/baseline_stage97/tests'
    sys.path.insert(0,str(engine))
    sys.path.insert(0,str(engine.parent/'engine'))
    from fourier_resource_expectation import exact_expectation
    parent_resource = exact_expectation(text)
    new_resource = exact_expectation(candidate_text)
    assert Fraction(parent_resource['mean']['toffoli_like']) == Fraction(11429,8)
    assert Fraction(new_resource['mean']['toffoli_like']) == Fraction(11453,8)
    assert new_resource['mean']['T'] == '1' and new_resource['mean']['generic_rotations'] == '34'
    report = dict(notice=NOTICE,status='FIRST_COEFFICIENT_D11_RETIREMENT_EMITTED_LOCAL_EXACT_PASS',
        numerical_verification='AGENT_VERIFIED_ROOT_REPLAY_PENDING', qualified=False,
        full_circuit_unchanged_official_proof_pending=True,
        source_sha256=sha(__file__),parent_native_sha256=PARENT_SHA,candidate_native_sha256=sha(native_out),
        local_contract_sha256=sha(local_contract),metadata_sha256=sha(metadata_path),
        input_domain='all legal original inputs [1,3133453)' if args.inputs=='full' else 'authenticated original witness inputs',
        exact_original_inputs=len(xs),all_original_HMRs_symbolic=True,extra_HMR_event=parent.measurements,
        added_classical_owner='b374',parent_interval=[START,STOP],candidate_interval=[a,b],
        extra_HMR_retirement_old_cut=START,restore_old_interval=[3316,3333],
        q35_merge_explicitly_undone=True,q35_extra_unconditional_products=2,
        q9_merge_preserved=True,extra_D11_restoration_unconditional_products=1,
        exact_added_expected_Toffolis='3',exact_candidate_expected_Toffolis='11453/8',
        exact_difference_from_current_combined_incumbent='49/16',
        quantum_values_and_old_classical_values_identical_at_endpoint=True,
        all_HMR_binary_phase_identical=True,intermediate_rotations=0,
        parent_local_occupied_owner_histogram=dict(sorted(old_hist.items())),
        candidate_local_occupied_owner_histogram=dict(sorted(new_hist.items())),
        parent_local_peak=max(old_hist),candidate_local_peak=max(new_hist),
        local_native_peak44_cuts_eliminated=old_hist.get(44,0)-new_hist.get(44,0),
        no_extra_quantum_owner_added=True,whole_native_Q=44,remaining_global_peaks_untouched=True,
        native_resources=new_resource,operation_map_sha256=sha(args.out/'OPERATION_MAP.json.gz'),
        local_occupancy_sha256=sha(args.out/'LOCAL_OCCUPANCY.json.gz'),
        new_local_HMR_map=new_events,seconds=time.monotonic()-began)
    (args.out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('native_resources','new_local_HMR_map')},indent=2))


if __name__ == '__main__':
    main()
