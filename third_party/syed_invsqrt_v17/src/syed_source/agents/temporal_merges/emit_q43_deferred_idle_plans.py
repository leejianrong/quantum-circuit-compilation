# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Emit nonoverlapping idle retirement/restoration plans and prove local phases.

Fresh retirement outcomes are held until restoration and repaid by Z. The
original circuit and its HMR events are otherwise retained exactly. The full
legal input domain and every formal original/fresh HMR are checked locally.
This does not claim global Q43 before all remaining peaks are handled.
"""
from pathlib import Path
from collections import Counter
from dataclasses import replace
from fractions import Fraction
import argparse
import gzip
import json
import sys
import time
import numpy as np
from temporal_core import NOTICE, Program, captures, advance, mul, sha, xor

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def product_lines(a,b,target):
    a,b=set(a),set(b)
    assert target not in a|b and a and b
    order=lambda q:int(q[1:])
    p=min(a,key=order)
    first=[f'CX {q} {p}' for q in sorted(a-{p},key=order)]
    if p in b:
        b.symmetric_difference_update(a-{p})
    q=min(b-{p},key=order)
    second=[f'CX {u} {q}' for u in sorted(b-{q},key=order)]
    return first+second+[f'CCX {p} {q} {target}']+second[::-1]+first[::-1]


def replay(initial,operations,origins,parent,fresh_events,full):
    state={q:dict(v) for q,v in initial.items()}
    state.update({b:{} for b in fresh_events})
    one={0:full};stack=[one];phase={};rotations=[];masks=[]
    def record():
        masks.append(sum(bool(state[f'q{i}']) << i for i in range(44)))
    record()
    for op,origin in zip(operations,origins):
        if op.kind=='PUSH_CONDITION':
            stack.append(stack[-1] if op.condition is None else mul(stack[-1],state[op.condition]))
        elif op.kind=='POP_CONDITION':
            stack.pop()
        else:
            if op.kind=='HMR':
                event=parent.operations[origin].event if origin is not None else fresh_events[op.arguments[1]]
                op=replace(op,event=event)
            guard=stack[-1] if op.condition is None else mul(stack[-1],state[op.condition])
            delta,rotation=advance(state,op,guard,one,formal=True)
            phase=xor(phase,delta)
            if rotation is not None:rotations.append(rotation)
        record()
    assert stack==[one]
    return state,phase,rotations,masks


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--cases',type=int,nargs='+',default=[143,100])
    args=ap.parse_args();began=time.monotonic()
    report_path=HERE/'q43_deferred_idle_recompute_v1/REPORT.json'
    screen=json.loads(report_path.read_text())
    native=ROOT/'root/combined1114_selective_qualification_v1/first/emitted/candidate.kmx'
    assert sha(native)==screen['native_sha256']
    text=native.read_text();parent=Program(text)
    plans=[r for r in screen['records'] if r['case_id'] in args.cases]
    assert len(plans)==len(set(args.cases))
    plans.sort(key=lambda r:r['start_cut'])
    assert all(a['end_cut']<=b['start_cut'] for a,b in zip(plans,plans[1:]))
    fresh=max(int(q[1:]) for q in parent.wires if q.startswith('b'))+1
    inserts={};fresh_events={};literal=[]
    for j,plan in enumerate(plans):
        q=plan['owner'];a,b=plan['start_cut'],plan['end_cut'];outcome=f'b{fresh+j}'
        fresh_events[outcome]=parent.measurements+j
        assert all(q not in o.arguments for o in parent.operations[a:b])
        assert 'paid_products' in plan['restoration']
        entry=[f'HMR {q} {outcome}'];exit=[]
        for product in plan['restoration']['products']:
            exit+=product_lines(product['A'],product['B'],q)
        for name in plan['restoration']['affine_offset']:
            exit.append(f'X {q}' if name=='constant' else f'CX {name} {q}')
        exit.append(f'Z {q} if {outcome}')
        inserts.setdefault(a,[]).extend(entry)
        inserts.setdefault(b,[]).extend(exit)
        literal.append(dict(case_id=plan['case_id'],owner=q,retire_cut=a,restore_cut=b,
                            added_classical_owner=outcome,entry_gates=entry,exit_gates=exit,
                            exact_added_expected_Toffolis=str(plan['restoration']['paid_products']),
                            covered_native_peak_cuts=plan['covered_peak_cuts']))
    by_line={op.line:i for i,op in enumerate(parent.operations)}
    lines=['# '+NOTICE];origin=[];mapping={};count=0
    for line_number,line in enumerate(text.splitlines(),1):
        i=by_line.get(line_number)
        if i is None:
            lines.append(line);continue
        mapping[i]=count
        added=inserts.get(i,[]);lines+=added;origin += [None]*len(added);count+=len(added)
        lines.append(line);origin.append(i);count+=1
    mapping[len(parent.operations)]=count
    changed='\n'.join(lines)+'\n';candidate=Program(changed)
    assert len(candidate.operations)==count
    assert candidate.measurements==parent.measurements+len(plans)
    xs=np.arange(1,3133453,dtype=np.uint64);full=(1<<len(xs))-1
    cuts={c for p in plans for c in (p['start_cut'],p['end_cut'])}
    frames=captures(parent,cuts,xs,formal=True,include_classical=True)
    for plan in plans:
        a,b,q=plan['start_cut'],plan['end_cut'],plan['owner']
        assert frames[a][q]==frames[b][q]
        p=plan['restoration'];value={}
        for product in p['products']:
            aa=xor(*[frames[b][u] for u in product['A']])
            bb=xor(*[frames[b][u] for u in product['B']])
            value=xor(value,mul(aa,bb))
        value=xor(value,*[({0:full} if u=='constant' else frames[b][u]) for u in p['affine_offset']])
        assert value==frames[b][q],('Full-domain restoration failure',plan['case_id'])
    a,b=plans[0]['start_cut'],plans[-1]['end_cut']
    # Include the final restoration, which is inserted before old operation b.
    ca,cb=mapping[a],mapping[b]+len(inserts[b])
    old=replay(frames[a],parent.operations[a:b],list(range(a,b)),parent,fresh_events,full)
    new=replay(frames[a],candidate.operations[ca:cb],origin[ca:cb],parent,fresh_events,full)
    assert all(old[0][q]==new[0][q] for q in parent.wires)
    assert old[1]==new[1] and old[2]==new[2]
    args.out.mkdir(exist_ok=False)
    dest=args.out/'candidate_text.kmx';dest.write_text(changed)
    with gzip.open(args.out/'OPERATION_MAP.json.gz','wt',compresslevel=9) as f:
        json.dump(dict(notice=NOTICE,parent_sha256=sha(native),candidate_sha256=sha(dest),old_cut_to_new_cut=mapping,
                       new_operation_origin=origin),f,separators=(',',':'))
    with gzip.open(args.out/'LOCAL_OCCUPANCY.json.gz','wt',compresslevel=9) as f:
        json.dump(dict(notice=NOTICE,parent_start_cut=a,parent_masks=old[3],candidate_start_cut=ca,candidate_masks=new[3]),f,separators=(',',':'))
    engine=ROOT/'incumbent_sources/frozen_source/fusion/runtime/work/c10/narrow/checkpoint002/cleanroom/baseline_stage97'
    sys.path.insert(0,str(engine/'tests'));sys.path.insert(0,str(engine/'engine'))
    from fourier_resource_expectation import exact_expectation
    resources=exact_expectation(changed)
    added=sum(p['restoration']['paid_products'] for p in plans)
    assert Fraction(resources['mean']['toffoli_like'])==Fraction(22857,16)+added
    assert resources['mean']['T']=='1' and resources['mean']['generic_rotations']=='34'
    per_interval=[]
    for p in plans:
        start,end=p['start_cut'],p['end_cut'];s=mapping[start];t=mapping[end]+len(inserts[end])
        start_mask=new[3][s-ca];end_mask=new[3][t-ca]
        hist=Counter(v.bit_count() for v in new[3][s-ca:t-ca+1])
        assert max(hist)<=43
        per_interval.append(dict(case_id=p['case_id'],candidate_interval=[s,t],peak_nonzero_owners=max(hist),
                                 histogram=dict(sorted(hist.items())),start_mask=start_mask,end_mask=end_mask))
    report=dict(notice=NOTICE,status='DEFERRED_IDLE_PLANS_EMITTED_EXACT_FULL_DOMAIN_LOCAL_PASS',
                numerical_verification='AGENT_VERIFIED_ROOT_REPLAY_PENDING',qualified=False,
                source_sha256=sha(__file__),parent_native_sha256=sha(native),candidate_native_sha256=sha(dest),
                input_screen_sha256=sha(report_path),full_legal_original_inputs=len(xs),all_HMR_symbolic=True,
                fresh_HMR_event_map=fresh_events,plans=literal,per_interval_occupancy=per_interval,
                exact_added_expected_Toffolis=str(added),exact_candidate_expected_Toffolis=resources['mean']['toffoli_like'],
                original_quantum_and_classical_values_identical_at_endpoint=True,complete_local_phase_identical=True,
                original_rotation_read_values_and_angles_preserved=True,local_rotation_events=len(old[2]),
                total_current_native_peak_cuts_covered=sum(p['covered_peak_cuts'] for p in plans),
                native_resources=resources,whole_native_Q=44,remaining_peaks_untouched=True,
                full_unchanged_official_proof_and_global_Q43_recoloring_pending=True,
                operation_map_sha256=sha(args.out/'OPERATION_MAP.json.gz'),
                local_occupancy_sha256=sha(args.out/'LOCAL_OCCUPANCY.json.gz'),seconds=time.monotonic()-began)
    (args.out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('native_resources','plans')},indent=2))


if __name__=='__main__':main()
