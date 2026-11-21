# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Construct a width43 fallback for the remaining105-cut middle packet.

Old-outcome phase repair is applied in the entry frame. The only value
transfer uses one direct CCX into q0. Original HMR b978 remains on cleanq21,
and its phase is repaid by a free quadratic in the actual endpoint frame.
"""
import argparse
import json
import sys
import time
from collections import Counter
from fractions import Fraction
from pathlib import Path
import numpy as np
from temporal_core import NOTICE, Program, captures, sha, bits
from emit_q43_deferred_idle_plans import replay
from emit_q43_long_virtual_q21 import prepare_parities,free_phase
from synthesize_q43_long_virtual_phase import support_basis,product_polynomial,cubic_factors
from analyze_q43_middle_long_phase import TRANSFER
from lift_q43_joint_overflow_C_fibers import atomic

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PARENT_SHA='0e4a525f98bc492ccfb5e05d04983eabc3bbd036e26e77a9bb244aabb77421da'


def owners(mask):return [f'q{q}' for q in bits(mask)]


def phase_terms(poly):return [owners(m) for m in sorted(poly)]


def cubic_lines(factors):
    prep,pivots=prepare_parities([owners(m) for m in factors])
    return prep+['CCZ '+' '.join(pivots)]+prep[::-1]


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();assert not args.out.exists();started=time.monotonic()
    native=HERE/'q43_long_second_delayed_q21_native_v1/candidate_text.kmx';assert sha(native)==PARENT_SHA
    refpath=HERE/'q43_late_short_affine_native_v1/candidate_text.kmx'
    contract=HERE/'q43_middle_long_phase_v1/REPORT.json';data=json.loads(contract.read_text())
    assert sha(refpath)==data['native_sha256']
    text=native.read_text();p=Program(text);ref=Program(refpath.read_text());a,b=data['interval']
    sig=lambda o:(o.kind,o.arguments,o.condition,o.half_turns)
    assert [sig(o) for o in p.operations[a:b]]==[sig(o) for o in ref.operations[a:b]]
    by={tuple(c['HMR_events']):frozenset(sum(1<<q for q in t) for t in c['quantum_terms']) for c in data['coefficients']}
    bit='b'+str(1+max(int(q[1:]) for q in p.wires if q.startswith('b')))
    prefix=[f'BIT_STORE0 {bit}',f'BIT_INVERT {bit} if b170',f'BIT_INVERT {bit} if b360']
    phase_plans=[]
    for u,guard in [(0,'b366'),(1,'b367')]:
        target=by[(846,)]^(by[(292,846)] if u else frozenset())
        quartic=support_basis(target,4);assert len(quartic)==4
        residual=target^product_polynomial(quartic)
        cubics=cubic_factors(residual)
        for factors in cubics:residual^=product_polynomial(factors)
        assert len(cubics)==2 and max(m.bit_count() for m in residual)<=2
        prep,pp=prepare_parities([owners(m) for m in quartic]);assert 'q1' not in pp
        assert all(not(mask>>1&1) for mask in quartic)
        aa,bb,cc,dd=pp
        prefix += [f'PUSH_CONDITION if {guard}']+prep+[
            f'CCX {aa} {bb} q1',f'CCZ q1 {cc} {dd}',f'CCX {aa} {bb} q1',f'CCZ q1 {cc} {dd}']+prep[::-1]
        for factors in cubics:prefix+=cubic_lines(factors)
        prefix+=free_phase(phase_terms(residual))+['POP_CONDITION']
        phase_plans.append(dict(guard=guard,probability='1/4',quartic_factors=[owners(m) for m in quartic],
                                cubic_products=[[owners(m) for m in fs] for fs in cubics],free_terms=phase_terms(residual)))
    extra=by[(305,846)];assert extra==by[(825,846)]
    factors=cubic_factors(extra);assert len(factors)==1
    residual=extra^product_polynomial(factors[0]);assert max(m.bit_count() for m in residual)<=2
    prefix+=['PUSH_CONDITION if b359',f'PUSH_CONDITION if {bit}']+cubic_lines(factors[0])+free_phase(phase_terms(residual))+['POP_CONDITION','POP_CONDITION']
    prefix+=['PUSH_CONDITION if b359','PUSH_CONDITION if b169']+free_phase(phase_terms(by[(304,846)]))+['POP_CONDITION','POP_CONDITION']
    skip=set(data['skipped_operations']);literals=text.splitlines();kept=[];ko=[]
    for i in range(a,b):
        if i in skip:continue
        if i==data['direct_value_transfer_operation']:kept+=TRANSFER;ko += [None]*len(TRANSFER)
        else:kept.append(literals[p.operations[i].line-1]);ko.append(i)
    prep,pp=prepare_parities([['q43','q34'],['q30','q43','q36']])
    suffix=['PUSH_CONDITION if b359','PUSH_CONDITION if b978']+prep+['CZ '+' '.join(pp)]+prep[::-1]+['Z q34','POP_CONDITION','POP_CONDITION']
    block=prefix+kept+suffix;bo=[None]*len(prefix)+ko+[None]*len(suffix)
    byline={o.line:i for i,o in enumerate(p.operations)};lines=['# '+NOTICE];origins=[];mapping={}
    for line_number,literal in enumerate(text.splitlines(),1):
        i=byline.get(line_number)
        if i is None:lines.append(literal);continue
        mapping[i]=len(origins)
        if i==a:lines.extend(block);origins.extend(bo)
        if a<=i<b:continue
        lines.append(literal);origins.append(i)
    mapping[len(p.operations)]=len(origins)
    changed='\n'.join(lines)+'\n';candidate=Program(changed)
    assert candidate.measurements==p.measurements and candidate.wires-p.wires=={bit}
    xs=np.arange(1,3133453,dtype=np.uint64);full=(1<<len(xs))-1
    initial=captures(p,{a},xs,formal=True,include_classical=True)[a];assert not initial['q21'];initial[bit]={}
    for name,event in [('b359',846),('b169',304),('b170',305),('b360',825)]:assert initial[name]=={1<<event:full}
    ca,cb=mapping[a],mapping[b]
    old=replay(initial,p.operations[a:b],list(range(a,b)),p,{},full)
    new=replay(initial,candidate.operations[ca:cb],origins[ca:cb],p,{},full)
    assert all(old[0][q]==new[0][q] for q in p.wires),'FULL_DOMAIN_VALUE_OR_CLASSICAL_FAILURE'
    assert old[1]==new[1],'FULL_DOMAIN_PHASE_FAILURE'
    assert old[2]==new[2] and max(m.bit_count() for m in new[3])<=43
    engine=ROOT/'incumbent_sources/frozen_source/fusion/runtime/work/c10/narrow/checkpoint002/cleanroom/baseline_stage97'
    sys.path.insert(0,str(engine/'tests'));sys.path.insert(0,str(engine/'engine'))
    from fourier_resource_expectation import exact_expectation
    resources=exact_expectation(changed);cost=Fraction(resources['mean']['toffoli_like']);delta=cost-Fraction(5837,4)
    assert delta==Fraction(11,4) and resources['mean']['T']=='1' and resources['mean']['generic_rotations']=='34'
    args.out.mkdir();dest=args.out/'candidate_text.kmx';dest.write_text(changed)
    atomic(args.out/'OPERATION_MAP.json.gz',dict(notice=NOTICE,parent_sha256=PARENT_SHA,candidate_sha256=sha(dest),
           old_cut_to_new_cut=mapping,new_operation_origin=origins,changed_interval_internal_cut_mapping_not_value_alignment=True))
    atomic(args.out/'LOCAL_OCCUPANCY.json.gz',dict(notice=NOTICE,parent_start_cut=a,parent_masks=old[3],candidate_start_cut=ca,candidate_masks=new[3]))
    report=dict(notice=NOTICE,status='MIDDLE_LONG_VIRTUAL_Q21_NATIVE_LOCAL_FULL_DOMAIN_ALL_HMR_PASS',
        numerical_verification='AGENT_VERIFIED_ROOT_REPLAY_PENDING',qualified=False,source_sha256=sha(__file__),
        parent_native_sha256=PARENT_SHA,candidate_native_sha256=sha(dest),contract_sha256=sha(contract),
        parent_interval=[a,b],candidate_interval=[ca,cb],phase_plans=phase_plans,
        extra_cubic_guard='b359 AND (b170 XOR b360)',extra_cubic_probability='1/4',
        old_outcome_phase_repair_cost='13/4',removed_native_CCZ_cost='1/2',
        original_birth_CCX_replaced_by_equal_cost_direct_value_transfer=True,
        original_HMR_preserved=['q21','b978'],dirty_owner='q1',dirty_owner_restored_exactly=True,
        extra_quantum_owners=0,exact_added_expected_Toffolis=str(delta),exact_candidate_expected_Toffolis=str(cost),
        full_legal_original_inputs=len(xs),all_HMR_formal=True,complete_local_phase_identical=True,
        original_quantum_and_classical_values_identical_at_endpoint=True,rotation_reads_unchanged=True,
        candidate_local_peak=max(m.bit_count() for m in new[3]),additional_peak44_windows_removed=1,
        additional_peak44_cuts_removed=sum(m.bit_count()==44 for m in old[3]),
        remaining_peak44_windows_model=43,remaining_peak44_cuts_model=340,
        remaining_groups=[dict(id='early_carry',windows=21,cuts=158),dict(id='q35_decoder',windows=22,cuts=182)],
        local_occupancy_histogram=dict(sorted(Counter(m.bit_count() for m in new[3]).items())),native_resources=resources,
        conservative_threshold_exceeded_by_current_fallback=True,secondary_official_resource_budget_remaining_root_supplied_decimal='5.602860267',
        whole_official_proof_and_rebuild_pending=True,global_Q43_not_yet_claimed=True,seconds=time.monotonic()-started)
    atomic(args.out/'REPORT.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('native_resources','phase_plans')}),flush=True)


if __name__=='__main__':main()
