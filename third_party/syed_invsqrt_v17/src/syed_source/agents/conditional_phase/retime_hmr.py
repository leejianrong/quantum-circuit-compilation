# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Move unconditional HMRs across target-only writes with exact binary repair.

This changes the measurement schedule.  It is not a repetition of any frozen
fixed-measurement handoff screen.  Each moved measurement receives a fresh
classical owner; its old owner changes at precisely the original instruction.
The universal identity is m*(t + sum G*f) = m*t + sum m*G*f over GF(2).
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shlex
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ENGINE = ROOT / 'incumbent_sources/frozen_source/fusion/runtime/work/c10/narrow/checkpoint002/cleanroom/baseline_stage97/engine'
sys.path.insert(0, str(ENGINE))
from branch_prover import Program

NOTICE = ('Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: '
          'Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, '
          'Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude '
          'Science supporting the research.')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mul(a, b):
    out = set()
    for x in a:
        for y in b:
            z = x | y
            if z in out:
                out.remove(z)
            else:
                out.add(z)
    return out


def probability(poly):
    union = 0
    for m in poly:
        union |= m
    bits = [i for i in range(union.bit_length()) if union >> i & 1]
    assert len(bits) <= 20, len(bits)
    compact = [sum(((m >> j) & 1) << i for i, j in enumerate(bits)) for m in poly]
    ones = sum(sum((x & m) == m for m in compact) & 1 for x in range(1 << len(bits)))
    return Fraction(ones, 1 << len(bits))


def original_guards(program):
    """Exact independent-HMR classical ANFs, including inactive HMR branches."""
    state = {q: set() for q in program.wires if q.startswith('b')}
    state.update({'0': set(), 'False': set(), '1': {0}, 'True': {0}})
    stack, result = [{0}], []
    for op in program.operations:
        k, a = op.kind, op.arguments
        g = stack[-1] if op.condition is None else mul(stack[-1], state[op.condition])
        result.append(set(g))
        if k == 'PUSH_CONDITION':
            stack.append(g)
        elif k == 'POP_CONDITION':
            stack.pop()
        elif k == 'HMR':
            state[a[1]] ^= mul(g, state[a[1]] ^ {1 << op.event})
        elif k == 'BIT_INVERT':
            state[a[0]] ^= g
        elif k in ('BIT_STORE0', 'BIT_STORE1'):
            v = {0} if k == 'BIT_STORE1' else set()
            state[a[0]] ^= mul(g, state[a[0]] ^ v)
    assert stack == [{0}]
    return result


def make_plan(program):
    depths, depth = [], 0
    for op in program.operations:
        depths.append(depth)
        depth += (op.kind == 'PUSH_CONDITION') - (op.kind == 'POP_CONDITION')
        assert depth >= 0
    depths.append(depth)
    assert depth == 0
    uses = defaultdict(list)
    for i, op in enumerate(program.operations):
        for q in op.arguments:
            if q.startswith('q'):
                uses[q].append(i)
    fresh = max(int(q[1:]) for q in program.wires if q.startswith('b') and q[1:].isdigit()) + 1
    plans = []
    for h, op in enumerate(program.operations):
        if op.kind != 'HMR' or op.condition is not None or depths[h]:
            continue
        q, b = op.arguments
        target_writes, barrier = [], -1
        for j in reversed(uses[q]):
            if j >= h:
                continue
            prior = program.operations[j]
            if prior.kind in ('X', 'CX', 'CCX') and prior.arguments[-1] == q:
                target_writes.append(j)
            else:
                barrier = j
                break
        start = next(i for i in range(barrier + 1, h + 1) if depths[i] == 0)
        if start == h:
            continue
        target_writes = sorted(j for j in target_writes if start <= j < h)
        # Merely moving through disjoint gates is useful: it makes the true
        # outcome available for phase synthesis while controls still exist.
        plans.append(dict(old_operation=h, insertion_cut=start, last_quantum_read=barrier,
                          quantum_owner=q, old_classical_owner=b,
                          fresh_classical_owner=f'b{fresh}', original_event=op.event,
                          target_write_operations=target_writes))
        fresh += 1
    return plans


