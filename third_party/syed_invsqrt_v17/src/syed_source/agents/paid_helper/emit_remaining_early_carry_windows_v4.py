# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Five early width repairs with reused native products and merged debts.

The two-product carry's first helper is immediately erased. Its reconstructed
value is measured later, and this outcome XORs with the original early HMR
outcome for their identical unchanged function. The existing final cleanup
then corrects both debts and still fires with probability1/2. There is no
extra retained quantum helper or inner paid phase. The paired net cost is1/2.
The first two repairs retire an older one-product carry. Their cubic debt is
paid only when a later native cleanup guard is zero; when that guard is one,
the native product already exists and pays the debt with free CZs. These two
repairs cost1/4 each. The final carry is applied directly to q0, eliminating
its temporary birth and HMR. One fair-guarded CCZ supplies its old phase
interaction. With the paired1/2 and final1/2, total3/2.
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

HERE=Path(__file__).resolve().parent
PARENT=r.BASE/'agents/temporal_merges/q43_long_second_delayed_q21_native_v1/candidate_text.kmx'
PARENT_SHA='0e4a525f98bc492ccfb5e05d04983eabc3bbd036e26e77a9bb244aabb77421da'
HALVES=r.BASE/'root/q43_first_bank_and_carry_half_v1/REPORT.json'


def product(a,b):
    ans=set()
    for x in a:
        for y in b:
            z=x|y
            if z in ans:ans.remove(z)
            else:ans.add(z)
    return ans


def phase_lines(op,erased,changed,f):
    z={0}
    for q in op.arguments:
        if q==erased:v=f
        elif q==changed:v={1<<int(q[1:])}^f
        else:v={1<<int(q[1:])}
        z=product(z,v)
    assert all(m.bit_count()<=3 for m in z)
    lines=[]
    for m in sorted(z):
        qs=[f'q{k}' for k in range(44) if m>>k&1]
        row=[('NEG','Z','CZ','CCZ')[len(qs)],*qs]
        if op.condition:row+=['if',op.condition]
        lines.append(' '.join(row))
    return lines


