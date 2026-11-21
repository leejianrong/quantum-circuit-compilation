# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Replace phase-width substitutions by exact affine-parity delta recomputation.

Each chosen helper h=(1+c+sum(extras))*(a+b) has fanned into both a and b.
Its value is unchanged by that fanout. Retire it during its next idle interval,
pay the literal quadratic HMR phase, then restore it with one actual AND.
The final unmatched packet retains its established two-CSWAP substitution.
"""
from pathlib import Path
from dataclasses import replace
from collections import Counter
from fractions import Fraction
from functools import lru_cache
import argparse
import gzip
import hashlib
import json
import shlex
import time

import emit_later_bank_guard_sharing as r

START, END = 8511, 9118
ORIGINAL_COST = Fraction(11469, 8)
PHASE_REPORT = r.BASE/'agents/conditional_phase/q43_phase_swaps_all_v2/REPORT.json'
PHASE_NATIVE = r.BASE/'agents/conditional_phase/q43_phase_swaps_all_v2/candidate_text.kmx'
ORIGINAL_MASKS = r.BASE/'root/q43_integrated_width_base_root_v1/ALL_INPUT_ALL_HMR_OCCUPANCY.json.gz'


def semantic(op):
    return op.kind, op.arguments, op.condition, op.half_turns


def find_outer(program):
    ops = program.operations
    plans = []
    for i, op in enumerate(ops):
        if op.kind != 'CCX' or not 8400 <= i <= END or i < 3:
            continue
        c, b, h = op.arguments
        if ops[i-1].kind != 'CX':
            continue
        a = ops[i-1].arguments[0]
        if not (ops[i-1].arguments == (a,b) and
                [(o.kind,o.arguments) for o in ops[i+1:i+3]] == [('CX',(a,b)),('X',(c,))]):
            continue
        j=i+3;reverse_extras=[]
        while ops[j].kind=='CX' and ops[j].arguments[1]==c:
            reverse_extras.append(ops[j].arguments[0]);j+=1
        extras=list(reversed(reverse_extras))
        if not extras:
            continue
        expected_pre=[('CX',(d,c)) for d in extras]+[('X',(c,)),('CX',(a,b))]
        if [(o.kind,o.arguments) for o in ops[i-len(expected_pre):i]] != expected_pre:
            continue
        if [(o.kind,o.arguments) for o in ops[j:j+2]] != [('CX',(h,a)),('CX',(h,b))]:
            continue
        literal_begin=j+2
        begin=max(literal_begin,START)
        stop = next(j for j in range(begin,len(ops)) if h in ops[j].arguments)
        if stop > END or literal_begin >= END:
            continue
        assert [(o.kind,o.arguments) for o in ops[stop:stop+2]] == [('CX',(h,a)),('CX',(h,b))]
        assert ops[stop+2].kind == 'HMR' and ops[stop+2].arguments[0] == h
        assert all(o.condition is None for o in ops[i-len(expected_pre):literal_begin])
        assert all(h not in o.arguments and h != o.condition for o in ops[literal_begin:stop])
        assert len({h,a,b,c,*extras}) == 4+len(extras)
        plans.append(dict(kind='OUTER_DELTA', birth=i, start=begin, literal_idle_start=literal_begin,
                          end=stop, helper=h,control=c,extra_controls=extras,left=a,right=b,cost=1,
                          value='(1+control+sum(extra_controls))*(left+right)'))
    return plans


def feedback(plan, scratch):
    h,a,b,c = [plan[k] for k in ['helper','left','right','control']]
    return ([f'HMR {h} {scratch}',f'Z {a} if {scratch}',f'Z {b} if {scratch}']+
            [f'CZ {d} {q} if {scratch}' for d in [c]+plan['extra_controls'] for q in [a,b]]+
            [f'BIT_STORE0 {scratch}'])


def reconstruction(plan):
    h,a,b,c = [plan[k] for k in ['helper','left','right','control']]
    return ([f'X {c}']+[f'CX {d} {c}' for d in plan['extra_controls']]+
            [f'CX {a} {b}',f'CCX {c} {b} {h}',f'CX {a} {b}']+
            [f'CX {d} {c}' for d in reversed(plan['extra_controls'])]+[f'X {c}'])


def choose_cover(outer, swaps, masks):
    peaks = [i for i in range(START,END+1) if masks[i].bit_count() == 44]
    options = []
    for p in outer:
        covered = [j for j,t in enumerate(peaks) if p['start'] <= t < p['end']]
        if covered:
            assert covered == list(range(covered[0],covered[-1]+1))
            options.append(dict(plan=p, first=covered[0], last=covered[-1]))
    for p in swaps:
        covered = [j for j,t in enumerate(peaks) if p['start'] <= t < p['end']]
        if covered:
            options.append(dict(plan=dict(kind='SWAP_FALLBACK',cost=1,**p),first=covered[0],last=covered[-1]))
    @lru_cache(None)
    def solve(index):
        if index == len(peaks):
            return 0, ()
        choices = []
        for j,option in enumerate(options):
            if option['first'] <= index <= option['last']:
                cost, later = solve(option['last']+1)
                choices.append((1+cost,(j,)+later))
        assert choices, index
        return min(choices)
    cost, indices = solve(0)
    chosen = [options[j]['plan'] for j in indices]
    assert len(chosen)==cost
    return chosen, dict(original_peak_cuts=len(peaks), minimum_unit_cost_within_declared_interval_options=cost,
                        options=len(options), chosen=[dict(kind=p['kind'],start=p['start'],end=p['end'],helper=p['helper']) for p in chosen])


def make_component(program, chosen, scratch):
    outer = [p for p in chosen if p['kind']=='OUTER_DELTA']
    fallback = [p for p in chosen if p['kind']=='SWAP_FALLBACK']
    assert all(not(s['start'] < p[k] < s['end']) for p in outer for s in fallback for k in ['start','end'])
    lines, origins, extras = [], [], {}
    start_map,end_map = {},{}
    i = START
    while i < END:
        for p in outer:
            if p['end'] == i:
                start_map[('restore',p['birth'])] = len(lines)
                text = reconstruction(p)
                lines += text;origins += [None]*len(text)
        for k,p in enumerate(outer):
            if p['start'] == i:
                start_map[('retire',p['birth'])] = len(lines)
                extras[len(lines)] = k
                text = feedback(p,scratch)
                lines += text;origins += [None]*len(text)
        swap = next((p for p in fallback if p['start']==i),None)
        if swap:
            lines += swap['replacement'];origins += swap['origins'];i=swap['end']
        else:
            lines.append(r.literal(program.operations[i]));origins.append(i);i+=1
    assert all(p['end']<END for p in outer)
    parsed = r.Program('\n'.join(lines)+'\n').operations
    ops = []
    for j,op in enumerate(parsed):
        if op.kind == 'HMR':
            event = program.measurements+extras[j] if j in extras else program.operations[origins[j]].event
            op = replace(op,event=event)
        ops.append(op)
    return lines, origins, ops, start_map, extras


def full_check(program, chosen, changed_ops, scratch, start_map):
    state = r.replay(program.operations[:START],r.initial_state(program))['state']
    state[scratch] = {}
    old_checks = {}
    full = (1 << r.N)-1
    def identity(p,cut):
        def check(state, stack):
            assert stack == [{0:full}]
            c,a,b,h = [state[p[k]] for k in ['control','left','right','helper']]
            factor=r.px({0:full},c)
            for d in p['extra_controls']:factor=r.px(factor,state[d])
            expected = r.pm(factor,r.px(a,b))
            assert state[p['helper']] == expected, ('Actual helper factor mismatch',p['birth'],cut)
        return check
    for p in chosen:
        if p['kind']=='OUTER_DELTA':
            old_checks[p['start']-START] = identity(p,p['start'])
            old_checks[p['end']-START] = identity(p,p['end'])
    old = r.replay(program.operations[START:END],state,phase=True,masks=True,checks=old_checks)
    changed = r.replay(changed_ops,state,phase=True,masks=True)
    dead = {p['dead_classical_owner'] for p in chosen if p['kind']=='SWAP_FALLBACK'}
    for q in state:
        if q not in dead:
            assert old['state'][q] == changed['state'][q], ('Final value mismatch',q)
    assert not changed['state'][scratch]
    assert old['phase'] == changed['phase'], 'Binary phase mismatch'
    assert old['rotations'] == changed['rotations'], 'Fractional phase mask mismatch'
    assert max(m.bit_count() for m in changed['masks']) <= 43
    return dict(status='FULL_3133452_INPUT_ALL_HMR_LOCAL_VALUE_PHASE_AND_WIDTH_PASS',
                original_inputs=r.N, all_formal_original_and_added_HMR=True,
                actual_helper_identities_checked=2*sum(p['kind']=='OUTER_DELTA' for p in chosen), original_interval=[START,END],
                original_peak=max(m.bit_count() for m in old['masks']),
                changed_peak=max(m.bit_count() for m in changed['masks']),
                original_peak44_cuts=sum(m.bit_count()==44 for m in old['masks']),
                changed_peak44_cuts=sum(m.bit_count()==44 for m in changed['masks']),
                fractional_arguments_checked=len(old['rotations']),
                original_binary_phase_sha256=r.poly_digest(old['phase']),
                changed_binary_phase_sha256=r.poly_digest(changed['phase']),
                changed_live_histogram=dict(sorted(Counter(m.bit_count() for m in changed['masks']).items())),
                ignored_classical_outputs=sorted(dead), scratch_reset_zero=True,
                local_width_only=True, global_Q43_claimed=False),changed['masks']


def splice(text,start,end,replacement,original_mapping):
    byline={};index=0
    metadata={'REGISTER','APPEND_TO_REGISTER','INFO_TAG','DEBUG_PRINT'}
    for line,s in enumerate(text.splitlines()):
        fields=shlex.split(s,comments=True)
        if fields and fields[0] not in metadata:
            byline[line]=index;index+=1
    lines=['# '+r.NOTICE];origins=[]
    for line,s in enumerate(text.splitlines()):
        i=byline.get(line)
        if i is None:
            lines.append(s)
        elif i==start:
            lines+=replacement;origins+=original_mapping
        elif not start <= i < end:
            lines.append(s);origins.append(i)
    return '\n'.join(lines)+'\n',origins


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--compose',type=Path)
    ap.add_argument('--compose-cost',type=Fraction)
    args=ap.parse_args();began=time.monotonic()
    args.out.mkdir(parents=True,exist_ok=False)
    assert r.sha(r.ORIGINAL)==r.ORIGINAL_SHA
    original_text=r.ORIGINAL.read_text();program=r.Program(original_text)
    swaps_report=json.loads(PHASE_REPORT.read_text());assert swaps_report['parent_native_sha256']==r.ORIGINAL_SHA
    masks_record=json.load(gzip.open(ORIGINAL_MASKS,'rt'));assert masks_record['native_sha256']==r.ORIGINAL_SHA
    chosen,cover=choose_cover(find_outer(program),swaps_report['plans'],masks_record['masks'])
    compose=r.Program(args.compose.read_text()) if args.compose else None
    all_wires=set(program.wires) | (set(compose.wires) if compose else set())
    scratch=next(f'b{i}' for i in range(8000,100000) if f'b{i}' not in all_wires)
    lines,origins,ops,start_map,extras=make_component(program,chosen,scratch)
    local,live=full_check(program,chosen,ops,scratch,start_map)
    output,mapping=splice(original_text,START,END,lines,origins)
    output_path=args.out/'integrated_candidate_text.kmx';output_path.write_text(output)
    changed=r.Program(output)
    removed_measurements=sum(o.kind=='HMR' for o in program.operations[START:END])
    added_measurements=sum(o.kind=='HMR' for o in ops)
    assert changed.measurements==program.measurements+added_measurements-removed_measurements
    added_cost=cover['minimum_unit_cost_within_declared_interval_options']
    saving=12-added_cost
    actual_outer=sum(p['kind']=='OUTER_DELTA' for p in chosen)
    actual_fallback=sum(p['kind']=='SWAP_FALLBACK' for p in chosen)
    def paid_count(block):
        depth=0;count=0
        for op in block:
            if op.kind=='PUSH_CONDITION':depth+=1
            elif op.kind=='POP_CONDITION':depth-=1
            elif op.kind in ('CCX','CCZ','CSWAP'):
                assert depth==0 and op.condition is None
                count+=1
        assert depth==0
        return count
    assert paid_count(ops)-paid_count(program.operations[START:END])==added_cost
    assert [(o.kind,o.arguments,o.condition,o.half_turns)for o in changed.operations if o.kind=='Z_POW']==[(o.kind,o.arguments,o.condition,o.half_turns)for o in program.operations if o.kind=='Z_POW']
    map_path=args.out/'INTEGRATED_OPERATION_MAP.json.gz'
    map_path.write_bytes(gzip.compress((json.dumps(dict(notice=r.NOTICE,parent_native_sha256=r.ORIGINAL_SHA,
          output_native_sha256=r.sha(output_path),output_to_original_operation=mapping),separators=(',',':'))+'\n').encode(),mtime=0))
    component=args.out/'PHASE_COMPONENT.kmx';component.write_text('# '+r.NOTICE+'\n'+'\n'.join(lines)+'\n')
    composed=None
    if compose:
        assert args.compose_cost is not None
        old_phase=r.Program(PHASE_NATIVE.read_text()).operations[START:9010]
        needle=[semantic(o)for o in old_phase]
        haystack=[semantic(o)for o in compose.operations]
        matches=[i for i in range(len(haystack)-len(needle)+1)if haystack[i]==needle[0] and haystack[i:i+len(needle)]==needle]
        assert len(matches)==1,('Expected one exact phase block match',matches)
        at=matches[0]
        composed_text,composed_map=splice(args.compose.read_text(),at,at+len(needle),lines,[None]*len(lines))
        composed_path=args.out/'candidate_text.kmx';composed_path.write_text(composed_text)
        map2=args.out/'COMPOSED_OPERATION_MAP.json.gz'
        map2.write_bytes(gzip.compress((json.dumps(dict(notice=r.NOTICE,parent_native_sha256=r.sha(args.compose),
              output_native_sha256=r.sha(composed_path),output_to_parent_operation=composed_map,
              replacement_original_component_origins=origins),separators=(',',':'))+'\n').encode(),mtime=0))
        composed=dict(parent_native=str(args.compose),parent_native_sha256=r.sha(args.compose),
                      replaced_parent_interval=[at,at+len(needle)],output_interval=[at,at+len(lines)],
                      exact_semantic_match_operations=len(needle),output_native=str(composed_path),output_native_sha256=r.sha(composed_path),
                      parent_cost=str(args.compose_cost),modelled_expected_Toffolis=str(args.compose_cost-saving),
                      exact_delta_expected_Toffolis=str(-saving),operation_map_sha256=r.sha(map2),
                      unchanged_full_domain_proof_pending=True)
    report=dict(notice=r.NOTICE,status='ACTUAL_OUTER_DELTA_RETIREMENT_EMITTED_LOCAL_FULL_PROOF_PASS',qualified=False,
          source_sha256=r.sha(Path(__file__)),parent_native_sha256=r.ORIGINAL_SHA,
          output_native_sha256=r.sha(output_path),component_sha256=r.sha(component),
          cover=cover,chosen=chosen,scratch_classical_owner=scratch,local_full_proof=local,
          original_expected_Toffolis=str(ORIGINAL_COST),actual_added_ANDs=actual_outer,remaining_swap_substitutions=actual_fallback,
          exact_added_expected_Toffolis=str(added_cost),integrated_modelled_expected_Toffolis=str(ORIGINAL_COST+added_cost),
          saving_vs_twelve_substitutions=str(saving),saving_vs_previous_outer_component=str(7-added_cost),composed=composed,
          original_HMR_count=program.measurements,output_HMR_count=changed.measurements,
          original_operations=len(program.operations),output_operations=len(changed.operations),
          component_original_interval=[START,END],component_output_interval=[START,START+len(lines)],
          component_inserted_HMR_offsets=extras,integrated_operation_map_sha256=r.sha(map_path),
          scope='Actual affine-parity outer delta helpers, each retired during its literal idle interval and reconstructed with one AND; remaining established CSWAP packets. Every factor identity is checked at both endpoints on all legal inputs and formal HMR branches. No whole-target decoder or information-losing encoding is assumed.',
          dependency_bindings=[r.bind(p)for p in [Path(r.__file__),r.ENGINE/'branch_prover.py',r.ORIGINAL,PHASE_REPORT,PHASE_NATIVE,ORIGINAL_MASKS]],
          costed_successors=[
              dict(route='Eliminate final unmatched phase substitution',modelled_additional_saving='1',scope='A separate causal borrow or equivalent free phase implementation of original9068..9118.'),
              dict(route='Whole-interval three-product decoder',modelled_additional_saving_over_this_component=str(added_cost-3),scope='Bound finite GPU job; exact first and unrestricted two-product tail plus native proof.'),
              dict(route='Whole-interval four-product decoder',modelled_additional_saving_over_this_component=str(added_cost-4),scope='Different larger decoder family with actual helper ownership and free cleanup.')],
          seconds=time.monotonic()-began)
    (args.out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items()if k not in ('chosen','dependency_bindings','notice')},indent=2),flush=True)


if __name__=='__main__':
    main()
