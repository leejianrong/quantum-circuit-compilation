# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Retire v9 across the first product and rebuild it with four native ANDs.

The q33=D8 HMR moves from4820 to4931 across operations disjoint from q33
and its outcome. The new v9 HMR is at3796; q19 has no intervening reference
before its restoration at4881. The already-paid A5 helper q29 is retained.
Three new product helpers are erased in reverse order using immediate free
quadratic feedback. The restored v9 repays its own fresh HMR phase by Z.
The entire changed interval is checked on all3133452 legal inputs and every
formal old/new HMR. Whole-circuit Q43 is not claimed by this local patch.
"""
from pathlib import Path
from collections import Counter
from fractions import Fraction
import argparse
import gzip
import json
import sys
import time
import numpy as np
from temporal_core import NOTICE, Program, captures, mul, sha, xor
from emit_q43_deferred_idle_plans import product_lines, replay

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
REFERENCE_SHA='23f2ecd3f88f4b72d7657abae0027511d64ec0201d4985e004608e15b11144c3'
PARENT_SHA='501f1d90c3a82c45c6a60d6ec478bd89c91ebc3f72e847cc56f8d4182a014e43'
PHYSICAL=dict(v7='q17',v8='q18',D8='q33',D9='q31',D10='q20',D11='q26',D12='q27',
              g_A5='q29',H0='q35',H1='q28',J='q36',v9='q19')
FORM=dict(H0=dict(A=['v7'],B=['D8']),H1=dict(A=['v8'],B=['D8']),
          J=dict(A=['D8','D9','D11','D12','g_A5','H0','H1'],B=['D10','H0']),
          C=['v8','D8','D9','D10','D12','g_A5'],D=['D9','D11'],
          E=['v8','D8','D9','D11','D12','g_A5','H1'])


def parity_value(values,names):return xor(*[values[name] for name in names])


def cleanup_lines(A,B,target,outcome):
    lines=[f'HMR {target} {outcome}']
    for line in product_lines(A,B,target):
        terms=line.split()
        if terms[0]=='CCX':
            assert terms[-1]==target
            line=f'CZ {terms[1]} {terms[2]} if {outcome}'
        lines.append(line)
    return lines


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--native',type=Path,default=ROOT/'root/q43_phase_and_late_width_v1/candidate_text.kmx')
    args=ap.parse_args();began=time.monotonic()
    assert sha(args.native)==PARENT_SHA
    reference_path=HERE/'q43_integrated_width_base_v1/candidate_text.kmx'
    assert sha(reference_path)==REFERENCE_SHA
    parent_text=args.native.read_text();parent=Program(parent_text)
    reference=Program(reference_path.read_text())
    signature=lambda o:(o.kind,o.arguments,o.condition,o.event,o.half_turns)
    assert list(map(signature,parent.operations[:8530]))==list(map(signature,reference.operations[:8530]))
    ops=parent.operations
    assert (ops[4820].kind,ops[4820].arguments)==('HMR',('q33','b612'))
    assert all('q33' not in o.arguments and 'b612' not in o.arguments and o.condition!='b612'
               for o in ops[4821:4931])
    assert all('q19' not in o.arguments for o in ops[3796:4885])
    depth=0;depths=[]
    for o in ops:
        depths.append(depth);depth+=(o.kind=='PUSH_CONDITION')-(o.kind=='POP_CONDITION')
    assert depth==0 and all(depths[c]==0 for c in (3796,4820,4881,4931,4933))
    fresh=max(int(q[1:]) for q in parent.wires if q.startswith('b'))+1
    outcome={name:f'b{fresh+j}' for j,name in enumerate(('v9','J','H1','H0'))}
    fresh_events={outcome[name]:parent.measurements+j for j,name in enumerate(('v9','J','H1','H0'))}
    physical=lambda names:[PHYSICAL[n] for n in names]
    decoder=[]
    for name in ('H0','H1','J'):
        decoder+=product_lines(physical(FORM[name]['A']),physical(FORM[name]['B']),PHYSICAL[name])
    for name in FORM['D']:decoder.append(f'CX {PHYSICAL[name]} {PHYSICAL["J"]}')
    decoder+=product_lines(physical(FORM['C']),[PHYSICAL['J']],PHYSICAL['v9'])
    for name in reversed(FORM['D']):decoder.append(f'CX {PHYSICAL[name]} {PHYSICAL["J"]}')
    for name in FORM['E']:decoder.append(f'CX {PHYSICAL[name]} {PHYSICAL["v9"]}')
    decoder.append(f'Z {PHYSICAL["v9"]} if {outcome["v9"]}')
    for name in ('J','H1','H0'):
        decoder+=cleanup_lines(physical(FORM[name]['A']),physical(FORM[name]['B']),PHYSICAL[name],outcome[name])
    assert sum(line.startswith('CCX ') for line in decoder)==4
    assert not any(line.startswith('CCZ ') for line in decoder)
    inserts={3796:[(f'HMR q19 {outcome["v9"]}',None)],
             4881:[(line,None) for line in decoder],4931:[('HMR q33 b612',4820)]}
    skipped={4820};by_line={o.line:i for i,o in enumerate(ops)}
    lines=['# '+NOTICE];origins=[];mapping={};count=0
    for line_number,line in enumerate(parent_text.splitlines(),1):
        i=by_line.get(line_number)
        if i is None:lines.append(line);continue
        mapping[i]=count
        for added,origin in inserts.get(i,[]):
            lines.append(added);origins.append(origin);count+=1
        if i not in skipped:
            lines.append(line);origins.append(i);count+=1
    mapping[len(ops)]=count
    text='\n'.join(lines)+'\n';candidate=Program(text)
    assert len(candidate.operations)==len(origins)==count
    assert candidate.measurements==parent.measurements+4
    assert candidate.registers==parent.registers
    assert [signature(o) for o in candidate.operations[:3796]]==[signature(o) for o in ops[:3796]]
    xs=np.arange(1,3133453,dtype=np.uint64);full=(1<<len(xs))-1
    frames=captures(parent,{3796,4820,4881,4933},xs,formal=True,include_classical=True)
    assert frames[3796]['q19']==frames[4881]['q19']
    assert all(not frames[4881][PHYSICAL[name]] for name in ('H0','H1','J'))
    values={name:frames[4881][q] for name,q in PHYSICAL.items()}
    values['D8']=frames[4820]['q33']
    assert values['g_A5']==mul(xor(values['D9'],values['D10'],values['D11']),values['D12'])
    for name in ('H0','H1','J'):
        values[name]=mul(parity_value(values,FORM[name]['A']),parity_value(values,FORM[name]['B']))
    restored=xor(mul(parity_value(values,FORM['C']),xor(values['J'],parity_value(values,FORM['D']))),
                 parity_value(values,FORM['E']))
    assert restored==frames[4881]['q19'],'FULL_DOMAIN_V9_IDENTITY_FAILED'
    a,b=3796,4933;ca,cb=mapping[a],mapping[b]
    old=replay(frames[a],ops[a:b],list(range(a,b)),parent,fresh_events,full)
    new=replay(frames[a],candidate.operations[ca:cb],origins[ca:cb],parent,fresh_events,full)
    assert all(old[0][q]==new[0][q] for q in parent.wires)
    assert old[1]==new[1] and old[2]==new[2]
    assert not old[2], 'Expected no rotations in the changed interval'
    assert max(m.bit_count() for m in new[3])<=43
    args.out.mkdir(exist_ok=False)
    destination=args.out/'candidate_text.kmx';destination.write_text(text)
    with gzip.open(args.out/'OPERATION_MAP.json.gz','wt',compresslevel=9) as f:
        json.dump(dict(notice=NOTICE,parent_sha256=PARENT_SHA,candidate_sha256=sha(destination),
                       old_cut_to_new_cut=mapping,new_operation_origin=origins),f,separators=(',',':'))
    with gzip.open(args.out/'LOCAL_OCCUPANCY.json.gz','wt',compresslevel=9) as f:
        json.dump(dict(notice=NOTICE,parent_start_cut=a,parent_masks=old[3],candidate_start_cut=ca,
                       candidate_masks=new[3]),f,separators=(',',':'))
    engine=ROOT/'incumbent_sources/frozen_source/fusion/runtime/work/c10/narrow/checkpoint002/cleanroom/baseline_stage97'
    sys.path.insert(0,str(engine/'tests'));sys.path.insert(0,str(engine/'engine'))
    from fourier_resource_expectation import exact_expectation
    resources=exact_expectation(text)
    assert Fraction(resources['mean']['toffoli_like'])==Fraction(11605,8)
    assert resources['mean']['T']=='1' and resources['mean']['generic_rotations']=='34'
    report=dict(notice=NOTICE,status='FIRST_PRODUCT_V9_RETIREMENT_NATIVE_EMITTED_LOCAL_FULL_DOMAIN_PASS',
        numerical_verification='AGENT_VERIFIED_ROOT_REPLAY_PENDING',qualified=False,
        source_sha256=sha(__file__),helper_source_sha256=sha(HERE/'emit_q43_deferred_idle_plans.py'),
        parent_native_sha256=PARENT_SHA,research_reference_sha256=REFERENCE_SHA,
        unchanged_prefix_operation_count=8530,candidate_native_sha256=sha(destination),
        component_witness_receipt_sha256=sha(HERE/'q43_v9_two_helper_D8_v1/REPORT.json'),
        full_legal_original_inputs=len(xs),all_old_and_new_HMR_symbolic=True,
        old_interval=[a,b],candidate_interval=[ca,cb],physical_owner_binding=PHYSICAL,formulas=FORM,
        fresh_outcomes=outcome,fresh_HMR_event_map=fresh_events,
        original_D8_measurement_preserved=dict(old_operation=4820,old_event=ops[4820].event,
            classical_owner='b612',new_original_frame_cut=4931,old_owner_assignment_at4932_unchanged=True),
        retirement_gate=f'HMR q19 {outcome["v9"]}',decoder_and_cleanup_gates=decoder,
        exact_added_expected_Toffolis='4',added_Toffoli_firing_probabilities=['1']*4,
        exact_candidate_expected_Toffolis='11605/8',T='1',rotations='34',
        all44_old_quantum_and_all_old_classical_endpoint_values_identical=True,
        complete_local_binary_phase_identical=True,intermediate_rotation_obligations=0,
        parent_local_peak=max(m.bit_count() for m in old[3]),candidate_local_peak=max(m.bit_count() for m in new[3]),
        parent_peak44_cuts_removed=sum(m.bit_count()==44 for m in old[3]),
        candidate_local_occupancy_histogram=dict(sorted(Counter(m.bit_count() for m in new[3]).items())),
        global_Q43_not_yet_claimed=True,unchanged_official_full_proof_and_rebuilds_pending=True,
        native_resources=resources,operation_map_sha256=sha(args.out/'OPERATION_MAP.json.gz'),
        occupancy_sha256=sha(args.out/'LOCAL_OCCUPANCY.json.gz'),seconds=time.monotonic()-began)
    (args.out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('decoder_and_cleanup_gates','native_resources')},indent=2))


if __name__=='__main__':main()
