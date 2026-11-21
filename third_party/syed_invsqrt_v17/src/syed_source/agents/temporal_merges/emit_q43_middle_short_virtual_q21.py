# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Keep the short middle q21 packet implicit, including every native phase.

At the selected birth, t=a*b+c. Its single value transfer is accumulated
directly into q0. The two identical CZ bundles combine under b170 XOR b360,
and their only paid phase is one CCZ on a,b,q29+q0. The original HMR remains
on the clean q21, with exact free quadratic feedback restoring its phase.
"""
import argparse
import json
import sys
import time
from collections import Counter
from fractions import Fraction
from pathlib import Path
import numpy as np
from temporal_core import NOTICE, Program, captures, sha
from emit_q43_deferred_idle_plans import replay
from lift_q43_joint_overflow_C_fibers import atomic

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PARENT_SHA='70eaa20cbe8a658ecaa634eb42d6c9fc521310ef385300be124cf34e397fea7a'


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();assert not args.out.exists();started=time.monotonic()
    native=HERE/'q43_late_short_affine_native_v1/candidate_text.kmx'
    assert sha(native)==PARENT_SHA
    text=native.read_text();p=Program(text)
    a,b,local_start=17047,17068,17030
    assert p.operations[a].kind=='CCX' and p.operations[a].arguments==('q43','q30','q21')
    assert p.operations[b-1].kind=='HMR' and p.operations[b-1].arguments==('q21','b203')
    assert p.operations[local_start].kind=='PUSH_CONDITION' and p.operations[local_start].condition=='b359'
    bit='b'+str(1+max(int(q[1:]) for q in p.wires if q.startswith('b')))
    # Enter with the parent's b359 condition already pushed.
    gates=[
        'PUSH_CONDITION if b169','CZ q43 q30','Z q8','POP_CONDITION',
        'CX q8 q43','CX q43 q30',
        f'BIT_STORE0 {bit}',f'BIT_INVERT {bit} if b170',f'BIT_INVERT {bit} if b360',
        f'PUSH_CONDITION if {bit}',
        'CZ q29 q0','CZ q8 q29','CZ q8 q0',
        'CX q43 q30','CX q8 q43','CX q29 q0','CCZ q43 q30 q0',
        'CX q29 q0','CX q8 q43','CX q43 q30','POP_CONDITION',
        'CX q29 q0',
        'CX q43 q30','CX q8 q43','CCX q43 q30 q0','CX q8 q0',
        'CX q8 q43','CX q43 q30',
        'POP_CONDITION',
        'HMR q21 b203',
        'PUSH_CONDITION if b359','PUSH_CONDITION if b203',
        'CX q43 q30','CX q8 q43','CZ q43 q30','Z q8',
        'CX q8 q43','CX q43 q30','POP_CONDITION','POP_CONDITION']
    assert sum(l.startswith('CCX ') for l in gates)==1 and sum(l.startswith('CCZ ') for l in gates)==1
    replacement_origin=[b-1 if s=='HMR q21 b203' else None for s in gates]
    byline={o.line:i for i,o in enumerate(p.operations)}
    lines=['# '+NOTICE];origins=[];mapping={}
    for line_number,literal in enumerate(text.splitlines(),1):
        i=byline.get(line_number)
        if i is None:lines.append(literal);continue
        mapping[i]=len(origins)
        if i==a:lines.extend(gates);origins.extend(replacement_origin)
        if a<=i<b:continue
        lines.append(literal);origins.append(i)
    mapping[len(p.operations)]=len(origins)
    changed='\n'.join(lines)+'\n';candidate=Program(changed)
    assert candidate.measurements==p.measurements and candidate.wires-p.wires=={bit}
    ca,cb=mapping[local_start],mapping[b]
    xs=np.arange(1,3133453,dtype=np.uint64);full=(1<<len(xs))-1
    frames=captures(p,{local_start,a,b},xs,formal=True,include_classical=True)
    assert not frames[a]['q21']
    frames[local_start][bit]={}
    old=replay(frames[local_start],p.operations[local_start:b],list(range(local_start,b)),p,{},full)
    new=replay(frames[local_start],candidate.operations[ca:cb],origins[ca:cb],p,{},full)
    assert all(old[0][q]==new[0][q] for q in p.wires),'FULL_DOMAIN_VALUE_OR_CLASSICAL_FAILURE'
    assert old[1]==new[1],'FULL_DOMAIN_PHASE_FAILURE'
    assert old[2]==new[2]
    assert max(m.bit_count() for m in new[3])<=43
    engine=ROOT/'incumbent_sources/frozen_source/fusion/runtime/work/c10/narrow/checkpoint002/cleanroom/baseline_stage97'
    sys.path.insert(0,str(engine/'tests'));sys.path.insert(0,str(engine/'engine'))
    from fourier_resource_expectation import exact_expectation
    resources=exact_expectation(changed);cost=Fraction(resources['mean']['toffoli_like']);delta=cost-Fraction(2913,2)
    assert 0<=delta<=1 and resources['mean']['T']=='1' and resources['mean']['generic_rotations']=='34'
    args.out.mkdir();dest=args.out/'candidate_text.kmx';dest.write_text(changed)
    atomic(args.out/'OPERATION_MAP.json.gz',dict(notice=NOTICE,parent_sha256=PARENT_SHA,
           candidate_sha256=sha(dest),old_cut_to_new_cut=mapping,new_operation_origin=origins))
    atomic(args.out/'LOCAL_OCCUPANCY.json.gz',dict(notice=NOTICE,parent_start_cut=local_start,
           parent_masks=old[3],candidate_start_cut=ca,candidate_masks=new[3]))
    report=dict(notice=NOTICE,status='MIDDLE_SHORT_VIRTUAL_Q21_NATIVE_LOCAL_FULL_DOMAIN_ALL_HMR_PASS',
                numerical_verification='AGENT_VERIFIED_ROOT_REPLAY_PENDING',qualified=False,
                source_sha256=sha(__file__),parent_native_sha256=PARENT_SHA,candidate_native_sha256=sha(dest),
                parent_replaced_interval=[a,b],parent_local_proof_interval=[local_start,b],
                candidate_local_proof_interval=[ca,cb],replacement_gates=gates,
                omitted_physical_value='q21=a*b+c inside b359',original_HMR_preserved=True,
                original_HMR_owner_and_bit=['q21','b203'],added_classical_guard_bit=bit,
                added_paid_phase_guard='b359 AND (b170 XOR b360)',
                exact_added_paid_phase_probability=str(delta),
                exact_added_expected_Toffolis=str(delta),exact_candidate_expected_Toffolis=str(cost),
                full_legal_original_inputs=len(xs),all_HMR_formal=True,
                original_quantum_and_classical_values_identical_at_endpoint=True,
                complete_local_phase_identical=True,rotation_reads_unchanged=True,
                old_local_peak=max(m.bit_count() for m in old[3]),candidate_local_peak=max(m.bit_count() for m in new[3]),
                additional_peak44_windows_removed=1,additional_peak44_cuts_removed=sum(m.bit_count()==44 for m in old[3]),
                includes_free_q9_six_window_component=True,
                remaining_peak44_windows_model=46,remaining_peak44_cuts_model=684,
                local_occupancy_histogram=dict(sorted(Counter(m.bit_count() for m in new[3]).items())),
                native_resources=resources,whole_official_proof_and_rebuild_pending=True,
                global_Q43_not_yet_claimed=True,seconds=time.monotonic()-started)
    atomic(args.out/'REPORT.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('native_resources','replacement_gates')}),flush=True)


if __name__=='__main__':main()
