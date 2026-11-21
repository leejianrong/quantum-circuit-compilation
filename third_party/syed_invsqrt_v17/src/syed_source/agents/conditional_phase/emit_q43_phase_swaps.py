# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Replace an ancilla-controlled phase sandwich by two physical CSWAPs.

The removed measurement is used only by its exact local binary cleanup and is
overwritten before its next read. Every selected middle block preserves its
three swap operands and never reads the retired helper. A universal Boolean
polynomial proof checks values, all HMR phase coefficients, and each exact
fractional phase argument. An optional complete-input replay checks the live
width of the changed interval; this is not a claim of global Q43.
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

from retime_hmr import NOTICE, Program, original_guards, probability, sha


def px(*polys):
    out = {}
    for poly in polys:
        for m, v in poly.items():
            out[m] = out.get(m, 0) ^ v
    return {m: v for m, v in out.items() if v}


def pm(a, b):
    out = {}
    for i, u in a.items():
        for j, v in b.items():
            out[i | j] = out.get(i | j, 0) ^ (u & v)
    return {m: v for m, v in out.items() if v}


def replay(operations, initial, full, *, event_offset=0, keep_masks=False,
           entry_checks=None):
    state = {q: dict(p) for q, p in initial.items()}
    one = {0: full}
    state.update({'0': {}, 'False': {}, '1': one, 'True': one})
    stack, phase, rotations, masks = [one], {}, [], []
    def record():
        if keep_masks:
            masks.append(sum(bool(v) << int(q[1:]) for q, v in state.items()
                             if q.startswith('q') and q[1:].isdigit()))
    record()
    for index, op in enumerate(operations):
        if entry_checks and index in entry_checks:
            assert not state[entry_checks[index]], ('Helper not zero', index)
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
                outcome = {1 << (event_offset + op.event): full}
                phase = px(phase, pm(g, pm(outcome, state[a[0]])))
                state[a[0]] = px(state[a[0]], pm(g, state[a[0]]))
                state[a[1]] = px(state[a[1]], pm(g, px(state[a[1]], outcome)))
            elif k in ('BIT_STORE0', 'BIT_STORE1'):
                value = one if k == 'BIT_STORE1' else {}
                state[a[0]] = px(state[a[0]], pm(g, px(state[a[0]], value)))
            elif k in ('Z', 'CZ', 'CCZ', 'NEG'):
                v = one
                for q in a:
                    v = pm(v, state[q])
                phase = px(phase, pm(g, v))
            elif k == 'Z_POW':
                rotations.append((op.half_turns, pm(g, state[a[0]])))
            elif k == 'R':
                assert not pm(g, state[a[0]])
            else:
                raise AssertionError(k)
        record()
    assert stack == [one]
    return state, phase, rotations, masks


def finite_decimal(value):
    """The native compiler requires decimals, not Fraction's a/b syntax."""
    numerator, denominator = value.numerator, value.denominator
    assert denominator & (denominator-1) == 0, denominator
    places = denominator.bit_length()-1
    digits = str(abs(numerator)*5**places).zfill(places+1)
    result = digits if not places else digits[:-places]+'.'+digits[-places:]
    if numerator < 0:
        result = '-'+result
    assert Fraction(result) == value
    return result


def literal(op):
    fields = [op.kind, *op.arguments]
    if op.half_turns is not None:
        fields.append(finite_decimal(op.half_turns))
    if op.condition is not None:
        fields += ['if', op.condition]
    return ' '.join(fields)