def continuation_live_classical(ops,start):
    """Conservative first-read liveness; only unconditional writes kill."""
    live=set();defined=set();depth=0;kill_receipts={}
    for i,o in enumerate(ops[start:],start):
        dest=None
        if o.kind=='HMR':dest=o.arguments[1]
        elif o.kind in ('BIT_STORE0','BIT_STORE1'):dest=o.arguments[0]
        reads={q for q in o.arguments if q.startswith('b') and q!=dest}
        if o.condition is not None:reads.add(o.condition)
        live.update(q for q in reads if q not in defined)
        if dest is not None and depth==0 and o.condition is None:
            if dest not in defined and dest not in live:kill_receipts[dest]=i
            defined.add(dest)
        if o.kind=='PUSH_CONDITION':depth+=1
        elif o.kind=='POP_CONDITION':depth-=1
        assert depth>=0
    assert depth==0
    return live,kill_receipts


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--full-local-proof',action='store_true');args=ap.parse_args();began=time.monotonic()
    assert not args.out.exists();args.out.mkdir(parents=True);assert r.sha(PARENT)==PARENT_SHA
    text=PARENT.read_text();parent=r.Program(text);ops=parent.operations;actual=[r.literal(o) for o in ops]
    inserts={};changes={};skipped=set();extra_events={};extra_count=0;dead_bits=[]
    def expect(i,lines):assert actual[i:i+len(lines)]==lines,(i,actual[i:i+len(lines)],lines)
    def insert(i,lines,origins=None):
        inserts.setdefault(i,[]).extend(zip(lines,[None]*len(lines) if origins is None else origins))
    def alter(lo,hi,lines,origins=None):
        assert not skipped&set(range(lo,hi));skipped.update(range(lo,hi))
        changes[lo]=list(zip(lines,[None]*len(lines) if origins is None else origins))
    def extra(bit):
        nonlocal extra_count
        extra_events[bit]=parent.measurements+extra_count;extra_count+=1
    def match(lines):
        hits=[i for i in range(len(actual)-len(lines)+1) if actual[i:i+len(lines)]==lines]
        assert len(hits)==1,(lines,hits);return hits[0]
    assert not any(f'b{k}' in parent.wires for k in range(9000,9032))
    # The first two scopes have an actual quadratic carry at their live entry.
    single_specs=[dict(start=11013,end=11074,moved=11072,hmr=11073,owner='q8',target='q12',
                       f=[1<<10,(1<<11)|(1<<9)],bit='b9000',peaks=[[11040,11046]],
                       cubic='CCZ q9 q11 q40 if b1',debt_guard='b889',later_guard='b302',complement='b9010',
                       paid_cut=11161,free_cut=11171,native_product_owner='q7',second_factor_owner='q9',third_factor_owner='q40'),
                  dict(start=11318,end=11379,moved=11377,hmr=11378,owner='q7',target='q12',
                       f=[1<<10,(1<<11)|(1<<40)],bit='b9001',peaks=[[11345,11351]],
                       cubic='CCZ q11 q40 q41 if b1',debt_guard='b900',later_guard='b291',complement='b9011',
                       paid_cut=11466,free_cut=11476,native_product_owner='q26',second_factor_owner='q40',third_factor_owner='q41')]
    for p in single_specs:
        q=p['owner'];a=p['target'];h=p['hmr'];j=p['moved'];f=set(p['f']);bit=p['bit']
        expect(j,[f'CX {q} {a}',f'HMR {q} {ops[h].arguments[1]}'])
        body=[actual[j],f'HMR {q} {bit}'];origins=[j,h]
        for i in range(p['start'],h+1):
            o=ops[i]
            if i==j:continue
            if i==h:
                lines=[f'BIT_STORE0 {o.arguments[1]}',f'BIT_INVERT {o.arguments[1]} if {bit}',f'BIT_STORE0 {bit}']
                body+=lines;origins +=[None]*len(lines)
            elif o.kind in ('Z','CZ','CCZ') and ({q,a}&set(o.arguments)):
                lines=phase_lines(o,q,a if i<j else None,f)
                if p['cubic'] in lines:
                    lines.remove(p['cubic']);p['removed_cubic_parent_operation']=i
                body+=lines;origins +=[None]*len(lines)
            else:body.append(actual[i]);origins.append(i)
        alter(p['start'],p['end'],body,origins)
        assert 'removed_cubic_parent_operation' in p
        p['replacement']=body;p['origins']=origins;p['exact_added_expected_Toffolis']='1/4'
        B=p['second_factor_owner'];C=p['third_factor_owner'];helper=p['native_product_owner']
        rbit=p['debt_guard'];z=p['later_guard'];comp=p['complement']
        expect(p['paid_cut'],[f'PUSH_CONDITION if {z}'])
        expect(p['free_cut']-1,[f'CCX q11 {B} {helper}',f'CX q10 {helper}'])
        parity=[f'CX q11 {B}','CX q10 q11',f'CX q12 {C}']
        paid=[f'BIT_STORE1 {comp}',f'BIT_INVERT {comp} if {z}',f'PUSH_CONDITION if {rbit}',f'PUSH_CONDITION if {comp}',
              *parity,f'CCZ q11 {B} {C}',*reversed(parity),'POP_CONDITION','POP_CONDITION',f'BIT_STORE0 {comp}']
        free=[f'Z {helper} if {rbit}',f'CZ {helper} q12 if {rbit}',f'CZ {helper} {C} if {rbit}']
        insert(p['paid_cut'],paid);insert(p['free_cut'],free)
        p['paid_complement_lines']=paid;p['native_product_free_lines']=free
    # Last paired peak: erase the first helper immediately, and combine the
    # two HMR outcomes of the identical q8 function at its old final cleanup.
    pair_start,pair_hmr=14685,14860
    expect(14684,['CX q8 q12','CX q12 q5'])
    expect(14819,['HMR q36 b192','PUSH_CONDITION if b192'])
    expect(pair_hmr,['HMR q8 b192','PUSH_CONDITION if b192'])
    insert(pair_start,['HMR q8 b9002'],[pair_hmr])
    first_prep=['CX q10 q7','CX q3 q7','CX q2 q7','CX q2 q10','CX q26 q10','CX q2 q3',
                'CCX q10 q3 q7','CX q2 q3','CX q26 q10','CX q2 q10']
    expect(14558,first_prep)
    second_prep=['CX q7 q11','CX q7 q4','X q4','CCX q11 q4 q8','X q4','CX q7 q4','CX q7 q11','CX q7 q8']
    E_phase=['Z q10','Z q3','CZ q10 q3','CZ q10 q2','CZ q3 q2','CZ q3 q26','CZ q2 q26']
    erase_first=['HMR q7 b9005',*[x+' if b9005' for x in E_phase],'BIT_STORE0 b9005']
    insert(14821,first_prep+second_prep+erase_first)
    pair_cleanup=['HMR q8 b9004']
    insert(14859,pair_cleanup);extra('b9004');extra('b9005')
    alter(pair_hmr,pair_hmr+1,['BIT_STORE0 b192','BIT_INVERT b192 if b9002','BIT_INVERT b192 if b9004',
                             'BIT_STORE0 b9002','BIT_STORE0 b9004'])
    # Reverse the already-paid half fallback contained in the freed interval.
    hp=next(p for p in json.loads(HALVES.read_text())['plans'] if p['case_id']==33)
    lo=match(hp['replacement']);hi=lo+len(hp['replacement']);assert pair_start<=lo<hi<14820
    original=r.Program(r.ORIGINAL.read_text());aa,bb=hp['original_integrated_interval']
    reverted=[r.literal(o) for o in original.operations[aa:bb]];reverted_origins=[]
    for o,line in zip(original.operations[aa:bb],reverted):
        if o.kind=='HMR':
            q,b=o.arguments;want=f'HMR {q} {hp["new_classical_owner"]}' if q==hp['retired_owner'] else line
            hits=[i for i in range(lo,hi) if actual[i]==want];assert len(hits)==1;reverted_origins.append(hits[0])
        else:reverted_origins.append(None)
    alter(lo,hi,reverted,reverted_origins);dead_bits.append(hp['new_classical_owner'])
    # Final peak: Z=(q29+Y)*(q30+Y)+Y is XORed directly into q0.
    # Its old b181*Z sign is quadratic in the prepared controls. The old
    # b360*Z*q0 interaction is one CCZ plus one CZ, before q0 is changed.
    # Delete the q21 HMR and its whole feedback: its b181 result is dead at
    # the next unconditional HMR q8->b181. Never mention a spare zero q21.
    direct_start,direct_end=15187,15208
    expect(direct_start,['CX q8 q29','CX q8 q30','CCX q29 q30 q21','CX q8 q21',
                        'PUSH_CONDITION if b181','Z q21','POP_CONDITION',
                        'CX q8 q29','CX q29 q30','PUSH_CONDITION if b360',
                        'CZ q21 q0','POP_CONDITION','CX q21 q0','HMR q21 b181',
                        'PUSH_CONDITION if b181','X q30','CZ q29 q30','CZ q29 q8',
                        'CZ q30 q8','X q30','POP_CONDITION'])
    expect(direct_end,['HMR q8 b181'])
    expect(14992,['HMR q26 b968','BIT_STORE0 b360','BIT_INVERT b360 if b967'])
    expect(15036,['BIT_STORE0 b360','BIT_INVERT b360 if b968'])
    assert not any((o.kind.startswith('BIT_') and o.arguments[0]=='b360') or
                   (o.kind=='HMR' and o.arguments[1]=='b360') for o in ops[15038:direct_end])
    direct_body=['CX q8 q29','CX q8 q30','CZ q29 q30 if b181','Z q8 if b181',
                 'CCZ q29 q30 q0 if b360','CZ q8 q0 if b360',
                 'CCX q29 q30 q0','CX q8 q0','CX q8 q29','CX q29 q30']
    alter(direct_start,direct_end,direct_body)
    live_after_direct,killed_after_direct=continuation_live_classical(ops,direct_end)
    assert 'b181' not in live_after_direct and killed_after_direct['b181']==15208
    # Render while preserving all native metadata and operation bindings.
    out=['# '+r.NOTICE];origins=[];mapping={};index=0;metadata={'REGISTER','APPEND_TO_REGISTER','INFO_TAG','DEBUG_PRINT'}
    for line in text.splitlines():
        tokens=shlex.split(line,comments=True)
        if not tokens or tokens[0] in metadata:out.append(line);continue
        mapping[index]=len(origins)
        for line2,origin in inserts.get(index,[]):out.append(line2);origins.append(origin)
        if index in changes:
            for line2,origin in changes[index]:out.append(line2);origins.append(origin)
        elif index not in skipped:out.append(line);origins.append(index)
        index+=1
    assert index==len(ops);mapping[index]=len(origins)
    changed='\n'.join(out)+'\n';candidate=r.Program(changed)
    assert len(candidate.operations)==len(origins) and candidate.measurements==parent.measurements+1
    assert candidate.registers==parent.registers
    assert [(o.arguments,o.condition,o.half_turns) for o in candidate.operations if o.kind=='Z_POW']==[(o.arguments,o.condition,o.half_turns) for o in ops if o.kind=='Z_POW']
    dest=args.out/'candidate_text.kmx';dest.write_text(changed)
    components=[dict(name='FIRST_SINGLE',parent_interval=[11013,11223],windows=[[11040,11046]],cost='1/4'),
                dict(name='SECOND_SINGLE',parent_interval=[11318,11528],windows=[[11345,11351]],cost='1/4'),
                dict(name='LAST_PAIR',parent_interval=[14685,14888],windows=[[14738,14744],[14754,14763]],cost='1/2'),
                dict(name='FINAL_WINDOW',parent_interval=[15186,15235],windows=[[15190,15201]],cost='1/2')]
    for c in components:c['output_interval']=[mapping[i] for i in c['parent_interval']]
    proof=None
    if args.full_local_proof:
        low,high=11013,15235;alo,ahi=mapping[low],mapping[high]
        prefix=r.replay(ops[:14685],r.initial_state(parent),captures=[11013,11318,14685])
        for p in single_specs:
            frame=prefix['captures'][p['start']];f={}
            for m in p['f']:
                z={0:(1<<r.N)-1}
                for k in range(44):
                    if m>>k&1:z=r.pm(z,frame[f'q{k}'])
                f=r.px(f,z)
            assert f==frame[p['owner']],('single actual relation',p['owner'])
        state=prefix['captures'][low]
        before=r.replay(ops[low:high],state,phase=True)
        segment=[];events=[]
        for i,o in enumerate(candidate.operations[alo:ahi],alo):
            if o.kind=='HMR':
                origin=origins[i]
                event=ops[origin].event if origin is not None else extra_events[o.arguments[1]]
                events.append(dict(output_operation=i,parent_operation=origin,formal_event=event))
                o=replace(o,event=event)
            segment.append(o)
        for q in candidate.wires:state.setdefault(q,{})
        after=r.replay(segment,state,phase=True,masks=True)
        assert before['phase']==after['phase'],'binary phase mismatch'
        assert before['rotations']==after['rotations'],'rotation mismatch'
        for q in [f'q{i}' for i in range(44)]:assert before['state'][q]==after['state'][q],('quantum mismatch',q)
        live,kills=continuation_live_classical(ops,high)
        for q in live:assert before['state'][q]==after['state'][q],('classical mismatch',q)
        assert not set(dead_bits)&live
        for k in range(9000,9012):assert not after['state'].get(f'b{k}',{}),('fresh classical residual',k)
        for c in components:
            a,b=c['output_interval'];hist=Counter(m.bit_count() for m in after['masks'][a-alo:b-alo+1])
            c['local_width_histogram']=dict(sorted(hist.items()));c['local_maximum_width']=max(hist)
            assert max(hist)<=43,('component width',c['name'],hist)
        proof=dict(notice=r.NOTICE,status='FULL_3133452_INPUT_ALL_HMR_LOCAL_VALUE_PHASE_WIDTH_PASS',original_inputs=r.N,
                   parent_interval=[low,high],output_interval=[alo,ahi],all_original_HMR=True,extra_independent_HMR=2,
                   removed_original_HMR=1,removed_q21_HMR_bit_dead_before_unconditional_overwrite=15208,
                   quantum_owners_compared=44,continuation_classical_owners_compared=len(live),
                   unused_removed_temporaries=dead_bits,fresh_classical_owners_zero_at_exit=True,
                   dead_parity_guard_first_unconditional_overwrites={q:kills[q] for q in ['b191','b192']},
                   components=components,formal_HMR_event_map=events,global_Q43_claimed=False)
        (args.out/'LOCAL_PROOF.json').write_text(json.dumps(proof,indent=2)+'\n')
    report=dict(notice=r.NOTICE,status='FIVE_REMAINING_EARLY_WINDOWS_EMITTED_ROOT_QUALIFICATION_PENDING',
                source_sha256=r.sha(Path(__file__)),parent_native=str(PARENT.relative_to(r.BASE)),parent_sha256=PARENT_SHA,
                candidate_native_sha256=r.sha(dest),parent_expected_Toffolis='5837/4',net_expected_Toffolis='3/2',
                modelled_expected_Toffolis='5843/4',removed_half_case=33,removed_half_parent_interval=[lo,hi],
                single_final_read_advances=single_specs,paired_actual_first_helper_preparation=first_prep,
                paired_actual_second_preparation=second_prep,paired_first_helper_immediate_cleanup=erase_first,
                paired_extra_preparation_cost='1',paired_extra_CCZ_cost='0',paired_removed_cost='1/2',
                paired_original_feedback_guard='m = s XOR (g AND u); s is original moved fair HMR, g is later native guard, u is new conditional HMR of the same q8 value',
                paired_original_feedback_guard_probability='1/2 because s is independent of g,u and has coefficient1',
                paired_native_cleanup_changes_no_quantum_values_after_14888=True,
                final_direct_carry_interval=[direct_start,direct_end],final_direct_carry_lines=direct_body,
                final_direct_carry_identity='Z=A*B+Y; old b181*Z is CZ(A,B)+Z(Y), old b360*Z*q0 is CCZ(A,B,q0)+CZ(Y,q0), then q0 ^= A*B+Y.',
                final_guard_probability='b360 is an exact copy of the unconditional HMR q26->b968 at14992; probability1/2.',
                final_direct_CCX_cost_delta='0',final_literal_CCZ_cost='1/2',
                removed_q21_HMR_operation=15200,removed_q21_HMR_live_uses='Only its removed feedback; b181 overwritten unconditionally at15208 before any remaining read.',
                final_component_no_q21_operand=True,
                components=components,peak_windows_removed=5,peak_cuts_removed=38,
                fresh_classical_owners=[f'b{k}' for k in range(9000,9012) if f'b{k}' in candidate.wires],extra_static_HMR=1,
                extra_independent_HMR=2,removed_original_HMR=1,T_model=1,rotation_model=34,
                full_local_proof_passed=proof is not None,global_Q43_claimed=False,
                seconds=time.monotonic()-began,
                bindings={str(p.relative_to(r.BASE)):r.sha(p) for p in [HALVES,r.ORIGINAL,Path(__file__)]})
    (args.out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    (args.out/'OPERATION_MAP.json.gz').write_bytes(gzip.compress((json.dumps(dict(notice=r.NOTICE,parent_to_output=mapping,output_origins=origins),separators=(',',':'))+'\n').encode(),mtime=0))
    print(json.dumps({k:v for k,v in report.items() if k not in ('single_final_read_advances','components','bindings')},indent=2),flush=True)


if __name__=='__main__':main()
