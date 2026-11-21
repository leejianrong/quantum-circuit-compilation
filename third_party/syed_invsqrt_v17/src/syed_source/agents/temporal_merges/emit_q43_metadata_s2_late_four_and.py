# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Emit the actual four-AND S2 decoder at the late native cut28240.

The original g0..g3 are retained native computations, with no extra capture
or cleanup cost. Their exact current physical affine forms are frozen in
the full-domain frame contract. q7 is the sole clean decoder helper, and
its complete quadratic phase is repaid before originaloperation28240.
"""
import argparse
from collections import Counter
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
from temporal_core import NOTICE,Program,captures,mul,sha,xor
from emit_q43_deferred_idle_plans import product_lines,replay
from construct_q35_retained_G_cubic_cofactor import component

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PARENT=ROOT/'agents/paid_helper/final_carry_guarded_borrow_native_v1/candidate_text.kmx'
PARENT_SHA='a4e2ff8d795f6713171440e32ccb024fef98ef2a83469f38a7d74a987ab3c793'
PLAN=HERE/'q43_s2_late_fixed_Q1_minimum_v1/REPORT.json'
BINDING=HERE/'Q43_S2_LATE_NATIVE_PRODUCTS_FRAME_V1.json'
ENTRY=25690
EXIT=28240


def dump(path,value):Path(path).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def dump_gz(path,value):
    with Path(path).open('wb') as f:
        with gzip.GzipFile(fileobj=f,mode='wb',mtime=0,filename='') as z:
            z.write((json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode())


def physical_form(logical_terms,forms):
    constant=False;owners=set()
    for name in logical_terms:
        for term in (['constant'] if name=='constant' else forms[name]):
            if term=='constant':constant=not constant
            elif term in owners:owners.remove(term)
            else:owners.add(term)
    assert 'q7' not in owners and 'q35' not in owners
    return constant,owners


def affine_lines(form,target):
    constant,owners=form;assert target not in owners
    return ([f'X {target}'] if constant else [])+[f'CX {q} {target}' for q in sorted(owners,key=lambda q:int(q[1:]))]


def product_affine(aa,bb,target):
    a0,a=aa;b0,b=bb;assert target not in a|b
    lines=[];linear=set()
    if a and b:
        if a==b:linear.symmetric_difference_update(a)
        else:lines+=product_lines(a,b,target)
    if a0:linear.symmetric_difference_update(b)
    if b0:linear.symmetric_difference_update(a)
    return lines+affine_lines((a0 and b0,linear),target)


def stream(plan,target,forms):
    lines=[]
    for p in plan['products']:
        lines+=product_affine(physical_form(p['A'],forms),physical_form(p['B'],forms),target)
    return lines+affine_lines(physical_form(plan['affine_terms'],forms),target)


def phase_terms(plan,forms):
    terms=set()
    def toggle(term):
        term=frozenset(term)
        if term in terms:terms.remove(term)
        else:terms.add(term)
    def expansion(form):
        constant,owners=form
        return ([frozenset()] if constant else [])+[frozenset([q]) for q in owners]
    for p in plan['products']:
        for a in expansion(physical_form(p['A'],forms)):
            for b in expansion(physical_form(p['B'],forms)):toggle(a|b)
    for term in expansion(physical_form(plan['affine_terms'],forms)):toggle(term)
    assert all(len(t)<=2 for t in terms)
    return sorted(terms,key=lambda t:(len(t),tuple(sorted(int(q[1:]) for q in t))))


def evaluate_component(plan,values,full):
    result=0
    for product in plan['products']:
        a=b=0
        for name in product['A']:a^=values[name]
        for name in product['B']:b^=values[name]
        result^=a&b
    for name in plan['affine_terms']:result^=full if name=='constant' else values[name]
    return result


def build(out):
    plan=json.loads(PLAN.read_text());binding=json.loads(BINDING.read_text())
    assert plan['actual_ANDs']==4 and plan['status']=='ACTUAL_LATE_S2_DECODER_WITHIN_FOUR_ANDS'
    assert plan['full_native_binding_sha256']==sha(BINDING)
    assert binding['parent_native_sha256']==PARENT_SHA and binding['new_restore_cut']==EXIT
    assert binding['clean_quadratic_helper']=='q7' and binding['streamed_output_plus_one_helper_peak_bound']==43
    Q0,Q1=plan['Q0'],plan['Q1'];assert [Q0['product_count'],Q1['product_count']]==[2,1]
    full,values=component()
    assert evaluate_component(Q0,values,full)^(values['D9']&evaluate_component(Q1,values,full))==values['S2']
    forms=binding['desired_control_physical_parities']
    assert sha(PARENT)==PARENT_SHA
    text=PARENT.read_text();parent=Program(text)
    assert len(parent.operations)==36893 and parent.measurements==1318
    assert all('q0' not in o.arguments and 'q35' not in o.arguments for o in parent.operations[ENTRY:EXIT])
    fresh=1+max(int(q[1:]) for q in parent.wires if q.startswith('b'))
    mb,mh=f'b{fresh}',f'b{fresh+1}';fresh_events={mb:parent.measurements,mh:parent.measurements+1}
    entry=['SWAP q35 q0',f'HMR q35 {mb}']
    exit=stream(Q0,'q35',forms)+stream(Q1,'q7',forms)
    exit+=product_affine(physical_form(['D9'],forms),(False,{'q7'}),'q35')
    exit+=[f'HMR q7 {mh}'];feedback=phase_terms(Q1,forms)
    for term in feedback:
        owners=sorted(term,key=lambda q:int(q[1:]))
        literal=('NEG' if not owners else ('Z ' if len(owners)==1 else 'CZ ')+' '.join(owners))
        exit.append(literal+f' if {mh}')
    exit += [f'Z q35 if {mb}','SWAP q35 q0']
    added=Program('\n'.join(entry+exit))
    assert sum(o.kind=='CCX' for o in added.operations)==4
    assert all(o.kind not in ('CCZ','Z_POW') for o in added.operations)
    inserts={ENTRY:entry,EXIT:exit};by_line={o.line:i for i,o in enumerate(parent.operations)}
    lines=['# '+NOTICE];origins=[];mapping={}
    for lineno,line in enumerate(text.splitlines(),1):
        i=by_line.get(lineno)
        if i is None:lines.append(line);continue
        mapping[i]=len(origins);block=inserts.get(i,[])
        lines+=block;origins+=[None]*len(block)
        lines.append(line);origins.append(i)
    mapping[len(parent.operations)]=len(origins)
    changed='\n'.join(lines)+'\n';candidate=Program(changed)
    assert len(candidate.operations)==len(origins) and candidate.measurements==parent.measurements+2
    dest=out/'candidate_text.kmx';dest.write_text(changed)
    dump(out/'VALUE_WITNESS.json',dict(notice=NOTICE,source_plan_sha256=sha(PLAN),source_binding_sha256=sha(BINDING),
         parent_native_sha256=PARENT_SHA,component_rows=4096,target='S2',C='D9',Q0=Q0,Q1=Q1,
         controls=plan['control_names'],physical_control_parities=forms,actual_ANDs=4,
         native_products_already_retained=[28056,28102,28126,28197],extra_G_cost=0,
         all4096_identity=True,qualified=False))
    dump(out/'NATIVE_GATE_PLAN.json',dict(notice=NOTICE,parent_sha256=PARENT_SHA,entry_original_cut=ENTRY,
         restore_original_cut=EXIT,entry_gates=entry,restore_gates=exit,fresh_HMR_symbolic_events=fresh_events,
         quadratic_helper='q7',helper_HMR_before_original_operation=EXIT,
         first_following_old_G_HMR=28243,feedback_quadratic_terms=[sorted(t) for t in feedback],
         paid_products=4,paid_CCZ=0,added_T=0,added_rotations=0,
         source_expected_Toffolis='5845/4',expected_candidate_Toffolis='5861/4'))
    dump_gz(out/'OPERATION_MAP.json.gz',dict(notice=NOTICE,parent_sha256=PARENT_SHA,candidate_sha256=sha(dest),
             old_cut_to_new_cut=mapping,new_operation_origin=origins))
    engine=ROOT/'incumbent_sources/frozen_source/fusion/runtime/work/c10/narrow/checkpoint002/cleanroom/baseline_stage97'
    sys.path.insert(0,str(engine/'tests'));sys.path.insert(0,str(engine/'engine'))
    from fourier_resource_expectation import exact_expectation
    resources=exact_expectation(changed)
    assert Fraction(resources['mean']['toffoli_like'])==Fraction(5861,4)
    assert resources['mean']['T']=='1' and resources['mean']['generic_rotations']=='34'
    emission=dict(notice=NOTICE,status='DETERMINISTIC_LATE_FOUR_AND_NATIVE_EMITTED',source_sha256=sha(__file__),
        parent_native_sha256=PARENT_SHA,candidate_native_sha256=sha(dest),source_value_plan_sha256=sha(PLAN),
        full_native_binding_sha256=sha(BINDING),value_witness_sha256=sha(out/'VALUE_WITNESS.json'),
        gate_plan_sha256=sha(out/'NATIVE_GATE_PLAN.json'),operation_map_sha256=sha(out/'OPERATION_MAP.json.gz'),
        old_HMR_count=parent.measurements,new_HMR_count=candidate.measurements,
        local_parent_interval=[ENTRY,EXIT],local_candidate_interval=[mapping[ENTRY],mapping[EXIT]+len(exit)],
        native_resources=resources,exact_added_expected_Toffolis='4',exact_candidate_expected_Toffolis='5861/4',
        frozen_five_AND_release_unchanged=True,physical_allocation_and_whole_proof_pending=True,qualified=False)
    dump(out/'EMISSION_RECEIPT.json',emission)
    print(json.dumps({k:emission[k] for k in ('status','candidate_native_sha256','local_candidate_interval',
                     'exact_candidate_expected_Toffolis')},sort_keys=True),flush=True)
    return parent,candidate,mapping,origins,inserts,fresh_events,emission,plan,binding


def eval_formal(plan,values,full):
    result={}
    for p in plan['products']:
        result=xor(result,mul(xor(*[values[n] for n in p['A']]),xor(*[values[n] for n in p['B']])))
    for n in plan['affine_terms']:result=xor(result,{0:full} if n=='constant' else values[n])
    return result


def verify(out,parent,candidate,mapping,origins,inserts,fresh_events,emission,plan,binding,began):
    xs=np.arange(1,3133453,dtype=np.uint64);full=(1<<len(xs))-1
    frames=captures(parent,{ENTRY,EXIT},xs,formal=True,include_classical=True)
    assert frames[ENTRY]['q0']==frames[EXIT]['q0'] and frames[ENTRY]['q35']==frames[EXIT]['q35']
    assert not frames[EXIT]['q7'] and not frames[EXIT]['q10']
    dirty=dict(frames[EXIT]);dirty['q0']=dirty['q35'];dirty['q35']={}
    values={name:xor(*[({0:full} if q=='constant' else dirty[q]) for q in binding['desired_control_physical_parities'][name]])
            for name in plan['control_names']}
    assert all(set(v)<={0} for v in values.values())
    target=xor(eval_formal(plan['Q0'],values,full),mul(values['D9'],eval_formal(plan['Q1'],values,full)))
    assert target==frames[EXIT]['q0']
    a,b=mapping[ENTRY],mapping[EXIT]+len(inserts[EXIT])
    old=replay(frames[ENTRY],parent.operations[ENTRY:EXIT],list(range(ENTRY,EXIT)),parent,fresh_events,full)
    new=replay(frames[ENTRY],candidate.operations[a:b],origins[a:b],parent,fresh_events,full)
    assert all(old[0][q]==new[0][q] for q in parent.wires)
    assert old[1]==new[1] and old[2]==new[2]
    demands=[]
    for j,op in enumerate(candidate.operations[a:b]):
        operands=sum(1<<int(q[1:]) for q in set(op.arguments) if q.startswith('q') and q[1:].isdigit())
        demands.append(new[3][j]|new[3][j+1]|operands)
    assert max(m.bit_count() for m in new[3])<=43 and max(m.bit_count() for m in demands)<=43
    with gzip.open(ROOT/'root/q43_final_guarded_borrow_width_root_v1/ALL_INPUT_ALL_HMR_OCCUPANCY.json.gz','rt') as f:width=json.load(f)
    assert width['native_sha256']==PARENT_SHA and width['masks'][ENTRY:EXIT+1]==old[3]
    peakcuts=[i for i,m in enumerate(width['masks']) if m.bit_count()==44]
    assert len(peakcuts)==182 and all(ENTRY<=i<EXIT for i in peakcuts)
    dump_gz(out/'LOCAL_OCCUPANCY.json.gz',dict(notice=NOTICE,parent_sha256=PARENT_SHA,candidate_sha256=emission['candidate_native_sha256'],
             parent_start_cut=ENTRY,candidate_start_cut=a,parent_masks=old[3],candidate_masks=new[3],candidate_operation_operand_demand_masks=demands))
    report=dict(emission,status='LATE_FOUR_AND_FULL_NATIVE_LOCAL_VALUE_PHASE_ROTATION_OCCUPANCY_PASS',
        numerical_verification='AGENT_VERIFIED_ROOT_REPLAY_PENDING',full_legal_original_inputs=len(xs),
        every_original_HMR_formal=True,every_fresh_HMR_formal=True,formal_HMR_variables=parent.measurements+2,
        all_original_quantum_and_classical_endpoint_values_identical=True,complete_binary_phase_identical=True,
        every_intermediate_rotation_read_and_angle_identical=True,local_rotation_events=len(old[2]),
        helper_q7_exactly_zero_at_original_28240=True,all_four_original_native_products_retained_unmodified=True,
        quadratic_helper_feedback_precedes_original_28243_HMR=True,
        local_peak_nonzero_owners=max(m.bit_count() for m in new[3]),local_peak_operand_demand=max(m.bit_count() for m in demands),
        original_peak44_cuts_covered=182,original_peak44_windows_covered=22,
        local_occupancy_histogram=dict(sorted(Counter(m.bit_count() for m in new[3]).items())),
        local_occupancy_sha256=sha(out/'LOCAL_OCCUPANCY.json.gz'),physical_Q43_allocation_still_owed=True,
        seconds=time.monotonic()-began)
    dump(out/'REPORT.json',report)
    print(json.dumps({k:report[k] for k in ('status','candidate_native_sha256','full_legal_original_inputs',
          'exact_candidate_expected_Toffolis','local_peak_operand_demand','seconds')},sort_keys=True),flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--build-only',action='store_true');args=ap.parse_args();began=time.monotonic()
    args.out.mkdir(parents=True,exist_ok=False);built=build(args.out)
    if not args.build_only:verify(args.out,*built,began)


if __name__=='__main__':main()
