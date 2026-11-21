# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Emit older-carry conditional reconstruction and undo eight paid fallbacks.

Eight original HMR events move earlier. Each old carry is rebuilt with one
actual AND in an existing fair half-probability branch and erased by a fresh
HMR with its full literal quadratic correction. The original HMR debt is
preserved through its original native feedback. Reversing seven half-cost
fallbacks and the quarter-cost case23 pays for all but one quarter of a gate.
"""
from collections import Counter
from dataclasses import replace
from fractions import Fraction
import argparse
import gzip
import json
from pathlib import Path
import shlex
import time

import emit_later_bank_guard_sharing as r
from scan_early_conditional_carry_borrows import PARENT, PARENT_SHA, PEAKS

HERE=Path(__file__).resolve().parent
INDEX=HERE/'early_conditional_carry_borrows_v1/INDEX.json'
HALVES=r.BASE/'root/q43_first_bank_and_carry_half_v1/REPORT.json'
QUARTER=r.BASE/'agents/conditional_phase/Q43_QUARTER_CARRY_CASE23_CONTRACT.json'


def bits(v):
    while v:
        b=v&-v;yield b.bit_length()-1;v^=b


def one_and(plan):
    q=plan['owner'];a,b=plan['feedback']['factor_masks']
    p=next(bits(a&~b));s=next(bits(b&~a))
    pre=[f'CX q{i} q{p}' for i in bits(a^(1<<p))]+[f'CX q{i} q{s}' for i in bits(b^(1<<s))]
    out=pre+[f'CCX q{p} q{s} {q}']+list(reversed(pre))
    for m in plan['feedback']['linear_remainder']:
        out.append(f'X {q}' if m==0 else f'CX q{m.bit_length()-1} {q}')
    return out


def free_feedback(plan,bit):
    out=[]
    for m in plan['feedback']['polynomial']:
        qs=[f'q{i}' for i in bits(m)]
        out.append(' '.join([('NEG','Z','CZ')[len(qs)],*qs,'if',bit]))
    return out


def phase_value(plan,state,n):
    ans={};one={0:(1<<n)-1}
    for m in plan['feedback']['polynomial']:
        z=one
        for i in bits(m):z=r.pm(z,state[f'q{i}'])
        ans=r.px(ans,z)
    return ans


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--full-local-proof',action='store_true')
    args=ap.parse_args();began=time.monotonic()
    assert not args.out.exists();args.out.mkdir(parents=True)
    assert r.sha(PARENT)==PARENT_SHA
    assert r.sha(HALVES)=='1b8f32e5e331e2dcce47b3041f2681a846a754f068ce3115aeb2fe55fa546e8f'
    assert r.sha(QUARTER)=='2fa0a0ec726da539db940746da4e09e9e85f21ef2418b6cc433fcf6953d18d90'
    indexed=json.loads(INDEX.read_text());assert indexed['parent_sha256']==PARENT_SHA
    plans=indexed['plans'];assert len(plans)==8
    text=PARENT.read_text();parent=r.Program(text);actual=[r.literal(o) for o in parent.operations]
    original=r.Program(r.ORIGINAL.read_text());assert r.sha(r.ORIGINAL)==r.ORIGINAL_SHA
    old=[r.literal(o) for o in original.operations]
    inserts={};changes={};skip=set();undo=[];dead_bits=[]
    fresh=1+max(int(q[1:]) for q in parent.wires if q.startswith('b'))
    new_events={};extra=0
    def insert(at,lines,origins=None):
        if origins is None:origins=[None]*len(lines)
        inserts.setdefault(at,[]).extend(zip(lines,origins))
    def alter(lo,hi,lines,origins=None):
        assert not set(range(lo,hi))&skip
        if origins is None:origins=[None]*len(lines)
        changes[lo]=list(zip(lines,origins));skip.update(range(lo,hi))
    def match(lines):
        hits=[i for i in range(len(actual)-len(lines)+1) if actual[i:i+len(lines)]==lines]
        assert len(hits)==1,(lines,hits)
        return hits[0]
    for number,p in enumerate(plans):
        q=p['owner'];h=p['old_HMR'];start=p['start'];block,end=p['reconstruction_block']
        assert parent.operations[h].kind=='HMR' and parent.operations[h].arguments[0]==q
        assert parent.operations[block-1].kind=='HMR' and parent.operations[block-1].arguments[1]==p['reconstruction_guard']
        assert parent.operations[block-1].condition is None
        saved=f'b{fresh+2*number}';scratch=f'b{fresh+2*number+1}'
        p['saved_outcome_owner']=saved;p['cleanup_outcome_owner']=scratch
        insert(start,[f'HMR {q} {saved}'],[h])
        insert(block+1,one_and(p))
        erase=[f'HMR {q} {scratch}',*free_feedback(p,scratch),f'BIT_STORE0 {scratch}']
        insert(end-1,erase)
        new_events[scratch]=parent.measurements+extra;extra+=1
        alter(h,h+1,[f'BIT_STORE0 {p["old_classical_owner"]}',f'BIT_INVERT {p["old_classical_owner"]} if {saved}',f'BIT_STORE0 {saved}'])
        p['preparation_lines']=one_and(p);p['free_cleanup_lines']=erase
        p['exact_preparation_guard_probability']='1/2'
    halfplans=json.loads(HALVES.read_text())['plans']
    for case in range(23,31):
        hp=next(p for p in halfplans if p['case_id']==case)
        pattern=hp['replacement'].copy()
        if case==23:
            pattern.remove('CCZ q1 q2 q16 if b1')
        lo=match(pattern);hi=lo+len(pattern)
        aa,bb=hp['original_integrated_interval'];replacement=old[aa:bb]
        origins=[]
        for o,line in zip(original.operations[aa:bb],replacement):
            if o.kind=='HMR':
                q,b=o.arguments
                want=f'HMR {q} {hp["new_classical_owner"]}' if q==hp['retired_owner'] else line
                hits=[i for i in range(lo,hi) if actual[i]==want]
                assert len(hits)==1,(case,want,hits);origins.append(hits[0])
            else:origins.append(None)
        enclosing=plans[case-23]
        assert enclosing['start']<=lo<hi<enclosing['reconstruction_block'][0]
        alter(lo,hi,replacement,origins)
        dead_bits.append(hp['new_classical_owner'])
        assert all(hp['new_classical_owner'] not in (set(o.arguments)|{o.condition}) for o in parent.operations[hi:])
        undo.append(dict(case=case,parent_interval=[lo,hi],restored_integrated_interval=[aa,bb],
                         saved_expected_Toffolis='1/4' if case==23 else '1/2',old_temporary=hp['new_classical_owner']))
    contract=json.loads(QUARTER.read_text())
    complement='b5020'
    paid=[f'BIT_STORE1 {complement}',f'BIT_INVERT {complement} if b280','PUSH_CONDITION if b911',f'PUSH_CONDITION if {complement}',
          *contract['paid_quantum_gates'],'POP_CONDITION','POP_CONDITION',f'BIT_STORE0 {complement}']
    lo=match(paid);alter(lo,lo+len(paid),[]);quarter_removed_paid=[lo,lo+len(paid)]
    free=contract['free_gates'];lo=match(free);alter(lo,lo+len(free),[]);quarter_removed_free=[lo,lo+len(free)]
    # Preserve every metadata declaration and every unaffected native line.
    lines=['# '+r.NOTICE];origins=[];metadata={'REGISTER','APPEND_TO_REGISTER','INFO_TAG','DEBUG_PRINT'};index=0
    parent_to_output={}
    for line in text.splitlines():
        tokens=shlex.split(line,comments=True)
        if not tokens or tokens[0] in metadata:
            lines.append(line);continue
        parent_to_output[index]=len(origins)
        for s,origin in inserts.get(index,[]):lines.append(s);origins.append(origin)
        if index in changes:
            for s,origin in changes[index]:lines.append(s);origins.append(origin)
        elif index not in skip:
            lines.append(line);origins.append(index)
        index+=1
    assert index==len(parent.operations)
    parent_to_output[index]=len(origins)
    changed='\n'.join(lines)+'\n';candidate=r.Program(changed)
    assert len(candidate.operations)==len(origins)
    assert candidate.measurements==parent.measurements+8 and candidate.registers==parent.registers
    native=args.out/'candidate_text.kmx';native.write_text(changed)
    lo=min(p['start'] for p in plans);hi=max(p['old_HMR']+1 for p in plans)
    alo,ahi=parent_to_output[lo],parent_to_output[hi]
    proof=None
    if args.full_local_proof:
        checkpoints=sorted({lo,*[p['start'] for p in plans]})
        prefix=r.replay(parent.operations[:checkpoints[-1]],r.initial_state(parent),captures=checkpoints)
        frames=prefix['captures'];state=frames[lo]
        for p in plans:
            assert phase_value(p,frames[p['start']],r.N)==frames[p['start']][p['owner']],('actual carry mismatch',p['id'])
        before=r.replay(parent.operations[lo:hi],state,phase=True,masks=True)
        segment=[];event_map=[]
        for pos,o in enumerate(candidate.operations[alo:ahi],alo):
            if o.kind=='HMR':
                origin=origins[pos]
                if origin is None:
                    event=new_events[o.arguments[1]]
                else:
                    assert parent.operations[origin].kind=='HMR'
                    event=parent.operations[origin].event
                event_map.append(dict(output_operation=pos,parent_operation=origin,formal_event=event))
                o=replace(o,event=event)
            segment.append(o)
        for q in candidate.wires:state.setdefault(q,{})
        after=r.replay(segment,state,phase=True,masks=True)
        assert before['phase']==after['phase'],'binary phase mismatch'
        assert before['rotations']==after['rotations'],'rotation mismatch'
        quantum=[f'q{i}' for i in range(44)]
        for q in quantum:assert before['state'][q]==after['state'][q],('quantum mismatch',q)
        live_classical={q for o in parent.operations[hi:] for q in (*o.arguments,o.condition) if isinstance(q,str) and q.startswith('b')}
        for q in live_classical:assert before['state'][q]==after['state'][q],('continuation classical mismatch',q)
        assert not set(dead_bits)&live_classical
        for p in plans:
            assert not after['state'][p['saved_outcome_owner']] and not after['state'][p['cleanup_outcome_owner']]
        hist=Counter(m.bit_count() for m in after['masks'])
        assert max(hist)<=43,('remaining peak in replaced early packet interval',hist)
        proof=dict(status='FULL_3133452_INPUT_ALL_HMR_LOCAL_VALUE_PHASE_WIDTH_PASS',original_inputs=r.N,
                   all_original_HMR=True,extra_independent_HMR=8,actual_one_AND_carry_identities_checked=8,
                   parent_interval=[lo,hi],output_interval=[alo,ahi],output_width_histogram=dict(sorted(hist.items())),
                   maximum_width_in_component=max(hist),every_quantum_owner_compared=True,
                   continuation_live_classical_owners_compared=len(live_classical),unused_removed_temporaries=dead_bits,
                   extra_classical_owners_zero_at_exit=True,formal_HMR_event_map=event_map,
                   global_Q43_claimed=False)
        (args.out/'LOCAL_PROOF.json').write_text(json.dumps(dict(notice=r.NOTICE,**proof),indent=2)+'\n')
    extra_cost=8*Fraction(1,2)-7*Fraction(1,2)-Fraction(1,4)
    result=dict(notice=r.NOTICE,status='EARLY_CONDITIONAL_CARRY_BORROWS_EMITTED_FULL_NATIVE_QUALIFICATION_PENDING',
                parent_native=str(PARENT.relative_to(r.BASE)),parent_sha256=PARENT_SHA,parent_cost='5837/4',
                candidate_native_sha256=r.sha(native),source_sha256=r.sha(Path(__file__)),
                plans=plans,undone_fallbacks=undo,quarter_removed_paid=quarter_removed_paid,quarter_removed_free=quarter_removed_free,
                actual_added_ANDs=8,exact_added_expected_Toffolis='4',exact_removed_expected_Toffolis='15/4',
                net_expected_Toffolis=str(extra_cost),modelled_total=str(Fraction(5837,4)+extra_cost),
                modelled_remaining_early_peak_windows=[p for i,p in enumerate(PEAKS) if i not in indexed['union_peak_ids']],
                additional_peak_windows_covered=len(indexed['union_peak_ids']),additional_peak_cuts_covered=sum(PEAKS[i][1]-PEAKS[i][0] for i in indexed['union_peak_ids']),
                T_model=1,rotation_model=34,extra_HMR=8,local_proof=None if proof is None else {k:v for k,v in proof.items() if k!='formal_HMR_event_map'},
                global_Q43_claimed=False,seconds=time.monotonic()-began,
                bindings={str(p.relative_to(r.BASE)):r.sha(p) for p in [INDEX,HALVES,QUARTER,r.ORIGINAL,Path(__file__),HERE/'scan_early_conditional_carry_borrows.py']})
    (args.out/'REPORT.json').write_text(json.dumps(result,indent=2)+'\n')
    (args.out/'OPERATION_MAP.json.gz').write_bytes(gzip.compress((json.dumps(dict(notice=r.NOTICE,parent_to_output=parent_to_output,output_origins=origins),separators=(',',':'))+'\n').encode(),mtime=0))
    print(json.dumps({k:v for k,v in result.items() if k not in ('plans','local_proof','bindings')},indent=2),flush=True)


if __name__=='__main__':main()
