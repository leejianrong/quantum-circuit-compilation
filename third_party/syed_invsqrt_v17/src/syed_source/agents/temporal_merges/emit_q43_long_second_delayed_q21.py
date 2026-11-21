# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Delay the second long q21 birth until after the actual q36 HMR.

All intervening q21 phase reads are aggregated into two cubic parity phases
plus free quadratic terms. The original product is reconstructed only once,
after the actual neighboring owner has retired, preserving every outcome.
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
from temporal_core import NOTICE, Program, captures, sha
from emit_q43_deferred_idle_plans import replay
from emit_q43_long_virtual_q21 import prepare_parities, free_phase
from lift_q43_joint_overflow_C_fibers import atomic

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
REFERENCE_SHA='70eaa20cbe8a658ecaa634eb42d6c9fc521310ef385300be124cf34e397fea7a'
PARENT_SHA='1996659e8f14e0e7e4ea636c3eb75929019559ef8b2d1b3ab735e68fe8dfaee9'


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();assert not args.out.exists();started=time.monotonic()
    native=HERE/'q43_long_virtual_q21_native_v1/candidate_text.kmx'
    reference=HERE/'q43_late_short_affine_native_v1/candidate_text.kmx'
    assert sha(native)==PARENT_SHA and sha(reference)==REFERENCE_SHA
    with gzip.open(HERE/'q43_middle_short_virtual_q21_native_v1/OPERATION_MAP.json.gz','rt') as f:m1=json.load(f)
    with gzip.open(HERE/'q43_long_virtual_q21_native_v1/OPERATION_MAP.json.gz','rt') as f:m2=json.load(f)
    assert m1['parent_sha256']==REFERENCE_SHA and m1['candidate_sha256']==m2['parent_sha256'] and m2['candidate_sha256']==PARENT_SHA
    port=lambda i:m2['old_cut_to_new_cut'][str(m1['old_cut_to_new_cut'][str(i)])]
    ra,rb,rstart=19168,19212,19140
    a,b,start=port(ra),port(rb),port(rstart)
    text=native.read_text();p=Program(text);ref=Program(reference.read_text())
    sig=lambda o:(o.kind,o.arguments,o.condition,o.half_turns)
    assert [sig(o) for o in p.operations[start:b]]==[sig(o) for o in ref.operations[rstart:rb]]
    bundles={};stack=[]
    for o in ref.operations[19175:19211]:
        if o.kind=='PUSH_CONDITION':stack.append(o.condition)
        elif o.kind=='POP_CONDITION':stack.pop()
        else:
            assert o.kind=='CZ' and 'q21' in o.arguments and len(stack)==1
            other=next(q for q in o.arguments if q!='q21')
            bundles.setdefault(stack[0],set()).symmetric_difference_update({other})
    assert not stack and set(bundles)=={'b366','b367'}
    linear=['q17','q0','q18','q43']
    gates=['CX q0 q17','CX q0 q19','POP_CONDITION','PUSH_CONDITION if b361']
    for guard,owners in bundles.items():
        terms=set()
        for q in linear:
            for r in owners:
                t=tuple(sorted({q,r},key=lambda s:int(s[1:])))
                if t in terms:terms.remove(t)
                else:terms.add(t)
        prep,pivots=prepare_parities([['q17'],['q19'],sorted(owners,key=lambda s:int(s[1:]))])
        gates += [f'PUSH_CONDITION if {guard}']+prep+['CCZ '+' '.join(pivots)]+prep[::-1]
        gates += free_phase([list(t) for t in sorted(terms)])+['POP_CONDITION']
    gates += ['POP_CONDITION','HMR q36 b984','PUSH_CONDITION if b361',
              'CX q17 q21','CX q0 q21','CX q18 q21','CX q43 q21',
              'CCX q17 q19 q21','POP_CONDITION']
    assert ref.operations[rb-1].kind=='HMR' and ref.operations[rb-1].arguments==('q36','b984')
    block_origins=[b-1 if line=='HMR q36 b984' else None for line in gates]
    byline={o.line:i for i,o in enumerate(p.operations)};lines=['# '+NOTICE];origins=[];mapping={}
    for line_number,literal in enumerate(text.splitlines(),1):
        i=byline.get(line_number)
        if i is None:lines.append(literal);continue
        mapping[i]=len(origins)
        if i==a:lines.extend(gates);origins.extend(block_origins)
        if a<=i<b:continue
        lines.append(literal);origins.append(i)
    mapping[len(p.operations)]=len(origins)
    changed='\n'.join(lines)+'\n';candidate=Program(changed)
    assert candidate.measurements==p.measurements and candidate.wires==p.wires
    xs=np.arange(1,3133453,dtype=np.uint64);full=(1<<len(xs))-1
    frames=captures(p,{start,a},xs,formal=True,include_classical=True)
    assert not frames[a]['q21']
    ca,cb=mapping[start],mapping[b]
    old=replay(frames[start],p.operations[start:b],list(range(start,b)),p,{},full)
    new=replay(frames[start],candidate.operations[ca:cb],origins[ca:cb],p,{},full)
    assert all(old[0][q]==new[0][q] for q in p.wires),'FULL_DOMAIN_VALUE_OR_CLASSICAL_FAILURE'
    assert old[1]==new[1],'FULL_DOMAIN_PHASE_FAILURE'
    assert old[2]==new[2]
    assert max(m.bit_count() for m in new[3])<=43
    engine=ROOT/'incumbent_sources/frozen_source/fusion/runtime/work/c10/narrow/checkpoint002/cleanroom/baseline_stage97'
    sys.path.insert(0,str(engine/'tests'));sys.path.insert(0,str(engine/'engine'))
    from fourier_resource_expectation import exact_expectation
    resources=exact_expectation(changed);cost=Fraction(resources['mean']['toffoli_like']);delta=cost-1459
    assert delta==Fraction(1,4) and resources['mean']['T']=='1' and resources['mean']['generic_rotations']=='34'
    args.out.mkdir();dest=args.out/'candidate_text.kmx';dest.write_text(changed)
    atomic(args.out/'OPERATION_MAP.json.gz',dict(notice=NOTICE,parent_sha256=PARENT_SHA,
           candidate_sha256=sha(dest),old_cut_to_new_cut=mapping,new_operation_origin=origins,
           changed_interval_internal_cut_mapping_not_value_alignment=True))
    atomic(args.out/'LOCAL_OCCUPANCY.json.gz',dict(notice=NOTICE,parent_start_cut=start,
           parent_masks=old[3],candidate_start_cut=ca,candidate_masks=new[3]))
    report=dict(notice=NOTICE,status='LONG_SECOND_DELAYED_Q21_NATIVE_LOCAL_FULL_DOMAIN_ALL_HMR_PASS',
                numerical_verification='AGENT_VERIFIED_ROOT_REPLAY_PENDING',qualified=False,
                source_sha256=sha(__file__),parent_native_sha256=PARENT_SHA,candidate_native_sha256=sha(dest),
                reference_native_sha256=REFERENCE_SHA,reference_replaced_interval=[ra,rb],
                reference_local_proof_interval=[rstart,rb],parent_replaced_interval=[a,b],
                parent_local_proof_interval=[start,b],candidate_local_proof_interval=[ca,cb],
                replacement_gates=gates,phase_bundles={k:sorted(v) for k,v in bundles.items()},
                implicit_value='b361*(q17*q19+q17+q0+q18+q43) after q17/q19 preparation',
                original_HMR_preserved=True,original_HMR=['q36','b984'],
                exact_added_paid_CCZ_guards=['b361 AND b366','b361 AND b367'],
                exact_added_paid_CCZ_probabilities=['1/8','1/8'],
                exact_added_expected_Toffolis=str(delta),exact_candidate_expected_Toffolis=str(cost),
                full_legal_original_inputs=len(xs),all_HMR_formal=True,
                original_quantum_and_classical_values_identical_at_endpoint=True,
                complete_local_phase_identical=True,rotation_reads_unchanged=True,
                extra_quantum_owners=0,candidate_local_peak=max(m.bit_count() for m in new[3]),
                additional_peak44_windows_removed=1,additional_peak44_cuts_removed=sum(m.bit_count()==44 for m in old[3]),
                remaining_peak44_windows_model=44,remaining_peak44_cuts_model=445,
                local_occupancy_histogram=dict(sorted(Counter(m.bit_count() for m in new[3]).items())),
                native_resources=resources,whole_official_proof_and_rebuild_pending=True,
                global_Q43_not_yet_claimed=True,seconds=time.monotonic()-started)
    atomic(args.out/'REPORT.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('native_resources','replacement_gates')}),flush=True)


if __name__=='__main__':main()