def find_plans(program, selection):
    ops = program.operations
    guards = original_guards(program)
    plans = []
    for i, op in enumerate(ops):
        if op.kind != 'CCX' or i < 2:
            continue
        c, b, t = op.arguments
        pre, post = ops[i-2:i], ops[i+1:i+5]
        a = pre[1].arguments[0] if pre[1].kind == 'CX' else None
        if not (pre[0].kind == 'X' and pre[0].arguments == (c,)
                and pre[1].arguments == (a, b)
                and [(o.kind, o.arguments) for o in post] ==
                [('CX', (a, b)), ('X', (c,)), ('CX', (t, a)), ('CX', (t, b))]):
            continue
        j = next((j for j in range(i+5, len(ops)) if t in ops[j].arguments), None)
        if j is None or j+9 > len(ops):
            continue
        closing = ops[j:j+9]
        expected = [('CX', (t, a)), ('CX', (t, b)), ('HMR', None),
                    ('X', (c,)), ('PUSH_CONDITION', ()), ('CZ', (c, a)),
                    ('CZ', (c, b)), ('POP_CONDITION', ()), ('X', (c,))]
        if not all(o.kind == k and (aa is None or o.arguments == aa)
                   for o, (k, aa) in zip(closing, expected)):
            continue
        h = closing[2]
        m = h.arguments[1]
        if h.arguments[0] != t or closing[4].condition != m:
            continue
        simple = j == i+7 and all(o.kind == 'Z_POW' for o in ops[i+5:j])
        # The eighth simple q43 gadget has no 44-owner peak on the bound base.
        category = 'simple_q8' if simple and t == 'q8' else 'outer' if not simple else 'unused_simple'
        if category == 'unused_simple' or selection == 'simple' and category != 'simple_q8' or selection == 'outer' and category != 'outer':
            continue
        assert len({c, a, b, t}) == 4
        assert all(guards[k] == {0} and ops[k].condition is None
                   for k in [*range(i-2, i+5), j, j+1, j+2, j+3, j+8])
        assert all(o.condition is None for o in closing[5:7])
        next_write = None
        for u in range(j+9, len(ops)):
            o = ops[u]
            assert o.condition != m, ('Outcome remains live', i, m, u)
            if o.kind == 'HMR' and o.arguments[1] == m or o.kind in ('BIT_STORE0', 'BIT_STORE1') and o.arguments[0] == m:
                assert guards[u] == {0} and o.condition is None
                next_write = u
                break
            assert m not in o.arguments, ('Outcome data remains live', i, m, u)
        assert next_write is not None
        body = list(range(i+5, j))
        entries = [(f'X {c}', None), (f'CSWAP {c} {a} {b}', None), (f'X {c}', None)]
        entries += [(literal(ops[u]), u) for u in body]
        entries += [(f'X {c}', None), (f'CSWAP {c} {a} {b}', None),
                    (f'X {c}', None), (f'BIT_STORE0 {m}', None)]
        native = '\n'.join(literal(o) for o in ops[i-2:j+9])+'\n'
        plans.append(dict(category=category, start=i-2, end=j+9, birth=i,
                          body_start=i+5, body_end=j, control=c, left=a, right=b,
                          helper=t, removed_HMR_event=h.event, removed_HMR_operation=j+2,
                          dead_classical_owner=m, next_unconditional_overwrite=next_write,
                          exact_gate_firing_probability=str(probability(guards[i])),
                          added_expected_Toffolis='1', original_block_sha256=hashlib.sha256(native.encode()).hexdigest(),
                          original_block=native, replacement=[s for s, _ in entries],
                          origins=[u for _, u in entries]))
    expected = {'simple': 7, 'outer': 5, 'all': 12}[selection]
    assert len(plans) == expected, (selection, len(plans))
    assert all(a['end'] <= b['start'] for a, b in zip(plans, plans[1:]))
    return plans


def changed_ops(plan, parent):
    result = Program('\n'.join(plan['replacement'])+'\n').operations
    for i, origin in enumerate(plan['origins']):
        if origin is not None and result[i].kind == 'HMR':
            result[i] = replace(result[i], event=parent.operations[origin].event)
    return result


