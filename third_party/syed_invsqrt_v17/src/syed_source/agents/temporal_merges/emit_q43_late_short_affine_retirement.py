# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Retire idle q9 across six late short peaks with a free affine restoration.

The complete 3,133,452-input/all-HMR identity and local phase equality are
checked before emission. Frozen parent files are never changed.
"""
import argparse
import gzip
import json
import sys
import time
from collections import Counter
from fractions import Fraction
from pathlib import Path
import numpy as np
from temporal_core import NOTICE, Program, captures, sha, xor
from emit_q43_deferred_idle_plans import replay
from lift_q43_joint_overflow_C_fibers import atomic

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PARENT_SHA='3f7374b21c92f3d6f262f153b54ac646d0633ed0bdcb38ef89a15c0ada0b3227'


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();assert not args.out.exists();started=time.monotonic()
    native=ROOT/'root/q43_bead_later_q31_v1/candidate_text.kmx'
    assert sha(native)==PARENT_SHA
    cert=HERE/'q43_remaining_broad_fallbacks_v2/CASE_046.json.gz'
    with gzip.open(cert,'rt') as f:plan=json.load(f)
    assert plan['owner']=='q9' and plan['result']['affine_offset']==['q10','q35']
    a,b=23590,23624
    assert [plan['start_cut'],plan['end_cut']]==[a,b]
    text=native.read_text();parent=Program(text)
    assert all('q9' not in o.arguments for o in parent.operations[a:b])
    depth=0;depths=[]
    for o in parent.operations:
        depths.append(depth);depth+=(o.kind=='PUSH_CONDITION')-(o.kind=='POP_CONDITION')
    assert depth==0 and depths[a]==depths[b]==0
    bit='b'+str(1+max(int(q[1:]) for q in parent.wires if q.startswith('b')))
    fresh_events={bit:parent.measurements}
    entry=[f'HMR q9 {bit}'];exit=['CX q10 q9','CX q35 q9',f'Z q9 if {bit}']
    inserts={a:entry,b:exit};origins=[];mapping={};lines=['# '+NOTICE]
    byline={o.line:i for i,o in enumerate(parent.operations)}
    for line_number,literal in enumerate(text.splitlines(),1):
        i=byline.get(line_number)
        if i is not None:
            mapping[i]=len(origins)
            added=inserts.get(i,[]);lines.extend(added);origins.extend([None]*len(added));origins.append(i)
        lines.append(literal)
    mapping[len(parent.operations)]=len(origins)
    changed='\n'.join(lines)+'\n';candidate=Program(changed)
    assert len(candidate.operations)==len(parent.operations)+4
    assert candidate.measurements==parent.measurements+1 and candidate.wires-parent.wires=={bit}
    xs=np.arange(1,3133453,dtype=np.uint64);full=(1<<len(xs))-1
    frames=captures(parent,{a,b},xs,formal=True,include_classical=True)
    assert frames[a]['q9']==frames[b]['q9']
    assert frames[b]['q9']==xor(frames[b]['q10'],frames[b]['q35']),'FULL_DOMAIN_AFFINE_IDENTITY_FAILED'
    ca,cb=mapping[a],mapping[b]+len(exit)
    old=replay(frames[a],parent.operations[a:b],list(range(a,b)),parent,fresh_events,full)
    new=replay(frames[a],candidate.operations[ca:cb],origins[ca:cb],parent,fresh_events,full)
    assert all(old[0][q]==new[0][q] for q in parent.wires)
    assert old[1]==new[1] and old[2]==new[2]
    assert max(m.bit_count() for m in new[3])<=43
    engine=ROOT/'incumbent_sources/frozen_source/fusion/runtime/work/c10/narrow/checkpoint002/cleanroom/baseline_stage97'
    sys.path.insert(0,str(engine/'tests'));sys.path.insert(0,str(engine/'engine'))
    from fourier_resource_expectation import exact_expectation
    resources=exact_expectation(changed)
    assert Fraction(resources['mean']['toffoli_like'])==Fraction(2913,2)
    assert resources['mean']['T']=='1' and resources['mean']['generic_rotations']=='34'
    args.out.mkdir();dest=args.out/'candidate_text.kmx';dest.write_text(changed)
    atomic(args.out/'OPERATION_MAP.json.gz',dict(notice=NOTICE,parent_sha256=PARENT_SHA,
           candidate_sha256=sha(dest),old_cut_to_new_cut=mapping,new_operation_origin=origins))
    atomic(args.out/'LOCAL_OCCUPANCY.json.gz',dict(notice=NOTICE,parent_start_cut=a,
           parent_masks=old[3],candidate_start_cut=ca,candidate_masks=new[3]))
    report=dict(notice=NOTICE,status='LATE_SHORT_AFFINE_RETIREMENT_NATIVE_LOCAL_FULL_DOMAIN_ALL_HMR_PASS',
                numerical_verification='AGENT_VERIFIED_ROOT_REPLAY_PENDING',qualified=False,
                source_sha256=sha(__file__),parent_native_sha256=PARENT_SHA,candidate_native_sha256=sha(dest),
                witness_certificate_sha256=sha(cert),parent_interval=[a,b],candidate_interval=[ca,cb],
                owner='q9',restoration_identity='q9 = q10 XOR q35 at parent cut23624',
                retirement_gates=entry,restoration_gates=exit,fresh_outcome=bit,
                full_legal_original_inputs=len(xs),all_old_and_new_HMR_formal=True,
                original_quantum_and_classical_values_identical_at_endpoint=True,
                complete_local_phase_identical=True,rotation_reads_unchanged=True,
                original_local_rotation_events=len(old[2]),exact_added_expected_Toffolis='0',
                exact_candidate_expected_Toffolis='2913/2',T=1,rotations=34,
                candidate_local_peak=max(m.bit_count() for m in new[3]),
                old_peak44_cuts_removed=sum(m.bit_count()==44 for m in old[3]),
                old_peak44_windows_covered=6,remaining_peak44_windows_model=47,
                remaining_peak44_cuts_model=704,
                local_occupancy_histogram=dict(sorted(Counter(m.bit_count() for m in new[3]).items())),
                native_resources=resources,whole_official_proof_and_rebuild_pending=True,
                global_Q43_not_yet_claimed=True,seconds=time.monotonic()-started)
    atomic(args.out/'REPORT.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='native_resources'}),flush=True)


if __name__=='__main__':main()
