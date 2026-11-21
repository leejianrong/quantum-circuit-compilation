# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Share the final carry's q26 owner between complementary classical branches.

On b360=0 the direct carry needs no CCZ. On b360=1 the old early-q26
retirement permits its Z temporary to use q26 instead of q21, followed by
the already-proved joint phase repair. This is a new causal branch routing,
not a repetition of the fixed q26-borrow search. No fractional phase is used.
"""
from collections import Counter
from dataclasses import replace
from pathlib import Path
import argparse
import gzip
import json
import shlex
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0,str(HERE))
import emit_later_bank_guard_sharing as r
from emit_remaining_early_carry_windows_v4 import continuation_live_classical


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--full-local-proof',action='store_true')
    args = parser.parse_args()
    args.out.mkdir(exist_ok=False)
    started = time.monotonic()
    parent = ROOT/'root/q43_direct_carry_allocation_prepared_native_v1/candidate_text.kmx'
    assert r.sha(parent) == 'ce44a05e69ff24e139c25e4770742203dfed962c3d99028aa83af03ce6f83446'
    contract_path = HERE/'FINAL_EARLY_DIRECT_CARRY_V4_CONTRACT.json'
    contract = json.loads(contract_path.read_text())
    text = parent.read_text()
    program = r.Program(text)
    old_lines = [r.literal(op) for op in program.operations]
    lo,hi = 15342,15380
    assert old_lines[lo:hi] == contract['replacement_fragment']
    fresh = [f'b{k}' for k in range(9100,9105)]
    assert not set(fresh)&program.wires
    rename = {'q21':'q26','b9033':'b9101','b9034':'b9102','b9035':'b9103','b9036':'b9104'}
    yes = [' '.join(rename.get(token,token) for token in line.split()) for line in contract['old_fragment']]
    no = [line for line in contract['replacement_fragment'] if line not in (
        'CCZ q29 q30 q0 if b360','CZ q8 q0 if b360')]
    assert len(yes)==72 and len(no)==36
    assert yes[0] == 'HMR q26 b9101'
    assert not any('q21' in line.split() for line in yes+no)
    body = ['BIT_STORE1 b9100','BIT_INVERT b9100 if b360','PUSH_CONDITION if b360',
            *yes,'POP_CONDITION','PUSH_CONDITION if b9100',*no,'POP_CONDITION','BIT_STORE0 b9100']
    replacement = r.Program('\n'.join(body)+'\n')
    assert len(replacement.operations)==115
    assert sum(op.kind=='HMR' for op in replacement.operations)==7
    output = ['# '+r.NOTICE]
    origins = []
    index = 0
    metadata = {'REGISTER','APPEND_TO_REGISTER','INFO_TAG','DEBUG_PRINT'}
    for line in text.splitlines():
        tokens = shlex.split(line,comments=True)
        if not tokens or tokens[0] in metadata:
            output.append(line)
            continue
        if index==lo:
            output.extend(body)
            origins.extend([None]*len(body))
        elif not lo<=index<hi:
            output.append(line)
            origins.append(index)
        index += 1
    assert index==len(program.operations)
    changed = '\n'.join(output)+'\n'
    candidate = r.Program(changed)
    delta = len(body)-(hi-lo)
    assert delta==77 and len(candidate.operations)==len(origins)
    assert candidate.measurements==program.measurements+4
    assert candidate.registers==program.registers
    assert [(op.arguments,op.condition,op.half_turns) for op in candidate.operations if op.kind=='Z_POW'] == [
        (op.arguments,op.condition,op.half_turns) for op in program.operations if op.kind=='Z_POW']
    destination = args.out/'candidate_text.kmx'
    destination.write_text(changed)
    proof = None
    if args.full_local_proof:
        # Include the following complete old R/q7 cleanup so every moved
        # outcome's continuation is explicitly checked before exit.
        end = hi+(15326-15235)
        assert r.literal(program.operations[end-1])=='POP_CONDITION'
        entry = r.replay(program.operations[:lo],r.initial_state(program))['state']
        assert not entry['q21']
        before = r.replay(program.operations[lo:end],entry,phase=True)
        prepared = {q:dict(value) for q,value in entry.items()}
        for bit in fresh:
            prepared[bit] = {}
        segment = []
        extra = 0
        for i,op in enumerate(candidate.operations[lo:end+delta],lo):
            if op.kind=='HMR':
                origin = origins[i]
                event = program.operations[origin].event if origin is not None else program.measurements+extra
                if origin is None:
                    extra += 1
                op = replace(op,event=event)
            segment.append(op)
        assert extra==7
        after = r.replay(segment,prepared,phase=True,masks=True)
        assert before['phase']==after['phase'],'All-HMR phase mismatch'
        assert before['rotations']==after['rotations']
        for q in [f'q{i}' for i in range(44)]:
            assert before['state'][q]==after['state'][q],('Quantum mismatch',q)
        live,kills = continuation_live_classical(program.operations,end)
        for bit in live:
            assert before['state'][bit]==after['state'][bit],('Continuation classical mismatch',bit)
        for bit in fresh:
            assert not after['state'][bit],('Fresh bit not cleared',bit)
        masks = after['masks'][:len(body)+1]
        histogram = Counter(mask.bit_count() for mask in masks)
        operand_peak = 0
        for i,op in enumerate(segment[:len(body)]):
            mask = masks[i]
            for q in op.arguments:
                if q.startswith('q'):
                    mask |= 1<<int(q[1:])
            operand_peak = max(operand_peak,mask.bit_count())
        assert max(histogram)<=43 and operand_peak<=43
        proof = dict(notice=r.NOTICE,status='ALL3133452_INPUT_ALL_HMR_GUARDED_BORROW_PHASE_VALUE_AND_OPERAND_WIDTH_PASS',
            inputs=r.N,parent_interval=[lo,end],candidate_interval=[lo,end+delta],all_formal_HMR=True,
            branch_HMR_events_independent=True,new_local_formal_events=7,
            unchanged_following_cleanup_events_coupled_by_original_operation=True,
            quantum_owners_compared=44,continuation_classical_owners_compared=len(live),
            all_fresh_bits_cleared=True,changed_fragment_width_histogram=dict(sorted(histogram.items())),
            maximum_live_width=max(histogram),maximum_live_union_gate_operands=operand_peak,
            q21_always_zero_and_never_mentioned=True,whole_circuit_qualification_pending=True)
        (args.out/'LOCAL_PROOF.json').write_text(json.dumps(proof,indent=2,sort_keys=True)+'\n')
    engine = ROOT/'incumbent_sources/frozen_source/fusion/runtime/work/c10/narrow/checkpoint002/cleanroom/baseline_stage97'
    sys.path.insert(0,str(engine/'engine'))
    sys.path.insert(0,str(engine/'tests'))
    from fourier_resource_expectation import exact_expectation
    resources = exact_expectation(changed)
    assert resources['mean']==dict(toffoli_like='5845/4',T='1',generic_rotations='34')
    report = dict(notice=r.NOTICE,status='CAUSAL_GUARDED_FINAL_CARRY_BORROW_EMITTED_ROOT_PROOF_PENDING',
        source_sha256=r.sha(Path(__file__)),parent_native_sha256=r.sha(parent),candidate_native_sha256=r.sha(destination),
        parent_interval=[lo,hi],candidate_interval=[lo,lo+len(body)],replacement=body,
        guard='n=b360, unchanged fair original HMR copy, independent of all later branch HMR outcomes.',
        branch0='Direct in-place carry; no added CCZ since n=0.',
        branch1='Early q26 retirement; route Z from q21 into the now-clean q26; erase Z before reusing q26 for the known joint phase helper.',
        branch1_original_scope_inherited='Uses V3 identity, with a fresh classical restriction and explicit physical q21->q26 routing; no cleanup scan repeated.',
        cost_from_original_final_packet='(1/2)*(3/4)+(1/2)*0=3/8',
        exact_expected_Toffoli_delta='-1/8',exact_expected_Toffolis='5845/4',T=1,generic_rotations=34,
        measured_native_expectation=resources,new_classical_bits=fresh,net_extra_HMR=4,
        no_new_fractional_phases=True,all_existing_Z_POW_instructions_unchanged=True,
        full_local_proof_passed=proof is not None,qualified=False,
        unchanged_root_whole_proof_and_two_rebuilds_required=True,seconds=time.monotonic()-started,
        bindings={str(p.relative_to(ROOT)):r.sha(p) for p in (parent,contract_path,Path(__file__))})
    (args.out/'REPORT.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    (args.out/'OPERATION_MAP.json.gz').write_bytes(gzip.compress((json.dumps(dict(notice=r.NOTICE,
        parent_to_output={i:i if i<=lo else i+delta for i in range(len(program.operations)+1) if i<=lo or i>=hi},
        output_origins=origins),separators=(',',':'))+'\n').encode(),mtime=0))
    print(json.dumps({k:report[k] for k in ('status','candidate_native_sha256','exact_expected_Toffolis','full_local_proof_passed','seconds')}),flush=True)


if __name__=='__main__':
    main()
