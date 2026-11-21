# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Emit the long virtual-q21 packet with exact dirty-owner phase repair.

The original HMR is preserved on clean q21. Reversible affine replay returns
the other owners to the entry frame for the phase repair, then restores the
exit frame. Every quartic uses the existing dirty q1 and returns it exactly.
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
from lift_q43_joint_overflow_C_fibers import atomic

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
REFERENCE_SHA='70eaa20cbe8a658ecaa634eb42d6c9fc521310ef385300be124cf34e397fea7a'
PARENT_SHA='9ae0bacb48b018958be750018cb28e852bd3abe2eb69a13ebf860758bdfdd952'


def prepare_parities(factors):
    remaining=[set(f) for f in factors];pivots=[];gates=[]
    for i in range(len(remaining)):
        row=remaining[i];options=row-set(pivots);assert options
        pivot=min(options,key=lambda q:int(q[1:]));pivots.append(pivot)
        for source in sorted(row-{pivot},key=lambda q:int(q[1:])):
            gates.append(f'CX {source} {pivot}')
            for j in range(i+1,len(remaining)):
                if pivot in remaining[j]:remaining[j].symmetric_difference_update({source})
    return gates,pivots


def wrapped(guards,literal):
    return [f'PUSH_CONDITION if {b}' for b in guards]+[literal]+['POP_CONDITION']*len(guards)


