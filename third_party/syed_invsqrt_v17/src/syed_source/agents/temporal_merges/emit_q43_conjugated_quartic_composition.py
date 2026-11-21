# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Replace six paid phase fallbacks by exact cheaper dirty-parity conjugations.

Every replacement is first verified as a universal Boolean phase identity,
then replayed on every3,133,452 original input and every formal native HMR.
The original value computations, outcome events, rotations and all branches
are retained. No extra quantum owner or unproved value decoder is introduced.
"""
import argparse
import json
import sys
import time
from fractions import Fraction
from pathlib import Path
import numpy as np
from temporal_core import NOTICE,Program,Span,captures,sha,bits
from analyze_q43_long_virtual_phase import mul,add
from synthesize_q43_long_virtual_phase import product_polynomial
from emit_q43_long_virtual_q21 import prepare_parities,free_phase
from emit_q43_deferred_idle_plans import replay
from lift_q43_joint_overflow_C_fibers import atomic

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PARENT_SHA='c3c163452c3bd01d73827d97abbd9bc4a0fb9fad59a89785e61c91386e0018a2'


def owners(mask):return [f'q{q}' for q in bits(mask)]


def phase_terms(poly):return [owners(m) for m in sorted(poly)]


def cubic_lines(factors):
    prep,pp=prepare_parities([owners(m) for m in factors])
    return prep+['CCZ '+' '.join(pp)]+prep[::-1]


def old_body(branch):
    prep,pp=prepare_parities(branch['quartic_factors']);a,b,c,d=pp
    body=prep+[f'CCX {a} {b} q1',f'CCZ q1 {c} {d}',f'CCX {a} {b} q1',f'CCZ q1 {c} {d}']+prep[::-1]
    for factors in branch['cubic_products']:
        prep,pp=prepare_parities(factors);body+=prep+['CCZ '+' '.join(pp)]+prep[::-1]
    body+=free_phase(branch.get('free_phase_terms',branch.get('free_terms')))
    return body


def new_body(row):
    r=row['conjugation'];assert r['paid_gates']==3 and r['three_gate_dirty_parity_independent']
    four=r['quartic_factors'];U,T=r['U'],r['T']
    I=Span()
    for f in four+[T]:assert I.add(f)
    coefficient=I.solve(U)
    factors=four+[T]
    if coefficient is None:factors.append(U)
    else:assert not (coefficient>>4)&1
    prep,pp=prepare_parities([owners(m) for m in factors])
    a,b,c,d,t=pp[:5]
    us=[pp[5]] if coefficient is None else [pp[j] for j in bits(coefficient)]
    assert t not in us and 'q21' not in pp
    u_phase=[f'CZ {t} {u}' for u in us]
    body=prep+[f'CCX {a} {b} {t}',f'CCZ {t} {c} {d}']+u_phase+[f'CCX {a} {b} {t}']+u_phase+prep[::-1]
    body+=free_phase(phase_terms(r['free_remainder']))
    for factors in row['extra_cubic_factor_masks']:body+=cubic_lines(factors)
    return body


def verify_body(body,target):
    initial={f'q{q}':frozenset([1<<q]) for q in range(44)}
    state=dict(initial);phase=frozenset()
    for o in Program('\n'.join(body)).operations:
        k,a=o.kind,o.arguments;assert o.condition is None
        if k=='X':state[a[0]]=add(state[a[0]],frozenset([0]))
        elif k=='CX':state[a[1]]=add(state[a[1]],state[a[0]])
        elif k=='CCX':state[a[2]]=add(state[a[2]],mul(state[a[0]],state[a[1]]))
        elif k in ('Z','CZ','CCZ','NEG'):
            term=frozenset([0])
            for q in a:term=mul(term,state[q])
            phase^=term
        else:raise AssertionError(k)
    assert state==initial and phase==target


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();assert not args.out.exists();started=time.monotonic()
    native=HERE/'q43_middle_long_virtual_q21_native_v1/candidate_text.kmx';assert sha(native)==PARENT_SHA
    lift_path=HERE/'q43_conjugated_quartic_lift_v2/REPORT.json';lift=json.loads(lift_path.read_text())
    long_path=HERE/'q43_long_virtual_phase_synthesis_v1/REPORT.json';long=json.loads(long_path.read_text())
    middle_path=HERE/'q43_middle_long_virtual_q21_native_v1/REPORT.json';middle=json.loads(middle_path.read_text())
    text=native.read_text();p=Program(text);sig=lambda o:(o.kind,o.arguments,o.condition,o.half_turns)
    actual=[sig(o) for o in p.operations];replacements=[]
    for row in lift['records']:
        if row['domain']=='long':
            j=row['sector']['u']*2+row['sector']['v'];branch=long['branches'][j];guard=f'b{8004+j}'
            suffix=['PUSH_CONDITION if b197']+free_phase(branch['free_future_HMR_phase_terms'])+['POP_CONDITION']
            limits=[0,len(actual)]
        else:
            j=row['sector']['u'];branch=middle['phase_plans'][j];guard=branch['guard'];suffix=[]
            limits=middle['candidate_interval']
        old=old_body(branch);new=new_body(row)
        target=product_polynomial([sum(1<<int(q[1:]) for q in factor) for factor in branch['quartic_factors']])
        for ff in branch['cubic_products']:
            target^=product_polynomial([sum(1<<int(q[1:]) for q in factor) for factor in ff])
        target^=frozenset(sum(1<<int(q[1:]) for q in terms) for terms in branch.get('free_phase_terms',branch.get('free_terms')))
        verify_body(old,target);verify_body(new,target)
        old=[f'PUSH_CONDITION if {guard}']+old+suffix+['POP_CONDITION']
        new=[f'PUSH_CONDITION if {guard}']+new+suffix+['POP_CONDITION']
        wanted=[sig(o) for o in Program('\n'.join(old)).operations]
        matches=[i for i in range(limits[0],limits[1]-len(wanted)+1) if actual[i]==wanted[0] and actual[i:i+len(wanted)]==wanted]
        assert len(matches)==1,(row['domain'],row['sector'],matches)
        a=matches[0];b=a+len(wanted)
        replacements.append(dict(domain=row['domain'],sector=row['sector'],guard=guard,parent_interval=[a,b],
                                 old_paid_gates=6,new_paid_gates=row['total_paid_gates'],gates=new,
                                 universal_boolean_phase_identity_verified=True))
    replacements.sort(key=lambda r:r['parent_interval'][0])
    assert all(x['parent_interval'][1]<=y['parent_interval'][0] for x,y in zip(replacements,replacements[1:]))
    starts={r['parent_interval'][0]:r for r in replacements};skip={i for r in replacements for i in range(*r['parent_interval'])}
    byline={o.line:i for i,o in enumerate(p.operations)};lines=['# '+NOTICE];origins=[];mapping={}
    for line_number,literal in enumerate(text.splitlines(),1):
        i=byline.get(line_number)
        if i is None:lines.append(literal);continue
        mapping[i]=len(origins)
        if i in starts:lines.extend(starts[i]['gates']);origins.extend([None]*len(starts[i]['gates']))
        if i in skip:continue
        lines.append(literal);origins.append(i)
    mapping[len(p.operations)]=len(origins)
    changed='\n'.join(lines)+'\n';candidate=Program(changed)
    assert candidate.measurements==p.measurements and candidate.wires==p.wires
    xs=np.arange(1,3133453,dtype=np.uint64);full=(1<<len(xs))-1
    caps=captures(p,{r['parent_interval'][0] for r in replacements},xs,formal=True,include_classical=True)
    for row in replacements:
        a,b=row['parent_interval'];initial=caps[a];assert not initial['q21']
        ca,cb=mapping[a],mapping[b]
        old=replay(initial,p.operations[a:b],list(range(a,b)),p,{},full)
        new=replay(initial,candidate.operations[ca:cb],origins[ca:cb],p,{},full)
        assert all(old[0][q]==new[0][q] for q in p.wires)
        assert old[1]==new[1] and old[2]==new[2]
        assert max(m.bit_count() for m in new[3])<=43
        row.update(candidate_interval=[ca,cb],full_input_all_HMR_phase_pass=True,candidate_local_peak=max(m.bit_count() for m in new[3]))
    engine=ROOT/'incumbent_sources/frozen_source/fusion/runtime/work/c10/narrow/checkpoint002/cleanroom/baseline_stage97'
    sys.path.insert(0,str(engine/'tests'));sys.path.insert(0,str(engine/'engine'))
    from fourier_resource_expectation import exact_expectation
    resources=exact_expectation(changed);cost=Fraction(resources['mean']['toffoli_like']);delta=cost-1462
    assert delta==Fraction(-19,8) and cost==Fraction(11677,8)
    assert resources['mean']['T']=='1' and resources['mean']['generic_rotations']=='34'
    args.out.mkdir();dest=args.out/'candidate_text.kmx';dest.write_text(changed)
    atomic(args.out/'OPERATION_MAP.json.gz',dict(notice=NOTICE,parent_sha256=PARENT_SHA,candidate_sha256=sha(dest),
           old_cut_to_new_cut=mapping,new_operation_origin=origins,changed_interval_internal_cut_mapping_not_value_alignment=True))
    report=dict(notice=NOTICE,status='CHEAPER_QUARTIC_COMPOSITION_NATIVE_UNIVERSAL_AND_FULL_DOMAIN_ALL_HMR_LOCAL_PASS',
        numerical_verification='AGENT_VERIFIED_ROOT_REPLAY_PENDING',qualified=False,source_sha256=sha(__file__),
        parent_native_sha256=PARENT_SHA,candidate_native_sha256=sha(dest),phase_lift_sha256=sha(lift_path),
        original_long_phase_plan_sha256=sha(long_path),original_middle_emitter_receipt_sha256=sha(middle_path),
        full_legal_original_inputs=len(xs),all_HMR_formal=True,universal_phase_and_value_identity_per_replacement=True,
        six_replacements=replacements,original_HMR_events_and_classical_relations_preserved=True,
        exact_added_expected_Toffolis=str(delta),exact_candidate_expected_Toffolis=str(cost),
        exact_saving_over_proved_0e4a_parent_after_adding_middle105_cut_solution='-3/8',
        extra_quantum_owners=0,Q=44,T=1,rotations=34,
        remaining_peak44_windows_model=43,remaining_peak44_cuts_model=340,
        remaining_groups=[dict(id='early_carry',windows=21,cuts=158),dict(id='q35_decoder',windows=22,cuts=182)],
        conservative_budget_remaining=str(Fraction(251427,172)-cost),
        secondary_official_resource_budget_remaining_root_supplied_decimal='7.977860267',
        native_resources=resources,whole_official_proof_and_rebuild_pending=True,global_Q43_not_yet_claimed=True,
        seconds=time.monotonic()-started)
    atomic(args.out/'REPORT.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('native_resources','six_replacements')}),flush=True)


if __name__=='__main__':main()