def universal_check(plan, parent):
    before = parent.operations[plan['start']:plan['end']]
    after = changed_ops(plan, parent)
    wires = sorted({q for o in [*before, *after] for q in (*o.arguments, *([o.condition] if o.condition else []))
                    if q.startswith(('q', 'b'))})
    state = {q: {1 << i: 1} for i, q in enumerate(wires)}
    state[plan['helper']] = {}
    original = replay(before, state, 1, event_offset=len(wires))
    changed = replay(after, state, 1, event_offset=len(wires))
    for q in wires:
        if q != plan['dead_classical_owner']:
            assert original[0][q] == changed[0][q], (plan['start'], q)
    assert original[1] == changed[1], ('Universal binary phase mismatch', plan['start'])
    assert original[2] == changed[2], ('Universal fractional mask mismatch', plan['start'])
    # Verify the middle block preserves all operands used by the outer undo.
    body_result = replay(parent.operations[plan['body_start']:plan['body_end']], state, 1, event_offset=len(wires))
    for q in (plan['control'], plan['left'], plan['right']):
        assert body_result[0][q] == state[q], ('Middle changes swap operand', q)
    return dict(status='UNIVERSAL_BOOLEAN_VALUE_AND_ALL_HMR_PHASE_IDENTITY_PASS',
                independent_initial_bits=len(wires)-1,
                original_HMR_count=sum(o.kind == 'HMR' for o in before),
                retained_HMR_count=sum(o.kind == 'HMR' for o in after),
                fractional_arguments_checked=len(original[2]),
                arbitrary_middle_input_bits=True, helper_initial_zero_required=True,
                ignored_classical_output=plan['dead_classical_owner'],
                ignored_output_overwritten_before_next_read=plan['next_unconditional_overwrite'])


