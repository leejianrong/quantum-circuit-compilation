# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Pack an actual value-restoring native circuit into exactly 43 physical wires.

The occupancy oracle retains every original input and every HMR variable.
No ideal retirement or decoder placeholder is allowed. Only globally zero
free gate identities may be omitted; all paid gates and every HMR survive.
The emitted circuit still requires the unchanged complete phase proof.
"""
from pathlib import Path
from collections import Counter
import argparse
import gzip
import json
import shlex
import time
from audit_width_candidate import occupancy
from emit_q43_all_early_and_quartics import literals, METADATA
from map_incumbent_width import NOTICE, Program, sha


def dump_gz(path, obj):
    path.write_bytes(gzip.compress((json.dumps(obj, sort_keys=True,
        separators=(',', ':'))+'\n').encode(), mtime=0))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--native', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--expected-native-sha256', required=True)
    args=ap.parse_args(); began=time.monotonic()
    native=args.native.resolve(); out=args.out.resolve()
    assert sha(native)==args.expected_native_sha256
    assert not out.exists(); out.mkdir(parents=True)
    text=native.read_text(); program,masks=occupancy(native)
    lines=literals(text)
    assert len(masks)==len(program.operations)+1==len(lines)+1
    assert max(map(int.bit_count,masks))<=43
    assert set(program.registers)=={'x'}
    assert program.registers['x']==tuple(f'q{i}' for i in range(22)) or list(program.registers['x'])==[f'q{i}' for i in range(22)]
    owners=lambda mask:{f'q{i}' for i in range(mask.bit_length()) if mask>>i&1}
    allocation={q:int(q[1:]) for q in owners(masks[0])}
    assert all(0<=p<43 for p in allocation.values())
    assignments=[]; releases=[]; records=[]; removed=[]; peak=0
    demands=Counter()

    def retain(wanted,cut):
        for q in sorted(set(allocation)-wanted,key=lambda q:int(q[1:])):
            releases.append([cut,q,allocation.pop(q)])

    def admit(wanted,cut):
        nonlocal peak
        assert len(wanted)<=43,(cut,'more than43 simultaneous operands',sorted(wanted))
        for q in sorted(wanted-set(allocation),key=lambda q:int(q[1:])):
            free=set(range(43))-set(allocation.values()); assert free,(cut,q)
            preferred=int(q[1:]); physical=preferred if preferred in free else min(free)
            allocation[q]=physical; assignments.append([cut,q,physical])
        assert len(allocation)==len(set(allocation.values()))
        assert wanted<=set(allocation) and all(0<=p<43 for p in allocation.values())
        peak=max(peak,len(allocation)); demands[len(wanted)]+=1

    for cut,(op,line) in enumerate(zip(program.operations,lines,strict=True)):
        pre=owners(masks[cut]); post=owners(masks[cut+1])
        retain(pre,cut); admit(pre,cut)
        operands={q for q in op.arguments if q.startswith('q') and q[1:].isdigit()}
        zero=False
        if op.kind in ('Z','CZ'):
            zero=any(q not in pre for q in operands)
        elif op.kind=='CX':
            zero=op.arguments[0] not in pre
        elif op.kind in ('R','SWAP'):
            zero=all(q not in pre for q in operands)
        if zero:
            assert masks[cut]==masks[cut+1]
            assert op.kind in ('Z','CZ','CX','R','SWAP')
            removed.append(dict(original_operation=cut,kind=op.kind,literal=line))
            continue
        admit(pre|post|operands,cut)
        renamed=' '.join(f'q{allocation[t]}' if t in operands else t
                         for t in shlex.split(line,comments=True))
        records.append(dict(original_operation=cut,literal=renamed))
        retain(post,cut+1)
    assert set(allocation)==set(program.registers['x'])
    end_swaps=[]
    for q in program.registers['x']:
        desired=int(q[1:]); present=allocation[q]
        if desired==present: continue
        other=next((r for r,t in allocation.items() if t==desired),None)
        end_swaps.append(f'SWAP q{present} q{desired}')
        allocation[q]=desired
        if other is not None: allocation[other]=present
    assert all(allocation[q]==int(q[1:]) for q in program.registers['x'])
    metadata=[line for line in text.splitlines()
              if (tokens:=shlex.split(line,comments=True)) and tokens[0] in METADATA]
    result='\n'.join(['# '+NOTICE]+metadata+[r['literal'] for r in records]+end_swaps)+'\n'
    candidate=Program(result)
    assert candidate.quantum_wires=={f'q{i}' for i in range(43)} or set(candidate.quantum_wires)=={f'q{i}' for i in range(43)}
    assert candidate.registers==program.registers and candidate.measurements==program.measurements
    # Every paid opcode and angle is retained in exactly its original order.
    paid={'CCX','CCZ','CSWAP','Z_POW'}
    before=[(o.kind,o.condition,o.half_turns) for o in program.operations if o.kind in paid]
    after=[(o.kind,o.condition,o.half_turns) for o in candidate.operations if o.kind in paid]
    assert before==after
    assert [o.condition for o in candidate.operations if o.kind=='HMR']==[o.condition for o in program.operations if o.kind=='HMR']
    path=out/'candidate_text.kmx'; path.write_text(result)
    occ=out/'SOURCE_ALL_INPUT_ALL_HMR_OCCUPANCY.json.gz'
    dump_gz(occ,dict(notice=NOTICE,native_sha256=sha(native),masks=masks))
    plan=out/'PHYSICAL_ALLOCATION.json.gz'
    dump_gz(plan,dict(notice=NOTICE,source_native_sha256=sha(native),packed_native_sha256=sha(path),
        renamed_operations=records,globally_zero_free_identities=removed,
        owner_assignments=assignments,owner_releases=releases,final_free_swaps=end_swaps))
    report=dict(notice=NOTICE,status='ACTUAL_Q43_NATIVE_PACKED_WHOLE_PHASE_PROOF_PENDING',
        source_native_sha256=sha(native),packed_native_sha256=sha(path),
        full_original_inputs=3133452,every_HMR_branch=True,source_operations=len(lines),
        physical_operations=len(candidate.operations),source_HMR=program.measurements,physical_HMR=candidate.measurements,
        physical_qubits=43,physical_indices='q0..q42',maximum_live_and_operand_owners=peak,
        source_value_peak=max(map(int.bit_count,masks)),paid_gates_preserved_in_order=True,
        fractional_angles_and_conditions_preserved=True,all_HMR_preserved_in_order=True,
        input_register_mapping_restored=True,globally_zero_free_identities_omitted=len(removed),
        omitted_identity_kinds=dict(sorted(Counter(r['kind'] for r in removed).items())),
        final_free_swaps=end_swaps,source_occupancy_sha256=sha(occ),allocation_sha256=sha(plan),
        packer_source_sha256=sha(Path(__file__)),no_placeholders=True,qualified=False,
        seconds=time.monotonic()-began)
    (out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)


if __name__=='__main__': main()
