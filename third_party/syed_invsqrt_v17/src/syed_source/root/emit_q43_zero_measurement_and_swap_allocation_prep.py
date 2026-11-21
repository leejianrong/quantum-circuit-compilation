# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Remove temporary operand-width demand from zero measurements and swaps.

An X-basis measurement of a proven zero wire supplies an independent fair bit
and no phase. Draw that bit on initially zero scratch, then write the original
classical destination at its original cut and under its original guard.
Unconditional swaps of scratch owners are implemented by suffix renaming.
The unchanged full circuit proof remains mandatory after emission.
"""
from pathlib import Path
import argparse
import gzip
import json
import shlex
import sys
import time
from map_incumbent_width import BASE, NOTICE, Program, sha
from emit_q43_all_early_and_quartics import literals, METADATA


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();assert not args.out.exists();began=time.monotonic()
    native=BASE/'root/q43_all_early_and_quartics_native_v1/candidate_text.kmx'
    maskpath=BASE/'root/q43_all_early_and_quartics_width_root_v1/ALL_INPUT_ALL_HMR_OCCUPANCY.json.gz'
    proofpath=BASE/'root/q43_all_early_and_quartics_proof_v1/proof.json'
    assert sha(native)=='cf6dbeb93accba67f13a516f6bb0af5b198853a93c72760c47907f68fccebc08'
    proof=json.loads(proofpath.read_text());assert proof['qualified'] and proof['every_HMR_transcript_proved'] and proof['proved_inputs']==3133452
    with gzip.open(maskpath,'rt') as f:md=json.load(f)
    assert md['native_sha256']==sha(native);masks=md['masks']
    p=Program(native.read_text());lines=literals(native.read_text());assert len(lines)==len(p.operations)
    assert len(masks)==len(lines)+1
    requested={17028,17426,19517,20745};swaps={32583,32586}
    initial_zero=next(q for q in sorted(p.quantum_wires,key=lambda x:int(x[1:])) if not (masks[0]>>int(q[1:])&1))
    assert initial_zero not in p.registers['x']
    fresh=1+max(int(q[1:]) for q in p.wires if q.startswith('b'))
    new_bits={cut:f'b{fresh+i}' for i,cut in enumerate(sorted(requested))}
    prefix=[f'HMR {initial_zero} {new_bits[cut]}' for cut in sorted(requested)]
    wire_map={q:q for q in p.quantum_wires}
    output_ops=list(prefix);parent_to_output={};records=[];swap_records=[];stack=[]
    for i,(op,line) in enumerate(zip(p.operations,lines)):
        parent_to_output[i]=len(output_ops)
        if i in requested:
            assert op.kind=='HMR' and not stack
            q,destination=op.arguments
            assert not(masks[i]>>int(q[1:])&1) and masks[i]==masks[i+1]
            bit=new_bits[i]
            replacement=[f'BIT_STORE0 {destination}',f'BIT_INVERT {destination} if {bit}']
            if op.condition is not None:
                replacement=[f'PUSH_CONDITION if {op.condition}']+replacement+['POP_CONDITION']
            replacement.append(f'BIT_STORE0 {bit}')
            output_ops.extend(replacement)
            records.append(dict(parent_operation=i,proven_zero_owner=q,original_destination=destination,
                                original_condition=op.condition,early_random_bit=bit,early_zero_owner=initial_zero,
                                output_interval=[parent_to_output[i],len(output_ops)]))
        elif i in swaps:
            assert op.kind=='SWAP' and op.condition is None and not stack
            left,right=op.arguments
            assert left not in p.registers['x'] and right not in p.registers['x']
            before={left:wire_map[left],right:wire_map[right]}
            wire_map[left],wire_map[right]=wire_map[right],wire_map[left]
            swap_records.append(dict(parent_operation=i,original_owners=[left,right],before=before,
                                     after={left:wire_map[left],right:wire_map[right]}))
        else:
            output_ops.append(' '.join(wire_map.get(t,t) for t in shlex.split(line,comments=True)))
        if op.kind=='PUSH_CONDITION':stack.append(op.condition)
        elif op.kind=='POP_CONDITION':stack.pop()
    parent_to_output[len(lines)]=len(output_ops)
    assert not stack and all(wire_map[q]==q for q in p.registers['x'])
    assert len(output_ops)-len(lines)==12
    output=['# '+NOTICE];inserted=False
    for line in native.read_text().splitlines():
        tokens=shlex.split(line,comments=True)
        if not tokens or tokens[0] in METADATA:output.append(line)
        elif not inserted:output.extend(output_ops);inserted=True
    text='\n'.join(output)+'\n';new=Program(text)
    assert new.registers==p.registers and new.quantum_wires==p.quantum_wires
    assert new.measurements==p.measurements==1315
    engine=BASE/'incumbent_sources/frozen_source/fusion/runtime/work/c10/narrow/checkpoint002/cleanroom/baseline_stage97'
    sys.path.insert(0,str(engine/'tests'));sys.path.insert(0,str(engine/'engine'))
    from fourier_resource_expectation import exact_expectation
    resources=exact_expectation(text)
    assert resources['mean']==dict(toffoli_like='11693/8',T='1',generic_rotations='34')
    args.out.mkdir(parents=True);dest=args.out/'candidate_text.kmx';dest.write_text(text)
    mapping=dict(notice=NOTICE,parent_native_sha256=sha(native),parent_to_output=parent_to_output,
                 random_measurements=records,scratch_swap_renamings=swap_records,final_quantum_renaming=wire_map)
    (args.out/'OPERATION_MAP.json.gz').write_bytes(gzip.compress((json.dumps(mapping,sort_keys=True,separators=(',',':'))+'\n').encode(),mtime=0))
    report=dict(notice=NOTICE,status='NATIVE_ALLOCATION_PREPARATION_FULL_PROOF_PENDING',source_sha256=sha(Path(__file__)),
                candidate_native_sha256=sha(dest),parent_native_sha256=sha(native),
                measured_zero_HMR_moved=len(records),unconditional_scratch_swaps_renamed=len(swaps),
                exact_expected_Toffolis='11693/8',Q=44,T=1,rotations=34,
                original_input_owner_map_unchanged=True,extra_quantum_owners=0,extra_HMR=0,
                original_classical_write_cuts_and_guards_preserved=True,
                all_new_classical_temporaries_cleared=True,global_Q43_claimed=False,
                full_unchanged_proof_and_two_builds_pending=True,qualified=False,
                bindings={str(x.relative_to(BASE)):sha(x) for x in [Path(__file__),native,maskpath,proofpath]},
                seconds=time.monotonic()-began)
    (args.out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['notice','bindings']}),flush=True)


if __name__=='__main__':main()
