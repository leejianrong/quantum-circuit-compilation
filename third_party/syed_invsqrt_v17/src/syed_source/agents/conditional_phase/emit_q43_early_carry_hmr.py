# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Emit the literal half-cost early-carry HMR fallback on an anchored parent.

All native blocks must match the sealed integrated-base contracts exactly.
Fresh classical owners carry moved physical outcomes until their old birth
locations. This emitter adds the actual CCZ repair, not a modelled free debt.
"""
import argparse
from collections import Counter
from dataclasses import replace
from fractions import Fraction
import gzip
import json
from pathlib import Path
import shlex
import time

from emit_q43_phase_swaps import NOTICE, Program, literal, replay, sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def choose(saved, requested):
    if requested:
        plans = [p for p in saved['candidates'] if p['case'] in requested]
        assert len(plans)==len(set(requested))
        return sorted(plans,key=lambda p:p['start'])
    selected = {}
    for p in saved['candidates']:
        key = tuple(p['covered_peak_ids'])
        if key not in selected or p['old_HMR']-p['start'] < selected[key]['old_HMR']-selected[key]['start']:
            selected[key] = p
    return sorted(selected.values(),key=lambda p:p['start'])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--native',required=True,type=Path)
    ap.add_argument('--plans',required=True,type=Path)
    ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--parent-cost',required=True,type=Fraction)
    ap.add_argument('--cases',nargs='+',type=int)
    ap.add_argument('--full-local-proof',action='store_true')
    args = ap.parse_args()
    began = time.monotonic()
    assert not args.out.exists()
    args.out.mkdir(parents=True)
    saved = json.loads(args.plans.read_text())
    original_path = ROOT/'agents/temporal_merges/q43_integrated_width_base_v1/candidate_text.kmx'
    assert sha(original_path)==saved['native_sha256']
    source = Program(original_path.read_text())
    text = args.native.read_text()
    parent = Program(text)
    originals = [literal(o) for o in source.operations]
    actual = [literal(o) for o in parent.operations]
    by_first = {}
    for i,line in enumerate(actual):
        by_first.setdefault(line,[]).append(i)
    chosen = choose(saved,args.cases)
    fresh = max(int(q[1:]) for q in parent.wires if q.startswith('b') and q[1:].isdigit())+1
    plans = []
    for number,p in enumerate(chosen):
        old = originals[p['start']:p['old_HMR']+1]
        matches = [i for i in by_first.get(old[0],[]) if actual[i:i+len(old)]==old]
        assert len(matches)==1,(p['case'],matches)
        start = matches[0]
        delta = start-p['start']
        new_bit = f'b{fresh+number}'
        lines = []
        for line in p['replacement']:
            words = line.split()
            lines.append(' '.join(new_bit if w==p['new_classical_owner'] else w for w in words))
        origins = [None if u is None else u+delta for u in p['origins']]
        plans.append(dict(case_id=p['case'],original_integrated_interval=[p['start'],p['old_HMR']+1],
                          parent_interval=[start,start+len(old)],replacement=lines,origins=origins,
                          retired_owner=p['retired_owner'],moved_target=p['moved_target'],
                          new_classical_owner=new_bit,original_event=parent.operations[p['old_HMR']+delta].event,
                          exact_added_expected_Toffolis=p['exact_added_expected_Toffolis'],
                          original_integrated_peak_windows=p['covered_peak_windows']))
    assert all(a['parent_interval'][1]<=b['parent_interval'][0] for a,b in zip(plans,plans[1:]))
    starts = {p['parent_interval'][0]:p for p in plans}
    metadata = {'REGISTER','APPEND_TO_REGISTER','INFO_TAG','DEBUG_PRINT'}
    index,skip = 0,-1
    lines,origins = ['# '+NOTICE],[]
    for line in text.splitlines():
        words = shlex.split(line,comments=True)
        if not words or words[0] in metadata:
            lines.append(line)
            continue
        if index in starts:
            p = starts[index]
            p['output_interval'] = [len(origins),len(origins)+len(p['replacement'])]
            lines += p['replacement']
            origins += p['origins']
            skip = p['parent_interval'][1]
        elif index >= skip:
            lines.append(line)
            origins.append(index)
        index += 1
    assert index==len(parent.operations)
    changed = '\n'.join(lines)+'\n'
    candidate = Program(changed)
    assert len(candidate.operations)==len(origins)
    assert candidate.measurements==parent.measurements
    assert candidate.registers==parent.registers
    assert [(o.half_turns,o.arguments,o.condition) for o in parent.operations if o.kind=='Z_POW']==[(o.half_turns,o.arguments,o.condition) for o in candidate.operations if o.kind=='Z_POW']
    dest = args.out/'candidate_text.kmx'
    dest.write_text(changed)
    proof = None
    if args.full_local_proof:
        import numpy as np
        n = 3133452
        xs = np.arange(1,n+1,dtype=np.uint64)
        full = (1<<n)-1
        state = {q:{} for q in parent.wires|candidate.wires}
        for bit,q in enumerate(parent.registers['x']):
            v = int.from_bytes(np.packbits(((xs>>bit)&1).astype(np.uint8),bitorder='little').tobytes(),'little')
            state[q] = {0:v} if v else {}
        del xs
        a,b = plans[0]['parent_interval'][0],plans[-1]['parent_interval'][1]
        state = replay(parent.operations[:a],state,full)[0]
        before = replay(parent.operations[a:b],state,full,keep_masks=True)
        aa,bb = plans[0]['output_interval'][0],plans[-1]['output_interval'][1]
        segment = list(candidate.operations[aa:bb])
        for i,origin in enumerate(origins[aa:bb]):
            if segment[i].kind=='HMR':
                assert origin is not None
                segment[i] = replace(segment[i],event=parent.operations[origin].event)
        after = replay(segment,state,full,keep_masks=True)
        assert before[1]==after[1] and before[2]==after[2]
        assert all(before[0][q]==after[0][q] for q in parent.wires)
        intervals = []
        for p in plans:
            lo,hi = p['output_interval']
            hist = Counter(m.bit_count() for m in after[3][lo-aa:hi-aa+1])
            assert max(hist)<=43,(p['case_id'],hist)
            intervals.append(dict(case_id=p['case_id'],output_interval=[lo,hi],peak=max(hist),histogram=dict(sorted(hist.items()))))
        proof = dict(status='FULL_3133452_INPUT_ALL_HMR_LOCAL_VALUE_PHASE_AND_WIDTH_PASS',
                     original_inputs=n,every_original_HMR=True,parent_interval=[a,b],output_interval=[aa,bb],
                     compared_native_classical_owners=True,fractional_arguments_unchanged=True,
                     selected_intervals=intervals,global_Q43_claimed=False)
    extra = sum(Fraction(p['exact_added_expected_Toffolis']) for p in plans)
    report = dict(notice=NOTICE,status='ANCHORED_EARLY_CARRY_HMR_FALLBACK_EMITTED',
                  native_path=str(args.native.resolve()),native_sha256=sha(args.native),
                  source_sha256=sha(__file__),plans_sha256=sha(args.plans),
                  output_native_sha256=sha(dest),parent_cost=str(args.parent_cost),
                  exact_added_expected_Toffolis=str(extra),modelled_output_cost=str(args.parent_cost+extra),
                  HMR_count=candidate.measurements,plan_count=len(plans),plans=plans,
                  local_full_proof=proof,full_native_qualification_pending=True,
                  global_Q43_claimed=False,seconds=time.monotonic()-began)
    (args.out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    (args.out/'OUTPUT_OPERATION_ORIGINS.json.gz').write_bytes(gzip.compress((json.dumps(dict(notice=NOTICE,origins=origins),separators=(',',':'))+'\n').encode(),mtime=0))
    print(json.dumps({k:v for k,v in report.items() if k not in ('plans','local_full_proof')},indent=2),flush=True)
    if proof:
        print(json.dumps({k:v for k,v in proof.items() if k!='selected_intervals'},indent=2),flush=True)


if __name__=='__main__':
    main()