def full_interval_check(parent, plans, changed, origins, new_starts, new_ends):
    import numpy as np
    n = 3133452
    xs = np.arange(1, n+1, dtype=np.uint64)
    full = (1 << n)-1
    state = {q: {} for q in parent.wires}
    for bit, q in enumerate(parent.registers['x']):
        v = int.from_bytes(np.packbits(((xs >> bit) & 1).astype(np.uint8), bitorder='little').tobytes(), 'little')
        state[q] = {0: v} if v else {}
    del xs
    start, end = plans[0]['start'], plans[-1]['end']
    state = replay(parent.operations[:start], state, full)[0]
    checks = {p['start']-start: p['helper'] for p in plans}
    old = replay(parent.operations[start:end], state, full, keep_masks=True, entry_checks=checks)
    aa, bb = new_starts[start], new_ends[end]
    operations = list(changed.operations[aa:bb])
    for j, origin in enumerate(origins[aa:bb]):
        if origin is not None and operations[j].kind == 'HMR':
            operations[j] = replace(operations[j], event=parent.operations[origin].event)
    new = replay(operations, state, full, keep_masks=True)
    for q in state:
        if q != plans[-1]['dead_classical_owner']:
            assert old[0][q] == new[0][q], ('Complete-input output mismatch', q)
    assert old[1] == new[1]
    assert old[2] == new[2]
    windows = []
    for p in plans:
        lo, hi = new_starts[p['start']]-aa, new_ends[p['end']]-aa
        hist = Counter(m.bit_count() for m in new[3][lo:hi+1])
        assert max(hist) <= 43, (p['start'], hist)
        windows.append(dict(parent_interval=[p['start'], p['end']],
                            output_interval=[lo+aa, hi+aa], helper=p['helper'],
                            peak=max(hist), histogram=dict(sorted(hist.items()))))
    return dict(status='FULL_3133452_INPUT_ALL_HMR_LOCAL_PHASE_AND_WIDTH_PASS',
                original_inputs=n, every_original_HMR=True,
                parent_interval=[start, end], output_interval=[aa, bb],
                old_peak=max(m.bit_count() for m in old[3]),
                new_peak=max(m.bit_count() for m in new[3]),
                old_peak44_cuts=sum(m.bit_count()==44 for m in old[3]),
                new_peak44_cuts=sum(m.bit_count()==44 for m in new[3]),
                fractional_arguments_checked=len(old[2]), selected_intervals=windows,
                global_Q43_claimed=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--native', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--selection', choices=['simple', 'outer', 'all'], default='all')
    ap.add_argument('--parent-cost', required=True, type=Fraction)
    ap.add_argument('--full-local-proof', action='store_true')
    args = ap.parse_args()
    began = time.monotonic()
    assert not args.out.exists()
    args.out.mkdir(parents=True)
    text = args.native.read_text()
    parent = Program(text)
    plans = find_plans(parent, args.selection)
    for p in plans:
        p['universal_proof'] = universal_check(p, parent)
    starts = {p['start']: p for p in plans}
    by_index = {}
    metadata = {'REGISTER', 'APPEND_TO_REGISTER', 'INFO_TAG', 'DEBUG_PRINT'}
    index = 0
    for line, s in enumerate(text.splitlines()):
        fields = shlex.split(s, comments=True)
        if fields and fields[0] not in metadata:
            by_index[line] = index
            index += 1
    assert index == len(parent.operations)
    lines, origins, new_starts, new_ends = ['# '+NOTICE], [], {}, {}
    skip = -1
    for line, s in enumerate(text.splitlines()):
        i = by_index.get(line)
        if i is None:
            lines.append(s)
        elif i in starts:
            p = starts[i]
            new_starts[i] = len(origins)
            lines += p['replacement']
            origins += p['origins']
            new_ends[p['end']] = len(origins)
            skip = p['end']
        elif i >= skip:
            lines.append(s)
            origins.append(i)
    output = '\n'.join(lines)+'\n'
    changed = Program(output)
    assert len(changed.operations) == len(origins)
    assert changed.measurements == parent.measurements-len(plans)
    assert changed.registers == parent.registers
    assert [(o.arguments, o.half_turns, o.condition) for o in changed.operations if o.kind == 'Z_POW'] == [(o.arguments, o.half_turns, o.condition) for o in parent.operations if o.kind == 'Z_POW']
    path = args.out/'candidate_text.kmx'
    path.write_text(output)
    local = full_interval_check(parent, plans, changed, origins, new_starts, new_ends) if args.full_local_proof else None
    report = dict(notice=NOTICE, status='CAUSAL_PHASE_SWAP_EMISSION_WITH_UNIVERSAL_PROOFS',
                  parent_native=str(args.native.resolve()), parent_native_sha256=sha(args.native),
                  output_native=str(path.resolve()), output_native_sha256=sha(path),
                  source_sha256=sha(__file__), selection=args.selection, plans=plans,
                  parent_cost=str(args.parent_cost), exact_added_expected_Toffolis=str(len(plans)),
                  modelled_output_cost=str(args.parent_cost+len(plans)),
                  parent_HMR_count=parent.measurements, output_HMR_count=changed.measurements,
                  original_operations=len(parent.operations), output_operations=len(changed.operations),
                  all_rotation_literals_preserved=True, local_full_proof=local,
                  output_start_cuts=new_starts, output_end_cuts=new_ends,
                  global_Q43_claimed=False, qualified=False, seconds=time.monotonic()-began)
    (args.out/'REPORT.json').write_text(json.dumps(report, indent=2)+'\n')
    mapping = dict(notice=NOTICE, parent_native_sha256=sha(args.native), output_native_sha256=sha(path),
                   output_to_original_operation=origins)
    (args.out/'OUTPUT_OPERATION_ORIGINS.json.gz').write_bytes(gzip.compress((json.dumps(mapping, separators=(',', ':'))+'\n').encode(), mtime=0))
    print(json.dumps({k:report[k] for k in ['status','selection','output_native_sha256','exact_added_expected_Toffolis','modelled_output_cost','output_HMR_count','seconds']}, indent=2), flush=True)
    if local:
        print(json.dumps(local, indent=2), flush=True)


if __name__ == '__main__':
    main()
