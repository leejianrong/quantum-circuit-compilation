# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Share complementary classical-HMR branches in three later helper windows.

The exact local proof retains every legal input and every formal HMR variable.
It compares the original measurement with a branchwise selection of two fresh
fair outcomes, checks binary phase and all values, and carries the endpoint
wire permutation through the remaining native program. No input-dependent
measurement or classical approximation to a quantum owner is used.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path
import shlex
import sys
import time

import numpy as np

BASE = Path(__file__).resolve().parents[2]
ENGINE = BASE/'incumbent_sources/frozen_source/fusion/runtime/work/c10/narrow/checkpoint002/cleanroom/baseline_stage97/engine'
sys.path.insert(0, str(ENGINE))
from branch_prover import Operation, Program

NOTICE = 'Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.'
PARENT = BASE/'root/q43_phase_and_late_width_v1/candidate_text.kmx'
PARENT_SHA = '501f1d90c3a82c45c6a60d6ec478bd89c91ebc3f72e847cc56f8d4182a014e43'
ORIGINAL = BASE/'agents/temporal_merges/q43_integrated_width_base_v1/candidate_text.kmx'
ORIGINAL_SHA = '23f2ecd3f88f4b72d7657abae0027511d64ec0201d4985e004608e15b11144c3'
ROOT_MASKS = BASE/'root/q43_phase_and_late_width_root_v1/ALL_INPUT_ALL_HMR_OCCUPANCY.json.gz'
ROOT_REPORT = BASE/'root/q43_phase_and_late_width_root_v1/REPORT.json'
N = 3133452


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path):
    return dict(path=str(path.resolve().relative_to(BASE)), bytes=path.stat().st_size, sha256=sha(path))


def px(a, b):
    if not a:
        return b.copy()
    if not b:
        return a.copy()
    out = a.copy()
    for k, v in b.items():
        z = out.get(k, 0) ^ v
        if z:
            out[k] = z
        else:
            out.pop(k, None)
    return out


def pm(a, b):
    out = {}
    for k, v in a.items():
        for j, w in b.items():
            z = v & w
            if not z:
                continue
            key = k | j
            z ^= out.get(key, 0)
            if z:
                out[key] = z
            else:
                out.pop(key, None)
    return out


