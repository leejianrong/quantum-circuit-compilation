# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Compose all proved early carry edits with the later native quartic repairs."""
from pathlib import Path
import argparse
import gzip
import json
import shlex
import sys
import time
from map_incumbent_width import BASE, NOTICE, Program, sha

METADATA = {'REGISTER', 'APPEND_TO_REGISTER', 'INFO_TAG', 'DEBUG_PRINT'}


def literals(text):
    return [line for line in text.splitlines()
            if (tokens := shlex.split(line, comments=True)) and tokens[0] not in METADATA]


def signature(op):
    return op.kind, op.arguments, op.condition, op.half_turns


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists()
    began = time.monotonic()
    paths = {
        'base': BASE / 'agents/temporal_merges/q43_long_second_delayed_q21_native_v1/candidate_text.kmx',
        'regular': BASE / 'agents/paid_helper/early_conditional_carry_borrows_native_v1/candidate_text.kmx',
        'remaining': BASE / 'agents/paid_helper/remaining_early_carry_windows_native_v3/candidate_text.kmx',
        'late': BASE / 'agents/temporal_merges/q43_conjugated_quartic_native_v1/candidate_text.kmx',
    }
    expected = {
        'base': '0e4a525f98bc492ccfb5e05d04983eabc3bbd036e26e77a9bb244aabb77421da',
        'regular': '7f13faa4ebdfcd0b61e6b92c47151ab873d3507717d10f4a52a169de7bcf085c',
        'remaining': '611fdf4f39bee393bc0c883ff509248cbccf8ffb1a9301d268ff8f22a3933dc1',
        'late': '19675c940d27600d4b01e4e9ba19e0e907cddef93026a28df1ee2116ad32fd06',
    }
    for name, path in paths.items():
        assert sha(path) == expected[name]
    programs = {name: Program(path.read_text()) for name, path in paths.items()}
    sigs = {name: [signature(op) for op in prog.operations] for name, prog in programs.items()}
    lines = {name: literals(path.read_text()) for name, path in paths.items()}
    for name in paths:
        assert len(lines[name]) == len(sigs[name])
        assert programs[name].registers == programs['base'].registers
        assert programs[name].quantum_wires == programs['base'].quantum_wires
    cut = 16000
    assert sigs['base'][:cut] == sigs['late'][:cut]
    intervals = {'regular': [(11676, 14361)],
                 'remaining': [(11013, 11223), (11318, 11528),
                               (14685, 14888), (15186, 15235)]}
    proofs = {}
    mappings = {}
    renamings = {}
    patches = []
    fresh = 1 + max(int(q[1:]) for prog in programs.values() for q in prog.wires if q.startswith('b'))
    for name in ['regular', 'remaining']:
        parent = paths[name].parent
        proof = json.loads((parent / 'LOCAL_PROOF.json').read_text())
        assert proof['original_inputs'] == 3133452 and proof['all_original_HMR']
        zero_key = 'extra_classical_owners_zero_at_exit' if name == 'regular' else 'fresh_classical_owners_zero_at_exit'
        assert proof[zero_key]
        if name == 'regular':
            assert proof['maximum_width_in_component'] == 43
        else:
            assert all(c['local_maximum_width'] <= 43 for c in proof['components'])
            assert [tuple(c['parent_interval']) for c in proof['components']] == intervals[name]
        proofs[name] = proof
        with gzip.open(parent / 'OPERATION_MAP.json.gz', 'rt') as f:
            mapping = json.load(f)['parent_to_output']
        mappings[name] = mapping
        additions = sorted(programs[name].wires - programs['base'].wires, key=lambda q: int(q[1:]))
        assert all(q.startswith('b') for q in additions)
        renamings[name] = {q: f'b{fresh + i}' for i, q in enumerate(additions)}
        fresh += len(additions)
        start = 0
        for left, right in intervals[name]:
            assert sigs[name][mapping[str(start)]:mapping[str(left)]] == sigs['base'][start:left]
            a, b = mapping[str(left)], mapping[str(right)]
            patches.append((left, right, name, a, b))
            start = right
        assert sigs[name][mapping[str(start)]:] == sigs['base'][start:]
    patches.sort()
    prefix = []
    patch_receipts = []
    cursor = 0
    for left, right, name, a, b in patches:
        assert cursor <= left < right <= cut
        prefix.extend(lines['base'][cursor:left])
        begin_output = len(prefix)
        rename = renamings[name]
        prefix.extend(' '.join(rename.get(t, t) for t in shlex.split(line, comments=True))
                      for line in lines[name][a:b])
        patch_receipts.append(dict(component=name, parent_interval=[left, right],
                                   component_interval=[a, b], output_interval=[begin_output, len(prefix)]))
        cursor = right
    prefix.extend(lines['base'][cursor:cut])
    delta = len(prefix) - cut
    assert delta == 175
    output = ['# ' + NOTICE]
    operation = 0
    for line in paths['late'].read_text().splitlines():
        tokens = shlex.split(line, comments=True)
        if not tokens or tokens[0] in METADATA:
            output.append(line)
            continue
        if operation == 0:
            output.extend(prefix)
        if operation >= cut:
            output.append(line)
        operation += 1
    assert operation == len(programs['late'].operations)
    text = '\n'.join(output) + '\n'
    program = Program(text)
    assert len(program.operations) == len(programs['late'].operations) + delta
    assert program.registers == programs['late'].registers
    assert program.quantum_wires == programs['late'].quantum_wires
    assert program.measurements == programs['late'].measurements + 10 == 1315
    assert [signature(op) for op in program.operations[len(prefix):]] == sigs['late'][cut:]

    # These original classical owners may differ at the remaining-component exit.
    # Verify their first later occurrence in the ACTUAL composed suffix is a
    # syntactically unconditional write, including the enclosing condition stack.
    endpoint = next(r['output_interval'][1] for r in patch_receipts
                    if r['parent_interval'] == [15186, 15235])
    exceptions = set(proofs['remaining']['dead_parity_guard_first_unconditional_overwrites'])
    exceptions.update(proofs['remaining']['unused_removed_temporaries'])
    liveness = {}
    stack = []
    for index, op in enumerate(program.operations):
        for wire in sorted(exceptions - liveness.keys()):
            if index < endpoint or (wire not in op.arguments and wire != op.condition):
                continue
            is_write = ((op.kind == 'HMR' and op.arguments[-1] == wire)
                        or (op.kind in ('BIT_STORE0', 'BIT_STORE1') and op.arguments == (wire,)))
            assert is_write and op.condition is None and not stack, (wire, index, op)
            liveness[wire] = dict(first_later_occurrence=index, kind=op.kind,
                                  arguments=list(op.arguments), unconditional_write=True)
        if op.kind == 'PUSH_CONDITION':
            stack.append(op.condition)
        elif op.kind == 'POP_CONDITION':
            assert stack
            stack.pop()
    assert not stack
    for wire in sorted(exceptions - liveness.keys()):
        liveness[wire] = dict(no_later_occurrence=True)

    engine = BASE / 'incumbent_sources/frozen_source/fusion/runtime/work/c10/narrow/checkpoint002/cleanroom/baseline_stage97'
    sys.path.insert(0, str(engine / 'tests'))
    sys.path.insert(0, str(engine / 'engine'))
    from fourier_resource_expectation import exact_expectation
    resources = exact_expectation(text)
    assert resources['mean'] == dict(toffoli_like='11693/8', T='1', generic_rotations='34')
    args.out.mkdir(parents=True)
    dest = args.out / 'candidate_text.kmx'
    dest.write_text(text)
    mapping = dict(notice=NOTICE, inputs=expected, patches=patch_receipts,
                   component_classical_renamings=renamings,
                   common_base_cut=cut, output_suffix_start=len(prefix),
                   late_cut_to_output_cut={i: i + delta for i in range(cut, len(programs['late'].operations) + 1)})
    (args.out / 'OPERATION_MAP.json.gz').write_bytes(gzip.compress(
        (json.dumps(mapping, sort_keys=True, separators=(',', ':')) + '\n').encode(), mtime=0))
    bound = [Path(__file__)] + list(paths.values())
    for name in ['regular', 'remaining']:
        bound.extend(paths[name].parent / f for f in ['LOCAL_PROOF.json', 'OPERATION_MAP.json.gz'])
    report = dict(notice=NOTICE, status='EXACT_DISJOINT_NATIVE_COMPOSITION_FULL_PROOF_PENDING',
                  source_sha256=sha(Path(__file__)), candidate_native_sha256=sha(dest),
                  input_native_hashes=expected, composition_cut=cut,
                  unchanged_complements_and_late_prefix_checked=True,
                  patches=patch_receipts, classical_renamings=renamings,
                  changed_dead_classical_liveness_in_actual_composition=liveness,
                  extra_HMR=10, exact_expected_Toffolis='11693/8',
                  exact_increment_over_late='2', Q=44, T=1, rotations=34,
                  modelled_remaining_windows=22, modelled_remaining_cuts=182,
                  modelled_remaining_group='q35', qualified=False,
                  full_unchanged_proof_and_byte_rebuild_pending=True,
                  native_resources=resources,
                  bindings={str(p.relative_to(BASE)): sha(p) for p in bound},
                  seconds=time.monotonic()-began)
    (args.out / 'REPORT.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['status', 'candidate_native_sha256',
          'exact_expected_Toffolis', 'modelled_remaining_windows', 'modelled_remaining_cuts', 'seconds']}), flush=True)


if __name__ == '__main__':
    main()
