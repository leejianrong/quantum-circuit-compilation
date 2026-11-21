# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Extend branch sharing with one shared, deferred measurement-phase helper.

A carry retires before the parked owner's next write. Its cubic phase waits
until the next helper retires, then shares a temporary with the latter's
quartic feedback. The temporary is prepared only when at least one of the
two fair measurement outcomes is one. Boolean majority factorization reduces
the feedback to two CCZs. Exact net expected cost is5/8.
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
import time

import emit_later_bank_guard_sharing as r

FIRST_REPORT = r.BASE/'agents/paid_helper/later_bank_guard_sharing_rebuild_v2/REPORT.json'
FIRST_REPORT_SHA = 'b72a4597841d372755edabce8cc10de593ce2ae38bd6395a4b6683cfba58ecb2'
CLASSICAL_OR = 'b5000'


def op(text, event=None):
    result = r.Program(text+'\n').operations
    assert len(result) == 1
    return replace(result[0], event=event) if result[0].kind == 'HMR' else result[0]


def fourth_replacement(parent, plan):
    out, origins = [], []
    def add(text, event=None):
        out.append(op(text, event))
        origins.append(None)
    def original(i, swap=False):
        o = parent.operations[i]
        if swap:
            mp = {'q21': 'q26', 'q26': 'q21'}
            o = replace(o, arguments=tuple(mp.get(a, a) for a in o.arguments))
        out.append(o)
        origins.append(i)
    add('CX q21 q26 if b979')
    add('CX q26 q21 if b979')
    for i in range(plan['start'], 19535-108):
        old = parent.operations[i]
        assert 'q21' not in old.arguments
        if 'q26' in old.arguments:
            assert old.kind not in ('CCX', 'CCZ', 'CSWAP')
            add('PUSH_CONDITION if b361')
            original(i)
            add('POP_CONDITION')
        else:
            original(i)
    # Temporarily close the current b361 scope. The complementary zero HMR
    # must fire outside it, preserving the original unconditional fair bit.
    add('POP_CONDITION')
    plan['early_HMR_local_index'] = len(out)
    add('HMR q26 b179 if b361', plan['m179'])
    add('HMR q21 b179 if b979', plan['extra_formal_HMR_event'])
    # The measured carry's phase is deliberately retained until the next
    # helper retires. Its exact expression in the later live values is proved.
    add('PUSH_CONDITION if b361')
    # q26 now physically contains q21 on every branch. The old q21 owner is
    # zero and will become the later temporary. All remaining original q26
    # reads are in the explicitly replaced cleanup, not this middle block.
    plan['endpoint_swap_begins_local'] = len(out)
    for i in range(19535-108, 19601-108):
        assert 'q26' not in parent.operations[i].arguments
        original(i, swap=True)
    # h26 = c+(a+c)*(b+c)+(a+b)*A*B.
    # h8 = d*e+L*c+L*(a+c)*(b+c)+L*(a+b)*A*B.
    # Prepare A*B iff m179 OR m180. Both phase debts use this one temporary.
    # q8 has just retired, giving the required physical space.
    for text in [
        f'BIT_STORE0 {CLASSICAL_OR}', f'BIT_STORE1 {CLASSICAL_OR} if b179',
        f'BIT_STORE1 {CLASSICAL_OR} if b180',
        'PUSH_CONDITION if b361', 'X q32',
        'X q28', 'CX q7 q17', 'CX q7 q28',
        f'PUSH_CONDITION if {CLASSICAL_OR}', 'CCX q17 q28 q21', 'POP_CONDITION',
        'PUSH_CONDITION if b179', 'Z q7',
        'CX q7 q18', 'CX q7 q32', 'CZ q18 q32', 'CX q7 q32', 'CX q7 q18',
        'CZ q21 q18', 'CZ q21 q32', 'POP_CONDITION',
        'PUSH_CONDITION if b180',
        'X q30', 'CZ q19 q30', 'CX q19 q30', 'CZ q30 q7',
        'CX q7 q18', 'CX q7 q32', 'CCZ q30 q18 q32', 'CX q7 q32', 'CX q7 q18',
        'CX q18 q32', 'CCZ q21 q30 q32', 'CX q18 q32',
        'CX q19 q30', 'X q30', 'POP_CONDITION', 'X q32', 'POP_CONDITION',
    ]:
        add(text)
    plan['temporary_HMR_local_index'] = len(out)
    add('HMR q21 b178', plan['m178'])
    for text in [
        'PUSH_CONDITION if b361', f'PUSH_CONDITION if {CLASSICAL_OR}',
        'PUSH_CONDITION if b178', 'CZ q17 q28', 'POP_CONDITION',
        'POP_CONDITION', 'CX q7 q28', 'CX q7 q17', 'X q28', 'POP_CONDITION',
        f'BIT_STORE0 {CLASSICAL_OR}',
    ]:
        add(text)
    return out, origins


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, default=Path(__file__).resolve().parent/'fourth_bank_deferred_phase_v1')
    args = ap.parse_args()
    args.out = args.out.resolve()
    began = time.monotonic()
    assert r.sha(r.PARENT) == r.PARENT_SHA
    assert r.sha(FIRST_REPORT) == FIRST_REPORT_SHA
    first = json.loads(FIRST_REPORT.read_text())
    parent = r.Program(r.PARENT.read_text())
    assert CLASSICAL_OR not in parent.wires
    root = json.loads(r.ROOT_REPORT.read_text())
    plans = first['plans']
    replacements = [r.local_replacement(parent, p, p['extra_formal_HMR_event']) for p in plans]
    fourth = dict(index=3, original_integrated_interval=[19495, 19637], start=19495-108, end=19637-108,
                  retiring_owner='q26', newborn_owner='q8', parked_owner='q21',
                  extra_formal_HMR_event=parent.measurements+3,
                  m180=parent.operations[19600-108].event,
                  m179=parent.operations[19610-108].event,
                  m178=parent.operations[19625-108].event,
                  original_peak_window=[19504-108, 19601-108])
    for old, q, b in [(19600, 'q8', 'b180'), (19610, 'q26', 'b179'), (19625, 'q26', 'b178')]:
        o = parent.operations[old-108]
        assert o.kind == 'HMR' and o.arguments == (q, b) and o.condition is None
    changed, changed_origins = fourth_replacement(parent, fourth)
    initial = r.initial_state(parent)
    initial[CLASSICAL_OR] = {}
    sampled = {}
    def capture(cut):
        def save(s, stack):
            sampled[cut] = {q: p.copy() for q, p in s.items()}
        return save
    prefix = r.replay(parent.operations[:fourth['end']], initial,
                      captures={fourth['start']},
                      checks={old-108: capture(old) for old in [19535, 19600, 19610]})
    state = prefix['captures'][fourth['start']]
    full = (1 << r.N)-1
    one = {0: full}
    branch = state['b979']
    complement = r.px(one, branch)
    assert len(branch) == 1 and 0 not in branch and next(iter(branch)).bit_count() == 1
    assert state['b361'] == complement
    assert not r.pm(complement, state['q21']) and not r.pm(branch, state['q26'])
    assert not state['q8']
    formula_rows = []
    for old, s in sampled.items():
        A = r.px(s['q17'], s['q7'])
        B = r.px(r.px(s['q28'], s['q7']), one)
        a, b, c = s['q18'], r.px(s['q32'], one), s['q7']
        h = r.px(r.pm(a, b), r.pm(r.px(a, b), r.px(c, r.pm(A, B))))
        assert s['q26'] == r.pm(s['b361'], h)
        row = dict(original_integrated_cut=old, h26_formula_exact=True,
                   h26_polynomial_sha256=r.poly_digest(s['q26']))
        if old == 19600:
            d, e = s['q19'], r.px(s['q30'], one)
            h8 = r.px(r.pm(d, e), r.pm(r.px(d, e), h))
            assert s['q8'] == r.pm(s['b361'], h8)
            row['h8_formula_exact'] = True
            row['h8_polynomial_sha256'] = r.poly_digest(s['q8'])
        formula_rows.append(row)
    u = {1 << fourth['m179']: full}
    v = {1 << fourth['extra_formal_HMR_event']: full}
    selected = r.px(r.pm(complement, u), r.pm(branch, v))
    old_result = r.replay(parent.operations[fourth['start']:fourth['end']], state,
                          phase=True, outcomes={fourth['m179']: selected}, masks=True)
    def companion_zero(s, stack):
        assert stack == [one] and not s['q21']
        assert s['b979'] == branch and s['b361'] == complement
    new_result = r.replay(changed, state, phase=True, masks=True,
                          checks={fourth['early_HMR_local_index']+1: companion_zero})
    for q in state:
        target = 'q26' if q == 'q21' else 'q21' if q == 'q26' else q
        assert old_result['state'][q] == new_result['state'][target], ('Local endpoint mismatch', q)
    assert old_result['phase'] == new_result['phase'], 'Local phase mismatch'
    assert old_result['rotations'] == new_result['rotations'] == []
    assert max(m.bit_count() for m in new_result['masks']) == 43
    assert sum(m.bit_count() == 44 for m in old_result['masks']) == 97
    local_proof = dict(status='EXACT_ALL_INPUT_ALL_HMR_LOCAL_PHASE_VALUE_AND_WIDTH_PASS',
                       original_inputs=r.N, parent_HMR_variables=parent.measurements,
                       extra_formal_variables=4, formulas=formula_rows,
                       parent_interval=[fourth['start'], fourth['end']],
                       original_peak=44, new_peak=43, removed_parent_peak_cuts=97,
                       matching_binary_phase_sha256=r.poly_digest(old_result['phase']),
                       binary_phase_terms=len(old_result['phase']),
                       every_classical_value_matches=True, endpoint_quantum_swap=['q21', 'q26'],
                       original_outcome_substitution='m179 := (1 XOR b979)*m179 XOR b979*extra_event',
                       exact_probability='The early branch is a prior fair classical HMR; the branchwise selected new outcome remains conditionally fair. b180 is the unchanged unconditional HMR outcome. The temporary HMR is unconditional, including its zero-helper branches.',
                       expected_Toffoli_removed='1/4', expected_Toffoli_added='7/8', expected_delta='5/8',
                       temporary_prepare_guard='b361 AND (b179 OR b180)', temporary_prepare_probability='3/8',
                       new_CCZ_count=2, each_new_CCZ_probability='1/4',
                       classical_scratch=CLASSICAL_OR, classical_scratch_restored_zero=True,
                       allocation='The parked branch uses the retiring carry owner. Its branch0 value is measured before the next q21 write. The one temporary is created only after q8 has retired and is HMR-erased before returning to the unchanged tail.',
                       replacement=[r.literal(o) for o in changed])
    plans.append(fourth)
    replacements.append((changed, changed_origins))
    print(json.dumps(dict(status='FOURTH_DEFERRED_PHASE_LOCAL_PROOF_PASS', cuts=97, expected_delta='5/8', seconds=time.monotonic()-began)), flush=True)

    mapping = {f'q{i}': f'q{i}' for i in range(44)}
    result, origins, cut_map, swaps = [], [], [], []
    cursor = 0
    def append(o, origin):
        result.append(replace(o, arguments=tuple(mapping.get(a, a) for a in o.arguments),
                              condition=mapping.get(o.condition, o.condition)))
        origins.append(origin)
    for p, (ops, old_indices) in zip(plans, replacements):
        for i in range(cursor, p['start']):
            cut_map.append([i, len(result)])
            append(parent.operations[i], i)
        p['new_start'] = len(result)
        for o, origin in zip(ops, old_indices):
            if origin is not None:
                cut_map.append([origin, len(result)])
            append(o, origin)
        retired = p['retiring_owner']
        pair = [mapping['q21'], mapping[retired]]
        swaps.append(pair)
        mapping['q21'], mapping[retired] = mapping[retired], mapping['q21']
        p['physical_endpoint_swap'] = pair
        p['new_end'] = len(result)
        cursor = p['end']
    for i in range(cursor, len(parent.operations)):
        cut_map.append([i, len(result)])
        append(parent.operations[i], i)
    cut_map.append([len(parent.operations), len(result)])
    restore_start = len(result)
    final_mapping = {q: v for q, v in mapping.items() if q != v}
    for a, b in reversed(swaps):
        for text in [f'CX {a} {b}', f'CX {b} {a}', f'CX {a} {b}']:
            result.append(op(text))
            origins.append(None)
        mapping = {q: b if v == a else a if v == b else v for q, v in mapping.items()}
    assert all(q == v for q, v in mapping.items())
    metadata = []
    for line in r.PARENT.read_text().splitlines():
        t = shlex.split(line, comments=True)
        if t and t[0] in ('REGISTER', 'APPEND_TO_REGISTER'):
            metadata.append(line)
    text = '# '+r.NOTICE+'\n'+'\n'.join(metadata+[r.literal(o) for o in result])+'\n'
    candidate = r.Program(text)
    assert candidate.registers == parent.registers and candidate.measurements == parent.measurements+4
    values = r.replay(candidate.operations, initial, masks=True)
    for q in candidate.quantum_wires:
        assert values['state'][q] == initial[q], ('Full final value mismatch', q)
    masks = values['masks']
    for p in plans:
        assert max(m.bit_count() for m in masks[p['new_start']:p['new_end']+1]) <= 43
    assert max(m.bit_count() for m in masks[restore_start:]) <= 23
    peak_cuts = sum(m.bit_count() == 44 for m in masks)
    assert peak_cuts == 1272-81-97 == 1094
    assert len(r.runs(masks, 44)) == 142
    args.out.mkdir(parents=True, exist_ok=False)
    native = args.out/'candidate_text.kmx'
    native.write_text(text)
    map_path = args.out/'OPERATION_MAP.json.gz'
    r.write_gz(map_path, dict(notice=r.NOTICE, parent_native_sha256=r.PARENT_SHA, native_sha256=r.sha(native),
                              old_to_new_cut_map=cut_map, candidate_operation_to_parent_operation=origins))
    mask_path = args.out/'ALL_INPUT_ALL_HMR_OCCUPANCY.json.gz'
    r.write_gz(mask_path, dict(notice=r.NOTICE, native_sha256=r.sha(native), masks=masks))
    report = dict(notice=r.NOTICE, status='AGENT_EXACT_FOUR_BANK_GUARD_SHARING_WITH_SHARED_DEFERRED_PHASE_HELPER_PASS',
                  root_qualification_pending=True, native_sha256=r.sha(native), parent_native_sha256=r.PARENT_SHA,
                  original_inputs=r.N, every_HMR_branch=True,
                  model_parent_expected_Toffolis='11573/8', model_delta='5/8', model_expected_Toffolis='5789/4',
                  model_Q43_break_even='251427/172', remaining_model_headroom='625/43',
                  global_Q=44, global_Q43_claim=False, parent_operations=len(parent.operations), operations=len(candidate.operations),
                  parent_HMR=parent.measurements, HMR=candidate.measurements,
                  inherited_first_three_proof=r.bind(FIRST_REPORT), fourth_local_proof=local_proof,
                  parent_peak44_cuts=1272, peak44_cuts=peak_cuts, removed_peak44_cuts=178,
                  parent_peak44_windows=146, peak44_windows=r.runs(masks, 44),
                  histogram=dict(sorted(Counter(m.bit_count() for m in masks).items())),
                  plans=plans, endpoint_permutation=final_mapping, final_restore_CX=12,
                  final_input_values_exact=True,
                  cost_derivation='Remove one carry-cleanup AND of probability1/4. Prepare one shared AB temporary under b361 AND (b179 OR b180), exact probability3/8. Apply two CCZs under b361 AND b180, each probability1/4. All other phase corrections, the temporary HMR correction, classical OR computation and physical routing are free Clifford/classical operations. Net3/8+2/4-1/4=5/8.',
                  successors=[
                      dict(route='Earlier carry retirement in the first remaining conditional-bank windows', scope='Bound integrated windows16355..16460 and16817..16837, with actual phase/read reconstruction.', model_added_cost='A cubic carry phase can replace one conditional AND at equal cost; a quartic late feedback using one temporary costs at most1 under two fair guards.', state='OPEN'),
                      dict(route='Changed affine owner charts on a fixed HMR branch', scope='Remaining later-bank windows18713..18909 and18938..18981. Root owns the global branch-chart census; this lane can emit actual local witnesses it finds.', model_added_cost='Clifford-only for an exact affine dependency, otherwise count every needed recomputation.', state='OPEN_COORDINATE_WITH_ROOT'),
                      dict(route='Read-crossing recomputation with one clean owner', scope='Virtualize a carry/helper across a peak and recreate it only after another owner has retired.', model_added_cost='One conditional AND costs its exact classical guard probability; cumulative additions must remain below625/43 for the Q43 target.', state='OPEN')],
                  bindings=[r.bind(p) for p in [Path(__file__), Path(r.__file__), r.ENGINE/'branch_prover.py', r.PARENT, FIRST_REPORT, r.ROOT_REPORT, native, map_path, mask_path]],
                  reproduction_command='/usr/bin/python3.13 agents/paid_helper/emit_fourth_bank_deferred_phase.py --out agents/paid_helper/fourth_bank_deferred_phase_rebuild_v1',
                  seconds=time.monotonic()-began)
    (args.out/'REPORT.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(status=report['status'], native_sha256=report['native_sha256'], operations=report['operations'],
                          HMR=report['HMR'], peak44_cuts=peak_cuts, windows=142,
                          model_expected_Toffolis=report['model_expected_Toffolis'], seconds=report['seconds'])), flush=True)


if __name__ == '__main__':
    main()