def free_phase(terms):
    return [('NEG' if not t else 'Z' if len(t)==1 else 'CZ')+(' '+' '.join(t) if t else '') for t in terms]


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();assert not args.out.exists();started=time.monotonic()
    native=HERE/'q43_middle_short_virtual_q21_native_v1/candidate_text.kmx'
    reference=HERE/'q43_late_short_affine_native_v1/candidate_text.kmx'
    assert sha(native)==PARENT_SHA and sha(reference)==REFERENCE_SHA
    phase_path=HERE/'q43_long_virtual_phase_synthesis_v1/REPORT.json'
    phase=json.loads(phase_path.read_text())
    debt_path=HERE/'q43_long_virtual_phase_v1/REPORT.json';debt=json.loads(debt_path.read_text())
    with gzip.open(HERE/'q43_middle_short_virtual_q21_native_v1/OPERATION_MAP.json.gz','rt') as f:
        alignment=json.load(f)
    assert alignment['parent_sha256']==REFERENCE_SHA and alignment['candidate_sha256']==PARENT_SHA
    old_a,old_b=18941,19140
    a,b=[alignment['old_cut_to_new_cut'][str(i)] for i in (old_a,old_b)]
    assert [a,b]==[18960,19159]
    text=native.read_text();p=Program(text);ref=Program(reference.read_text())
    sig=lambda o:(o.kind,o.arguments,o.condition,o.half_turns)
    assert [sig(o) for o in p.operations[a:b]]==[sig(o) for o in ref.operations[old_a:old_b]]
    skip={a+i-old_a for i in debt['skipped_operations']}
    first_bit=1+max(int(q[1:]) for q in p.wires if q.startswith('b'))
    guard_bits=[f'b{first_bit+j}' for j in range(4)]
    start_guard=[]
    # b363=m292, b364=m846, b365=m881. Four disjoint sectors each have probability1/8.
    for j,branch in enumerate(phase['branches']):
        u,v=branch['outcomes']['292'],branch['outcomes']['846'];g=guard_bits[j]
        start_guard += [f'BIT_STORE0 {g}','PUSH_CONDITION if b365']
        if not u:start_guard.append('BIT_INVERT b363')
        if not v:start_guard.append('BIT_INVERT b364')
        start_guard += ['PUSH_CONDITION if b363','PUSH_CONDITION if b364',f'BIT_INVERT {g}',
                        'POP_CONDITION','POP_CONDITION']
        if not v:start_guard.append('BIT_INVERT b364')
        if not u:start_guard.append('BIT_INVERT b363')
        start_guard.append('POP_CONDITION')
    literals=text.splitlines();kept=[];kept_origins=[];skeleton=[];stack=[]
    for i in range(a,b):
        o=p.operations[i]
        if o.kind=='PUSH_CONDITION':
            assert o.condition is not None;stack.append(o.condition)
        elif o.kind=='POP_CONDITION':stack.pop()
        if i in skip:continue
        kept.append(literals[o.line-1]);kept_origins.append(i)
        if o.kind in ('CX','X','BIT_INVERT'):
            guards=stack+([o.condition] if o.condition else [])
            if o.kind=='BIT_INVERT':assert o.arguments[0] not in guards
            assert 'q21' not in o.arguments and 'b197' not in o.arguments and 'b197' not in guards
            skeleton.append((list(guards),o.kind+' '+' '.join(o.arguments)))
        elif o.kind not in ('PUSH_CONDITION','POP_CONDITION','Z','CZ','CCZ','HMR','NEG'):
            raise AssertionError((i,o.kind))
    assert not stack
    inverse=[line for guards,literal in reversed(skeleton) for line in wrapped(guards,literal)]
    forward=[line for guards,literal in skeleton for line in wrapped(guards,literal)]
    repair=[]
    for guard,branch in zip(guard_bits,phase['branches']):
        repair.append(f'PUSH_CONDITION if {guard}')
        prep,pivots=prepare_parities(branch['quartic_factors'])
        assert 'q1' not in pivots and all('q1' not in f for f in branch['quartic_factors'])
        u,v,w,z=pivots
        repair += prep+[f'CCX {u} {v} q1',f'CCZ q1 {w} {z}',
                        f'CCX {u} {v} q1',f'CCZ q1 {w} {z}']+prep[::-1]
        for cubic in branch['cubic_products']:
            prep,pp=prepare_parities(cubic)
            repair += prep+['CCZ '+' '.join(pp)]+prep[::-1]
        repair += free_phase(branch['free_phase_terms'])
        repair.append('PUSH_CONDITION if b197')
        repair += free_phase(branch['free_future_HMR_phase_terms'])
        repair += ['POP_CONDITION','POP_CONDITION']
    block=start_guard+kept+inverse+repair+forward
    block_origins=[None]*len(start_guard)+kept_origins+[None]*(len(inverse)+len(repair)+len(forward))
    assert all('q21' not in line.split() for line in block if not line.startswith('HMR q21 '))
    byline={o.line:i for i,o in enumerate(p.operations)};lines=['# '+NOTICE];origins=[];mapping={}
    for line_number,literal in enumerate(text.splitlines(),1):
        i=byline.get(line_number)
        if i is None:lines.append(literal);continue
        mapping[i]=len(origins)
        if i==a:lines.extend(block);origins.extend(block_origins)
        if a<=i<b:continue
        lines.append(literal);origins.append(i)
    mapping[len(p.operations)]=len(origins)
    changed='\n'.join(lines)+'\n';candidate=Program(changed)
    assert candidate.measurements==p.measurements and candidate.wires-p.wires==set(guard_bits)
    xs=np.arange(1,3133453,dtype=np.uint64);full=(1<<len(xs))-1
    initial=captures(p,{a},xs,formal=True,include_classical=True)[a]
    assert not initial['q21']
    for name,event in [('b363',292),('b364',846),('b365',881)]:
        assert initial[name]=={1<<event:full}
    initial.update({g:{} for g in guard_bits})
    ca,cb=mapping[a],mapping[b]
    old=replay(initial,p.operations[a:b],list(range(a,b)),p,{},full)
    new=replay(initial,candidate.operations[ca:cb],origins[ca:cb],p,{},full)
    assert all(old[0][q]==new[0][q] for q in p.wires),'FULL_DOMAIN_VALUE_OR_CLASSICAL_FAILURE'
    assert old[1]==new[1],'FULL_DOMAIN_PHASE_FAILURE'
    assert old[2]==new[2]
    assert max(m.bit_count() for m in new[3])<=43
    engine=ROOT/'incumbent_sources/frozen_source/fusion/runtime/work/c10/narrow/checkpoint002/cleanroom/baseline_stage97'
    sys.path.insert(0,str(engine/'tests'));sys.path.insert(0,str(engine/'engine'))
    from fourier_resource_expectation import exact_expectation
    resources=exact_expectation(changed);cost=Fraction(resources['mean']['toffoli_like']);delta=cost-Fraction(5827,4)
    assert resources['mean']['T']=='1' and resources['mean']['generic_rotations']=='34'
    args.out.mkdir();dest=args.out/'candidate_text.kmx';dest.write_text(changed)
    atomic(args.out/'OPERATION_MAP.json.gz',dict(notice=NOTICE,parent_sha256=PARENT_SHA,
           candidate_sha256=sha(dest),old_cut_to_new_cut=mapping,new_operation_origin=origins,
           changed_interval_internal_cut_mapping_not_value_alignment=True))
    atomic(args.out/'LOCAL_OCCUPANCY.json.gz',dict(notice=NOTICE,parent_start_cut=a,
           parent_masks=old[3],candidate_start_cut=ca,candidate_masks=new[3]))
    report=dict(notice=NOTICE,status='LONG_VIRTUAL_Q21_DIRTY_PHASE_NATIVE_LOCAL_FULL_DOMAIN_ALL_HMR_PASS',
                numerical_verification='AGENT_VERIFIED_ROOT_REPLAY_PENDING',qualified=False,
                source_sha256=sha(__file__),parent_native_sha256=PARENT_SHA,candidate_native_sha256=sha(dest),
                reference_native_sha256=REFERENCE_SHA,reference_interval=[old_a,old_b],parent_interval=[a,b],
                candidate_interval=[ca,cb],phase_plan_sha256=sha(phase_path),phase_debt_sha256=sha(debt_path),
                full_legal_original_inputs=len(xs),all_HMR_formal=True,
                original_quantum_and_classical_values_identical_at_endpoint=True,
                complete_local_phase_identical=True,rotation_reads_unchanged=True,
                original_HMR_preserved=True,original_HMR=['q21','b197'],dirty_owner='q1',
                dirty_owner_returned_exactly=True,extra_quantum_owners=0,
                classical_sector_guards=[dict(bit=g,outcomes=r['outcomes'],probability='1/8') for g,r in zip(guard_bits,phase['branches'])],
                phase_repair_expected_paid_gates='3',exact_added_expected_Toffolis=str(delta),
                exact_candidate_expected_Toffolis=str(cost),candidate_local_peak=max(m.bit_count() for m in new[3]),
                additional_peak44_windows_removed=1,additional_peak44_cuts_removed=sum(m.bit_count()==44 for m in old[3]),
                includes_free_q9_and_middle_quarter_components=True,
                remaining_peak44_windows_model=45,remaining_peak44_cuts_model=488,
                local_occupancy_histogram=dict(sorted(Counter(m.bit_count() for m in new[3]).items())),
                native_resources=resources,whole_official_proof_and_rebuild_pending=True,
                global_Q43_not_yet_claimed=True,seconds=time.monotonic()-started)
    atomic(args.out/'REPORT.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='native_resources'}),flush=True)


if __name__=='__main__':main()