def poly_digest(poly):
    h = hashlib.sha256()
    for mon, value in sorted(poly.items()):
        a = mon.to_bytes((mon.bit_length()+7)//8, 'little')
        b = value.to_bytes((N+7)//8, 'little')
        h.update(len(a).to_bytes(4, 'little'))
        h.update(a)
        h.update(b)
    return h.hexdigest()


def initial_state(program):
    xs = np.arange(1, N+1, dtype=np.uint64)
    state = {q: {} for q in program.wires}
    for bit, q in enumerate(program.registers['x']):
        v = int.from_bytes(np.packbits(((xs >> bit) & 1).astype(np.uint8), bitorder='little').tobytes(), 'little')
        state[q] = {0: v} if v else {}
    return state


def replay(ops, initial, *, phase=False, outcomes=None, captures=(), masks=False,
           checks=None, require_closed=True):
    full = (1 << N)-1
    one = {0: full}
    state = {q: p.copy() for q, p in initial.items()}
    state.update({'0': {}, 'False': {}, '1': one, 'True': one})
    stack = [one]
    binary = {}
    rotations = []
    saved = {}
    live = []
    quantum = [f'q{i}' for i in range(44)]

    def record(i):
        if i in captures:
            assert stack == [one], ('Entry is under a condition', i)
            saved[i] = {q: p.copy() for q, p in state.items()}
        if masks:
            live.append(sum(1 << i for i, q in enumerate(quantum) if state[q]))
        if checks and i in checks:
            checks[i](state, stack)

    for i, op in enumerate(ops):
        record(i)
        k, a = op.kind, op.arguments
        g = stack[-1] if op.condition is None else pm(stack[-1], state[op.condition])
        if k == 'PUSH_CONDITION':
            stack.append(g)
        elif k == 'POP_CONDITION':
            assert len(stack) > 1
            stack.pop()
        elif g:
            if k in ('X', 'BIT_INVERT'):
                state[a[0]] = px(state[a[0]], g)
            elif k == 'CX':
                state[a[1]] = px(state[a[1]], pm(g, state[a[0]]))
            elif k == 'CCX':
                state[a[2]] = px(state[a[2]], pm(g, pm(state[a[0]], state[a[1]])))
            elif k in ('SWAP', 'CSWAP'):
                u, v = a[-2:]
                d = pm(g, px(state[u], state[v]))
                if k == 'CSWAP':
                    d = pm(d, state[a[0]])
                state[u], state[v] = px(state[u], d), px(state[v], d)
            elif k == 'HMR':
                outcome = outcomes[op.event] if outcomes and op.event in outcomes else {1 << op.event: full}
                if phase:
                    binary = px(binary, pm(g, pm(outcome, state[a[0]])))
                state[a[0]] = px(state[a[0]], pm(g, state[a[0]]))
                state[a[1]] = px(state[a[1]], pm(g, px(state[a[1]], outcome)))
            elif k in ('BIT_STORE0', 'BIT_STORE1'):
                desired = one if k == 'BIT_STORE1' else {}
                state[a[0]] = px(state[a[0]], pm(g, px(state[a[0]], desired)))
            elif k in ('Z', 'CZ', 'CCZ', 'NEG'):
                if phase:
                    value = one
                    for q in a:
                        value = pm(value, state[q])
                    binary = px(binary, pm(g, value))
            elif k == 'Z_POW':
                if phase:
                    rotations.append((op.half_turns, pm(g, state[a[0]])))
            elif k == 'R':
                assert not pm(g, state[a[0]]), ('Nonzero reset', i, a)
            else:
                raise AssertionError((i, k))
    record(len(ops))
    if require_closed:
        assert stack == [one]
    return dict(state=state, phase=binary, rotations=rotations, captures=saved, masks=live)


def decimal(value):
    num, den = value.numerator, value.denominator
    assert den & (den-1) == 0
    places = den.bit_length()-1
    digits = str(abs(num)*5**places).zfill(places+1)
    ans = digits if not places else digits[:-places]+'.'+digits[-places:]
    if num < 0:
        ans = '-'+ans
    assert Fraction(ans) == value
    return ans


def literal(op):
    row = [op.kind, *op.arguments]
    if op.half_turns is not None:
        row.append(decimal(op.half_turns))
    if op.condition is not None:
        row += ['if', op.condition]
    return ' '.join(row)


def semantic(op):
    return op.kind, op.arguments, op.condition, op.half_turns


def local_replacement(parent, plan, extra_event):
    old = parent.operations[plan['start']:plan['end']]
    r, newborn = plan['retiring_owner'], plan['newborn_owner']
    assert all('q21' not in o.arguments and o.condition != 'q21' for o in old)
    assert old[0].kind == 'PUSH_CONDITION' and old[0].condition == 'b361'
    assert old[-1].kind == 'HMR' and old[-1].arguments[0] == r and old[-1].condition is None
    assert sum(o.kind == 'HMR' for o in old) == 1
    assert not any(o.kind == 'Z_POW' for o in old)
    result = [Operation('CX', ('q21', r), 'b979'), Operation('CX', (r, 'q21'), 'b979')]
    origins = [None, None]
    for i, o in enumerate(old[:-1], plan['start']):
        if r in o.arguments or o.condition == r:
            # No nonlinear gate is newly guarded. Its firing probability stays
            # exactly as in the already qualified parent.
            assert o.kind not in ('CCX', 'CCZ', 'CSWAP')
            result += [Operation('PUSH_CONDITION', (), 'b361'), o, Operation('POP_CONDITION', ())]
            origins += [None, i, None]
        else:
            result.append(o)
            origins.append(i)
    result += [replace(old[-1], condition='b361'),
               Operation('HMR', (newborn, old[-1].arguments[1]), 'b979', event=extra_event)]
    origins += [plan['end']-1, None]
    return result, origins


def runs(masks, target):
    out = []
    start = None
    for i, mask in enumerate(masks):
        yes = mask.bit_count() == target
        if yes and start is None:
            start = i
        if start is not None and (not yes or i == len(masks)-1):
            out.append([start, i if not yes else i+1])
            start = None
    return out


def write_gz(path, data):
    with path.open('wb') as f:
        with gzip.GzipFile(fileobj=f, mode='wb', filename='', mtime=0) as z:
            z.write((json.dumps(data, separators=(',', ':'))+'\n').encode())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=Path(__file__).resolve().parent/'later_bank_guard_sharing_v1')
    args = parser.parse_args()
    began = time.monotonic()
    assert sha(PARENT) == PARENT_SHA and sha(ORIGINAL) == ORIGINAL_SHA
    parent = Program(PARENT.read_text())
    original = Program(ORIGINAL.read_text())
    assert len(parent.operations) == 35445 and parent.measurements == 1280
    root = json.loads(ROOT_REPORT.read_text())
    assert root['native_sha256'] == PARENT_SHA and root['every_HMR_branch']
    root_masks = json.load(gzip.open(ROOT_MASKS, 'rt'))
    root_masks = root_masks.get('masks', root_masks.get('occupied_owner_masks'))
    assert root_masks is not None
    plans = []
    for j, (a, b, r, newborn, peak) in enumerate([
        (19286, 19329, 'q7', 'q36', [19294, 19329]),
        (19405, 19439, 'q26', 'q7', [19413, 19439]),
        (19467, 19495, 'q8', 'q26', [19475, 19495]),
    ]):
        start, end = a-108, b-108
        assert all(semantic(original.operations[i]) == semantic(parent.operations[i-108]) for i in range(a, b))
        plans.append(dict(index=j, original_integrated_interval=[a, b], start=start, end=end,
                          retiring_owner=r, newborn_owner=newborn, parked_owner='q21',
                          classical_branch_bit='b979', complementary_bit='b361',
                          original_peak_window=[c-108 for c in peak],
                          parent_HMR_event=parent.operations[end-1].event,
                          extra_formal_HMR_event=parent.measurements+j))
    entries = {p['start'] for p in plans}
    initial = initial_state(parent)
    prefix = replay(parent.operations[:plans[-1]['end']], initial, captures=entries)
    full = (1 << N)-1
    one = {0: full}
    event = next(o.event for o in parent.operations if o.kind == 'HMR' and o.arguments[1] == 'b979')
    branch = {1 << event: full}
    complement = px(one, branch)
    proof_rows = []
    replacements = []
    for plan in plans:
        state = prefix['captures'][plan['start']]
        r, newborn = plan['retiring_owner'], plan['newborn_owner']
        assert state['b979'] == branch and state['b361'] == complement
        assert not pm(complement, state['q21']), ('Parked owner has data in branch0', plan)
        assert not pm(branch, state[r]), ('Retiring owner has data in branch1', plan)
        assert not state[newborn], ('Newborn owner is not initially zero', plan)
        changed, origins = local_replacement(parent, plan, plan['extra_formal_HMR_event'])
        u = {1 << plan['parent_HMR_event']: full}
        v = {1 << plan['extra_formal_HMR_event']: full}
        mixed = px(pm(complement, u), pm(branch, v))
        old_result = replay(parent.operations[plan['start']:plan['end']], state, phase=True,
                            outcomes={plan['parent_HMR_event']: mixed}, masks=True)
        def zero_check(s, stack):
            assert stack == [one]
            assert s['b979'] == branch and s['b361'] == complement
            assert not pm(branch, s[newborn]), 'Companion HMR must measure exact zero'
        new_result = replay(changed, state, phase=True, masks=True,
                            checks={len(changed)-1: zero_check})
        for q in state:
            target = r if q == 'q21' else 'q21' if q == r else q
            assert old_result['state'][q] == new_result['state'][target], ('Endpoint value mismatch', plan['index'], q)
        assert old_result['phase'] == new_result['phase'], ('Binary phase mismatch', plan['index'])
        assert old_result['rotations'] == new_result['rotations'] == []
        assert max(m.bit_count() for m in new_result['masks']) <= 43
        assert max(m.bit_count() for m in old_result['masks']) == 44
        row = dict(status='EXACT_ALL_INPUT_ALL_HMR_LOCAL_VALUE_PHASE_AND_WIDTH_PASS',
                   original_inputs=N, parent_HMR_variables=parent.measurements,
                   comparison_HMR_variables=parent.measurements+3,
                   branch_event=event, parent_interval=[plan['start'], plan['end']],
                   original_operations=plan['end']-plan['start'], changed_operations=len(changed),
                   original_peak=44, changed_peak=43,
                   original_peak_cuts=sum(m.bit_count() == 44 for m in old_result['masks']),
                   original_HMR_event=plan['parent_HMR_event'], extra_HMR_event=plan['extra_formal_HMR_event'],
                   original_outcome_substitution='(1 XOR branch)*original_event XOR branch*extra_event',
                   outcome_distribution='The branch is determined by an earlier HMR. Both fresh outcomes are independent and fair, so their branchwise selection is conditionally fair. The extra HMR acts on an exactly zero owner.',
                   binary_phase_polynomial_terms=len(old_result['phase']),
                   matching_binary_phase_sha256=poly_digest(old_result['phase']),
                   matching_classical_values=True, matching_quantum_values_after_endpoint_swap=True,
                   endpoint_swap=['q21', r], rotations_checked=0,
                   nonlinear_gate_additions=0, expected_Toffoli_delta='0',
                   replacement=[literal(o) for o in changed])
        proof_rows.append(row)
        replacements.append((changed, origins))
    print(json.dumps(dict(status='LOCAL_PROOFS_PASS', plans=len(plans), removed_parent_peak_cuts=81, seconds=time.monotonic()-began)), flush=True)

    mapping = {f'q{i}': f'q{i}' for i in range(44)}
    result = []
    origins = []
    cut_map = []
    swaps = []
    cursor = 0
    def append(op, origin):
        result.append(replace(op, arguments=tuple(mapping.get(a, a) for a in op.arguments),
                              condition=mapping.get(op.condition, op.condition)))
        origins.append(origin)
    for plan, (changed, changed_origins) in zip(plans, replacements):
        for i in range(cursor, plan['start']):
            cut_map.append([i, len(result)])
            append(parent.operations[i], i)
        plan['new_start'] = len(result)
        plan['entry_physical_mapping'] = {q: v for q, v in mapping.items() if q != v}
        for op, origin in zip(changed, changed_origins):
            if origin is not None:
                cut_map.append([origin, len(result)])
            append(op, origin)
        r = plan['retiring_owner']
        physical_pair = [mapping['q21'], mapping[r]]
        swaps.append(physical_pair)
        mapping['q21'], mapping[r] = mapping[r], mapping['q21']
        plan['physical_endpoint_swap'] = physical_pair
        plan['new_end'] = len(result)
        plan['exit_physical_mapping'] = {q: v for q, v in mapping.items() if q != v}
        cursor = plan['end']
    for i in range(cursor, len(parent.operations)):
        cut_map.append([i, len(result)])
        append(parent.operations[i], i)
    cut_map.append([len(parent.operations), len(result)])
    restore_start = len(result)
    final_mapping = {q: v for q, v in mapping.items() if q != v}
    # Revert the accumulated physical permutation after all original native
    # operations. Only the input register is occupied at this endpoint.
    for a, b in reversed(swaps):
        for op in [Operation('CX', (a, b)), Operation('CX', (b, a)), Operation('CX', (a, b))]:
            result.append(op)
            origins.append(None)
        mapping = {q: b if v == a else a if v == b else v for q, v in mapping.items()}
    assert all(q == v for q, v in mapping.items())
    metadata = []
    for line in PARENT.read_text().splitlines():
        tokens = shlex.split(line, comments=True)
        if tokens and tokens[0] in ('APPEND_TO_REGISTER', 'REGISTER'):
            metadata.append(line)
    text = '# '+NOTICE+'\n'+'\n'.join(metadata+[literal(o) for o in result])+'\n'
    candidate = Program(text)
    assert len(candidate.operations) == len(result)
    assert candidate.measurements == parent.measurements+3
    assert candidate.registers == parent.registers
    # Compare the entire costly/rotation gate guard stacks through the mapping.
    def costly_guards(program):
        stack = []
        rows = []
        for op in program.operations:
            if op.kind == 'PUSH_CONDITION':
                stack.append(op.condition)
            elif op.kind == 'POP_CONDITION':
                stack.pop()
            elif op.kind in ('CCX', 'CCZ', 'CSWAP', 'Z_POW'):
                rows.append((op.kind, tuple(stack), op.condition, op.half_turns))
        assert not stack
        return rows
    assert costly_guards(candidate) == costly_guards(parent)
    value_check = replay(candidate.operations, initial, masks=True)
    for q in candidate.quantum_wires:
        assert value_check['state'][q] == initial[q], ('Full native final value mismatch', q)
    masks = value_check['masks']
    for p in plans:
        assert max(m.bit_count() for m in masks[p['new_start']:p['new_end']+1]) <= 43
    assert max(m.bit_count() for m in masks[restore_start:]) <= 23
    parent_peak_cuts = sum(m.bit_count() == 44 for m in root_masks)
    peak_cuts = sum(m.bit_count() == 44 for m in masks)
    assert parent_peak_cuts-peak_cuts == 81, (parent_peak_cuts, peak_cuts)
    assert max(m.bit_count() for m in masks) == 44
    args.out.mkdir(exist_ok=False, parents=True)
    native = args.out/'candidate_text.kmx'
    native.write_text(text)
    map_path = args.out/'OPERATION_MAP.json.gz'
    write_gz(map_path, dict(notice=NOTICE, parent_native_sha256=PARENT_SHA, native_sha256=sha(native),
                           old_to_new_cut_map=cut_map, candidate_operation_to_parent_operation=origins))
    mask_path = args.out/'ALL_INPUT_ALL_HMR_OCCUPANCY.json.gz'
    write_gz(mask_path, dict(notice=NOTICE, native_sha256=sha(native), masks=masks))
    report = dict(notice=NOTICE, status='AGENT_EXACT_GUARDED_SHARING_EMISSION_LOCAL_PHASE_PROOFS_AND_FULL_VALUE_WIDTH_PASS',
                  root_qualification_pending=True, native_sha256=sha(native), parent_native_sha256=PARENT_SHA,
                  original_integrated_native_sha256=ORIGINAL_SHA,
                  parent_expected_Toffolis='11573/8', expected_Toffoli_delta='0',
                  resulting_expected_Toffolis_by_unchanged_costly_guards='11573/8',
                  global_Q=44, global_Q43_claim=False, original_inputs=N, every_HMR_branch=True,
                  parent_operations=len(parent.operations), operations=len(candidate.operations),
                  parent_HMR=parent.measurements, HMR=candidate.measurements,
                  parent_peak44_cuts=parent_peak_cuts, peak44_cuts=peak_cuts,
                  removed_peak44_cuts=81, parent_peak44_windows=len(root['peak44_windows']),
                  peak44_windows=runs(masks, 44), histogram=dict(sorted(Counter(m.bit_count() for m in masks).items())),
                  plans=plans, local_proofs=proof_rows, added_routing_CX=6,
                  endpoint_permutation=final_mapping, final_restore_CX=9,
                  final_restore_start=restore_start, exact_final_input_values=True,
                  phase_semantics='Each local identity is exact after substituting a conditionally fair branchwise-selected HMR outcome into the parent. It preserves every classical state and all quantum states under the explicit endpoint permutation. Later operations are renamed by that permutation, and three free SWAP decompositions restore the original input register at the end. Parent full-domain qualification is bound separately; root full qualification of this emitted native remains pending.',
                  permissions='Routing guards are only the already available classical HMR b979 and its exact complement b361. No input-dependent measurement or discarded coherent value is introduced.',
                  successors=[
                      dict(route='Classical branch sharing at remaining later-bank partial window', scope='The first 32 cuts of old integrated [19504,19601) have branch maximum43, then a branch reaches44. A causal early retirement or changed owner at cut19536 is still needed.', model_expected_Toffolis='11573/8 plus any newly proved boundary repair', cap_for_Q43_improvement='251427/172', state='OPEN_BOUNDARY_REPAIR'),
                      dict(route='Retire and recompute a read-crossing helper', scope='Remaining later conditional-bank peaks with a literal one-AND owner whose reads can be moved or synthesized.', added_cost='One unconditional recomputation adds1; a fair HMR-conditioned one adds1/2. Total new cost must remain below5215/344 after this parent.', state='OPEN_ACTUAL_OWNER_AND_PHASE_CHECKS'),
                      dict(route='Eliminate a helper used only by a quartic phase', scope='Use a borrowed live target for a two-AND/two-CCZ commutator with exact restore, if its controls and causal ownership are available.', added_cost='At most4 per unconditional quartic phase, or2 under a fair independent classical HMR guard, less any removed helper cost.', state='OPEN_LITERAL_PHASE_AND_TIMING_CHECKS')],
                  bindings=[bind(p) for p in [Path(__file__), ENGINE/'branch_prover.py', PARENT, ORIGINAL, ROOT_REPORT, ROOT_MASKS, native, map_path, mask_path]],
                  reproduction_command=f'/usr/bin/python3.13 agents/paid_helper/emit_later_bank_guard_sharing.py --out agents/paid_helper/later_bank_guard_sharing_rebuild',
                  seconds=time.monotonic()-began)
    (args.out/'REPORT.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(status=report['status'], native_sha256=report['native_sha256'],
                          operations=report['operations'], HMR=report['HMR'],
                          peak44_cuts=peak_cuts, peak44_windows=len(report['peak44_windows']),
                          expected_Toffolis=report['resulting_expected_Toffolis_by_unchanged_costly_guards'],
                          seconds=report['seconds'])), flush=True)


if __name__ == '__main__':
    main()