def transform_text(text):
    program = Program(text)
    plans = make_plan(program)
    original_guard = original_guards(program)
    insert = defaultdict(list)
    replace = {}
    saving = Fraction(0)
    changes = []
    new_hmr_to_old = {}
    for p in plans:
        h, start = p['old_operation'], p['insertion_cut']
        q, old, new = p['quantum_owner'], p['old_classical_owner'], p['fresh_classical_owner']
        insert[start].append(f'HMR {q} {new}')
        assert h not in replace
        replace[h] = [f'BIT_STORE0 {old}', f'BIT_INVERT {old} if {new}']
        new_hmr_to_old[new] = p['original_event']
        for j in p['target_write_operations']:
            assert j not in replace
            op = program.operations[j]
            phase = {'X': 'NEG', 'CX': 'Z', 'CCX': 'CZ'}[op.kind]
            owners = list(op.arguments[:-1])
            line = ' '.join([phase] + owners + ['if', new])
            replace[j] = ([f'PUSH_CONDITION if {op.condition}', line, 'POP_CONDITION']
                          if op.condition is not None else [line])
            cost = probability(original_guard[j]) if op.kind == 'CCX' else Fraction(0)
            saving += cost
            changes.append(dict(operation=j, original_gate=op.kind, quantum_owners=list(op.arguments),
                                phase_gate=phase, phase_owners=owners,
                                phase_outcome_event=p['original_event'], replacement=replace[j],
                                exact_original_firing_probability=str(probability(original_guard[j])),
                                exact_expected_Toffoli_saving=str(cost)))
    lines, index = [], 0
    mapping = {}
    metadata = {'REGISTER', 'APPEND_TO_REGISTER', 'INFO_TAG', 'DEBUG_PRINT'}
    for line in text.splitlines():
        toks = shlex.split(line, comments=True)
        if not toks or toks[0] in metadata:
            lines.append(line)
            continue
        assert program.operations[index].kind == toks[0]
        mapping[index] = len(lines)
        lines.extend(insert.get(index, []))
        lines.extend(replace.get(index, [line]))
        index += 1
    assert index == len(program.operations)
    result = '# ' + NOTICE + '\n' + '\n'.join(lines) + '\n'
    changed = Program(result)
    assert changed.measurements == program.measurements
    assert changed.registers == program.registers
    assert changed.quantum_wires == program.quantum_wires
    old_events = defaultdict(list)
    for op in program.operations:
        if op.kind == 'HMR' and op.event not in {p['original_event'] for p in plans}:
            old_events[op.arguments].append(op.event)
    event_mapping = {}
    for op in changed.operations:
        if op.kind == 'HMR':
            if op.arguments[1] in new_hmr_to_old:
                event_mapping[op.event] = new_hmr_to_old[op.arguments[1]]
            else:
                event_mapping[op.event] = old_events[op.arguments].pop(0)
    assert sorted(event_mapping.values()) == list(range(program.measurements))
    audit = dict(notice=NOTICE, status='UNIVERSAL_HMR_TARGET_WRITE_RETIMING_CONSTRUCTION',
                 parent_text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                 output_text_sha256=hashlib.sha256(result.encode()).hexdigest(),
                 moved_measurements=len(plans), removed_target_write_counts=dict(Counter(x['original_gate'] for x in changes)),
                 exact_expected_Toffoli_saving=str(saving), plans=plans, target_write_changes=changes,
                 new_to_original_HMR_event=event_mapping, Q=len(program.quantum_wires),
                 HMR_count=program.measurements, no_fractional_phase_changes=True,
                 phase_identity='m*(t XOR sum G*f) = m*t XOR sum m*G*f; each f has at most two quantum controls',
                 chronology='Fresh outcome owner born at the early HMR; original classical owner assigned only at original HMR location',
                 scope='Only unconditional scope-free HMRs; crossing target-only X/CX/CCX and gates disjoint from the measured quantum owner. Every quantum read is a barrier.',
                 qualified=False)
    return result, audit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--native', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    args = ap.parse_args()
    began = time.monotonic()
    args.out.mkdir(parents=True, exist_ok=True)
    text, audit = transform_text(args.native.read_text())
    dest = args.out / 'retimed.kmx'
    dest.write_text(text)
    audit.update(source_sha256=sha(__file__), parent_path=str(args.native.resolve()),
                 output_path=str(dest.resolve()), seconds=time.monotonic()-began)
    (args.out/'REPORT.json').write_text(json.dumps(audit, indent=2)+'\n')
    print(json.dumps({k:audit[k] for k in ['status','moved_measurements','removed_target_write_counts','exact_expected_Toffoli_saving','Q','HMR_count','seconds']}),flush=True)


if __name__ == '__main__':
    main()
