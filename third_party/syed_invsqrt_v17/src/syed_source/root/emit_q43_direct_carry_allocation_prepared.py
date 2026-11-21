# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Apply the bound direct early carry to the allocation-prepared width parent."""
from pathlib import Path
import argparse
import gzip
import json
import shlex
import sys
import time
from map_incumbent_width import BASE, NOTICE, Program, sha

META = {'REGISTER', 'APPEND_TO_REGISTER', 'INFO_TAG', 'DEBUG_PRINT'}


def literals(text):
    return [' '.join(tokens) for line in text.splitlines()
            if (tokens := shlex.split(line, comments=True)) and tokens[0] not in META]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    assert not args.out.exists()
    began = time.monotonic()
    parent = BASE / 'root/q43_zero_measurement_allocation_prep_native_v1/candidate_text.kmx'
    contract_path = BASE / 'agents/paid_helper/FINAL_EARLY_DIRECT_CARRY_V4_CONTRACT.json'
    contract = json.loads(contract_path.read_text())
    assert sha(parent) == 'b9aa10bcc7b0932afb1d154cff1d101b802d04f78348a6c971bcbeab4606d863'
    assert contract['status'] == 'UNIVERSAL_FINAL_EARLY_DIRECT_CARRY_AND_PARENT_BINDINGS_PASS'
    binding = next(b for b in contract['current_parent_bindings'] if b['sha256'] == sha(parent))
    left, right = binding['replace_interval']
    assert (left, right) == (15342, 15414)
    original = parent.read_text()
    old_lines = literals(original)
    assert old_lines[left:right] == contract['old_fragment']
    replacement = contract['replacement_fragment']
    assert len(replacement) == 38 and right-left == 72
    assert all('q21' not in shlex.split(line) for line in replacement)
    output = ['# ' + NOTICE]
    operation = 0
    for line in original.splitlines():
        tokens = shlex.split(line, comments=True)
        if not tokens or tokens[0] in META:
            output.append(line)
            continue
        if operation == left:
            output.extend(replacement)
        if operation < left or operation >= right:
            output.append(line)
        operation += 1
    assert operation == len(old_lines) == 36850
    text = '\n'.join(output) + '\n'
    new_lines = literals(text)
    delta = len(replacement) - (right-left)
    assert delta == -34
    assert new_lines[:left] == old_lines[:left]
    assert new_lines[left+len(replacement):] == old_lines[right:]
    old, new = Program(original), Program(text)
    assert new.registers == old.registers and new.quantum_wires == old.quantum_wires
    assert new.measurements == old.measurements-1 == 1314
    assert len(new.operations) == 36816
    engine = BASE / 'incumbent_sources/frozen_source/fusion/runtime/work/c10/narrow/checkpoint002/cleanroom/baseline_stage97'
    sys.path.insert(0, str(engine/'tests'))
    sys.path.insert(0, str(engine/'engine'))
    from fourier_resource_expectation import exact_expectation
    resources = exact_expectation(text)
    assert resources['mean'] == dict(toffoli_like='11691/8', T='1', generic_rotations='34')
    args.out.mkdir(parents=True)
    dest = args.out/'candidate_text.kmx'
    dest.write_text(text)
    mapping = dict(notice=NOTICE, parent_native_sha256=sha(parent),
                   replaced_parent_interval=[left,right], output_interval=[left,left+len(replacement)],
                   parent_to_output={i:i if i<=left else i+delta for i in range(len(old.operations)+1)
                                     if i<=left or i>=right},
                   interior_parent_cuts_have_no_correspondence=True)
    (args.out/'OPERATION_MAP.json.gz').write_bytes(gzip.compress(
        (json.dumps(mapping,sort_keys=True,separators=(',',':'))+'\n').encode(),mtime=0))
    report = dict(notice=NOTICE,status='ROOT_BOUND_DIRECT_CARRY_COMPOSITION_FULL_PROOF_PENDING',
                  source_sha256=sha(Path(__file__)),candidate_native_sha256=sha(dest),
                  parent_native_sha256=sha(parent),exact_expected_Toffolis='11691/8',
                  measured_native_expectation=resources,Q=44,T=1,rotations=34,
                  unchanged_complement=True,removed_HMR=1,operations=len(new.operations),
                  source_registers_preserved=True,allocation_preparation_preserved=True,
                  old_interval=[left,right],new_interval=[left,left+len(replacement)],
                  modelled_remaining_width_windows=22,modelled_remaining_width_cuts=182,
                  modelled_q43_s6_total='11723/8',
                  qualified=False,full_unchanged_proof_and_byte_rebuild_pending=True,
                  bindings={str(p.relative_to(BASE)):sha(p) for p in [Path(__file__),parent,contract_path]},
                  seconds=time.monotonic()-began)
    (args.out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['status','candidate_native_sha256','exact_expected_Toffolis','operations','seconds']}),flush=True)


if __name__ == '__main__':
    main()
