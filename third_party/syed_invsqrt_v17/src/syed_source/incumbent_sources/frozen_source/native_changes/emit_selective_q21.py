# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Emit the complete causal selective-deletion/q21-displacement construction.

The 3034 common-prefix pulses are global.  They are canceled later on the
six retained-gate sectors.  Only observed m286=m836=0 sectors delete18933;
they physically sample early m909 and retain the old physical HMR909 too.
The latter is reconciled to the early value by explicit free phases.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from fractions import Fraction
import json
from pathlib import Path
import shlex
import time
from retime_hmr import NOTICE,Program,original_guards,probability,sha


def parity_product_instructions(left,right,gate,target=None):
    """Prepare two independent parities reversibly, act, then restore controls."""
    left=set(left);right=set(right);assert left and right and left!=right
    order=lambda q:int(q[1:])
    p=min(left,key=order);forward=[('CX',q,p) for q in sorted(left-{p},key=order)]
    adjusted=set(right)
    if p in right:adjusted^=left-{p}
    q=min(adjusted-{p},key=order)
    forward += [('CX',r,q) for r in sorted(adjusted-{q},key=order)]
    middle=[gate,p,q]+([] if target is None else [target])
    return [' '.join(x) for x in forward]+[' '.join(middle)]+[' '.join(x) for x in reversed(forward)]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--native',type=Path,required=True)
    ap.add_argument('--common-recipe',type=Path,required=True);ap.add_argument('--good-reports',type=Path,nargs='+',required=True)
    ap.add_argument('--cancel-report',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();began=time.monotonic();source=args.native.read_text();program=Program(source)
    common=json.loads(args.common_recipe.read_text());cancel=json.loads(args.cancel_report.read_text())
    assert common['deleted_CCX']==18933 and common['varied_event']==871
    assert all(p['varied_outcome_guard']==0 for p in common['phase_pulses'] if p['cut']>=18933)
    assert cancel['all_retained_cases_repaired'] and cancel['selected_deletion_cases']==[0,2]
    good={}
    for path in args.good_reports:
        report=json.loads(path.read_text())
        for r in report['records']:
            if r['case'] in (0,2):
                assert r['status']=='EXACT_SUBSET_Q21_DISPLACEMENT_RESIDUAL_RECIPE' and r['pulses'] is not None
                assert r['insertion_cut']==19794 and r['retirement_cut']==19833
                assert r['paid_CCX_count']==1 and Fraction(r['added_expected_Toffolis_for_block'])==Fraction(1,32)
                good[r['case']]=r
    assert sorted(good)==[0,2]
    bad={r['case']:r for r in cancel['records']};assert sorted(bad)==[1,3,4,5,6,7]
    assert all(r['pulses'] is not None for r in bad.values())
    contexts=[];scope=[]
    for i,op in enumerate(program.operations):
        contexts.append(list(scope))
        if op.kind=='PUSH_CONDITION':scope.append(i)
        elif op.kind=='POP_CONDITION':scope.pop()
    assert not scope and contexts[17030]==contexts[19833]==[] and contexts[19794]==[19792]
    assert program.operations[18933].kind=='CCX' and program.operations[18933].arguments==('q17','q19','q21')
    assert program.operations[19832].kind=='HMR' and program.operations[19832].arguments==('q21','b360')
    original_gs=original_guards(program)
    next_b=max(int(b[1:]) for b in program.wires if b.startswith('b') and b[1:].isdigit())+1
    first_fresh=next_b
    def fresh():
        nonlocal next_b
        value=f'b{next_b}';next_b+=1;return value
    copies={e:fresh() for e in (286,815,836,871,905)}
    complements={e:fresh() for e in (286,815,836,871)}
    early=fresh();selected=fresh();not_selected=fresh();physical909=fresh();mismatch=fresh()
    event_birth={op.event:i+1 for i,op in enumerate(program.operations) if op.kind=='HMR'}
    pulses=[]
    for pulse in common['phase_pulses']:
        lane=pulse['varied_outcome_guard'];conditions=[] if lane is None else [copies[871] if lane else complements[871]]
        assert lane is None or pulse['cut']>=event_birth[871]
        pulses.append(dict(pulse,conditions=conditions,role='global common prefix'))
    for case,record in sorted({**good,**bad}.items()):
        fixed={int(e):v for e,v in record['fixed_observed_outcomes'].items()}
        assert fixed=={871:1,286:case&1,815:(case>>1)&1,836:(case>>2)&1}
        base=[copies[e] if v else complements[e] for e,v in sorted(fixed.items())]
        for pulse in record['pulses']:
            if pulse['phase_gate']=='Q21_AFFINE_DISPLACEMENT':continue
            assert pulse['phase_gate'] in ('NEG','Z','CZ')
            conditions=list(base)
            for e in pulse['observed_event_copies']:
                if e in fixed:continue
                if e==909:
                    assert case in good and pulse['cut']>=17030
                    conditions.append(early)
                else:
                    assert e in copies and pulse['cut']>=event_birth[e]
                    conditions.append(copies[e])
            assert pulse['exited_original_PUSH_operations']==contexts[pulse['cut']]
            assert case in bad or pulse['cut']<=19794 or pulse['cut']>=19833
            pulses.append(dict(pulse,conditions=conditions,role='good residual' if case in good else 'retained-gate prefix cancellation',case=case))
    needed={j for pulse in pulses for j in contexts[pulse['cut']]};scope_copies={j:fresh() for j in sorted(needed)}
    birth_inserts=defaultdict(list);birth_bindings=[]
    for i,op in enumerate(program.operations):
        if op.kind!='HMR' or op.event not in copies:continue
        assert original_gs[i]=={0} and contexts[i]==[]
        dest=copies[op.event]
        birth_inserts[i+1]+=[f'BIT_STORE0 {dest}',f'BIT_INVERT {dest} if {op.arguments[1]}']
        if op.event in complements:
            birth_inserts[i+1]+=[f'BIT_STORE1 {complements[op.event]}',f'BIT_INVERT {complements[op.event]} if {dest}']
        birth_bindings.append(dict(event=op.event,operation=i,source_owner=op.arguments[1],copy_owner=dest,complement_owner=complements.get(op.event)))
    birth_inserts[17030]+=[f'PUSH_CONDITION if {copies[871]}',f'PUSH_CONDITION if {complements[286]}',
                          f'PUSH_CONDITION if {complements[836]}',f'BIT_STORE1 {selected}',
                          'POP_CONDITION','POP_CONDITION','POP_CONDITION',
                          f'BIT_STORE1 {not_selected}',f'BIT_INVERT {not_selected} if {selected}',
                          f'PUSH_CONDITION if {selected}',f'HMR q36 {early}','POP_CONDITION']
    grouped=defaultdict(lambda:defaultdict(list))
    for pulse in pulses:grouped[pulse['cut']][tuple(pulse['conditions'])].append(' '.join([pulse['phase_gate']]+pulse['quantum_owners']))
    phase_inserts={}
    for cut,groups in grouped.items():
        ctx=contexts[cut];lines=['POP_CONDITION']*len(ctx)
        for conditions,gates in sorted(groups.items()):
            lines += [f'PUSH_CONDITION if {b}' for b in conditions]+gates+['POP_CONDITION']*len(conditions)
        lines += [f'PUSH_CONDITION if {scope_copies[j]}' for j in ctx];phase_inserts[cut]=lines
    displacement=[];h_repairs=[];h_bindings=[]
    for case,record in sorted(good.items()):
        fixed={int(e):v for e,v in record['fixed_observed_outcomes'].items()}
        conditions=[copies[e] if v else complements[e] for e,v in sorted(fixed.items())]
        # This insertion is already inside the original m905 scope.
        shift=[];h_phase=[];affine=[]
        for pulse in record['pulses']:
            if pulse['phase_gate']!='Q21_AFFINE_DISPLACEMENT':continue
            owners=pulse['quantum_owners'];assert not any(q in ('q21','q34','q26') for q in owners)
            if owners:shift.append(f'CX {owners[0]} q21');h_phase.append(f'Z {owners[0]}');affine.append(owners[0])
            else:shift.append('X q21');h_phase.append('NEG');affine.append('1')
        for factor in record['paid_factors']:
            assert not any(q in ('q21','q34','q26') for q in factor['left_parity']+factor['right_parity'])
            shift+=parity_product_instructions(factor['left_parity'],factor['right_parity'],'CCX','q21')
            h_phase+=parity_product_instructions(factor['left_parity'],factor['right_parity'],'CZ')
        displacement += [f'PUSH_CONDITION if {b}' for b in conditions]+shift+['POP_CONDITION']*len(conditions)
        # Combining the physical-outcome assimilation and the canonical
        # gadget sign repair cancels both early_m909*h terms.  Only n909*h
        # remains, in addition to (n909 XOR early_m909)*the affine baseline.
        final_conditions=conditions+[copies[905],physical909]
        h_repairs += [f'PUSH_CONDITION if {b}' for b in final_conditions]+h_phase+['POP_CONDITION']*len(final_conditions)
        h_bindings.append(dict(case=case,affine_terms=affine,quadratic_factors=record['paid_factors'],
                               insertion_instructions=shift,physical_outcome_phase_instructions=h_phase,
                               paid_guard_events=dict(fixed,m905=1),expected_paid_for_block='1/32'))
    retirement=[f'BIT_STORE0 {physical909}',f'BIT_INVERT {physical909} if b360',
                f'PUSH_CONDITION if {selected}',f'BIT_STORE0 {mismatch}',
                f'BIT_INVERT {mismatch} if {physical909}',f'BIT_INVERT {mismatch} if {early}',
                f'Z q17 if {mismatch}',f'Z q18 if {mismatch}',f'Z q43 if {mismatch}','POP_CONDITION']
    retirement+=h_repairs
    retirement += [f'PUSH_CONDITION if {selected}','BIT_STORE0 b360',f'BIT_INVERT b360 if {early}','POP_CONDITION']
    metadata={'REGISTER','APPEND_TO_REGISTER','INFO_TAG','DEBUG_PRINT'};lines=['# '+NOTICE];index=0
    original_to_new={};insertion_ranges={};new_index=0
    def emit(instructions,role,cut):
        nonlocal new_index
        if not instructions:return
        start=new_index;lines.extend(instructions);new_index+=len(instructions)
        insertion_ranges.setdefault(str(cut),[]).append(dict(role=role,new_operations=[start,new_index]))
    initialization=[f'BIT_STORE0 b{i}' for i in range(first_fresh,next_b)]
    for line in source.splitlines():
        tokens=shlex.split(line,comments=True)
        if not tokens or tokens[0] in metadata:lines.append(line);continue
        assert program.operations[index].kind==tokens[0]
        if index==0:emit(initialization,'fresh classical owner initialization',index)
        emit(birth_inserts.get(index,[]),'observed outcome copies / selected early sample',index)
        if index==19833:emit(retirement,'physical HMR909 reconciliation and gadget sign repair',index)
        emit(phase_inserts.get(index,[]),'causal phase recipe',index)
        if index==19794:emit(displacement,'q21 displacements on selected past blocks',index)
        if index in scope_copies:
            op=program.operations[index];owner=scope_copies[index]
            emit([f'BIT_STORE0 {owner}',f'BIT_INVERT {owner} if {op.condition}'],'immutable cached original PUSH guard',index)
        original_to_new[index]=new_index
        if index==18933:lines.append(f'CCX q17 q19 q21 if {not_selected}')
        else:lines.append(line)
        new_index+=1;index+=1
    assert index==len(program.operations)
    output='\n'.join(lines)+'\n';candidate=Program(output)
    assert len(candidate.operations)==new_index
    assert candidate.quantum_wires==program.quantum_wires and candidate.registers==program.registers
    assert candidate.measurements==program.measurements+1
    candidate_gs=original_guards(candidate)
    def resource(p,gs):return sum((probability(g) for op,g in zip(p.operations,gs) if op.kind in ('CCX','CCZ','CSWAP')),Fraction(0))
    before=resource(program,original_gs);after=resource(candidate,candidate_gs)
    assert before==Fraction(11429,8) and after==Fraction(22857,16),(before,after)
    assert [(op.arguments,op.half_turns,op.condition) for op in program.operations if op.kind=='Z_POW']==[(op.arguments,op.half_turns,op.condition) for op in candidate.operations if op.kind=='Z_POW']
    old_events={i:op.event for i,op in enumerate(program.operations) if op.kind=='HMR'};new_to_old={new:old for old,new in original_to_new.items()}
    hmr=[];paid=[]
    for i,op in enumerate(candidate.operations):
        if op.kind=='HMR':
            old=new_to_old.get(i)
            hmr.append(dict(new_operation=i,new_event=op.event,quantum_owner=op.arguments[0],outcome_owner=op.arguments[1],
                            original_operation=old,original_event=old_events.get(old),
                            role='early ideal909 on selected sector' if old is None else ('retained physical909' if old_events[old]==909 else 'original HMR')))
        if op.kind in ('CCX','CCZ','CSWAP') and (i not in new_to_old or new_to_old[i]==18933):
            paid.append(dict(new_operation=i,kind=op.kind,arguments=op.arguments,original_operation=new_to_old.get(i),
                             firing_probability=str(probability(candidate_gs[i])),guard_ANF_monomials=[[j for j in range(m.bit_length()) if m>>j&1] for m in sorted(candidate_gs[i])]))
    args.out.mkdir(parents=True,exist_ok=True);dest=args.out/'candidate.kmx';dest.write_text(output)
    report=dict(notice=NOTICE,status='COMPLETE_CAUSAL_SELECTIVE_Q21_CANDIDATE_AWAITING_FULL_DOMAIN_PROOF',
                original_selected_CCX=18933,selection_original_outcomes='m871 AND NOT m286 AND NOT m836',
                selected_original_probability='1/8',retained_gate_probability='3/8',added_paid_probability='1/16',
                expected_Toffolis_before=str(before),expected_Toffolis_after=str(after),expected_saving=str(before-after),
                global_common_prefix_pulses=len(common['phase_pulses']),ordinary_good_residual_pulses=sum(r['ordinary_phase_pulses'] for r in good.values()),
                ordinary_retained_gate_cancellation_pulses=sum(r['pulse_count'] for r in bad.values()),
                quantum_displacement_recipes=h_bindings,actual_changed_paid_instructions=paid,
                copied_original_outcome_owners=copies,complement_owners=complements,copy_birth_bindings=birth_bindings,
                selected_sector_owner=selected,complementary_sector_owner=not_selected,
                early_m909_owner=early,retained_physical_m909_copy_owner=physical909,mismatch_owner=mismatch,
                actual_HMR_bindings=hmr,retirement_reconciliation_instructions=retirement,
                cached_original_PUSH_guards=scope_copies,original_to_new_operation=original_to_new,insertion_ranges=insertion_ranges,
                Q=44,T=1,generic_rotations=34,unchanged_Z_POW_instructions=39,
                native_operations=len(candidate.operations),HMR_sites=candidate.measurements,
                all_outcome_reads_causal=True,qualified=False,
                bindings={str(f):sha(f) for f in [Path(__file__),args.native,args.common_recipe,*args.good_reports,args.cancel_report,dest]},seconds=time.monotonic()-began)
    (args.out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],candidate=str(dest),sha256=sha(dest),emitter_sha256=sha(Path(__file__)),
                          expected_Toffolis_after=str(after),native_operations=len(candidate.operations),seconds=time.monotonic()-began)),flush=True)


if __name__=='__main__':main()
