# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Find literal older-carry borrows across later guarded cleanup reads.

This is a constructive syntactic census, not a complete decoder search. An
original HMR moves left past control-only reads. The owner is reconstructed
by one actual AND only in the existing later guard, then freely HMR-erased.
The original measurement debt and its native correction are retained.
"""
import argparse
import json
from pathlib import Path
import time

import emit_later_bank_guard_sharing as r

HERE = Path(__file__).resolve().parent
PARENT = r.BASE/'agents/temporal_merges/q43_long_second_delayed_q21_native_v1/candidate_text.kmx'
PARENT_SHA = '0e4a525f98bc492ccfb5e05d04983eabc3bbd036e26e77a9bb244aabb77421da'
PEAKS = [[11040,11046],[11345,11351],[11728,11734],[11744,11753],
         [12095,12101],[12111,12120],[12454,12460],[12470,12479],
         [12813,12819],[12829,12838],[13172,13178],[13188,13197],
         [13531,13537],[13547,13556],[13890,13896],[13906,13915],
         [14249,14255],[14265,14274],[14738,14744],[14754,14763],[15190,15201]]


def product(a,b):
    ans=set()
    for x in a:
        for y in b:
            z=x|y
            if z in ans: ans.remove(z)
            else: ans.add(z)
    return ans


def targets(o):
    if o.kind in ('X','CX','CCX'): return {o.arguments[-1]}
    if o.kind in ('SWAP','CSWAP'): return set(o.arguments[-2:])
    if o.kind in ('HMR','R'): return {o.arguments[0]}
    return set()


def feedback(ops,h,pop):
    q,b=ops[h].arguments
    start=h+1
    if ops[start].kind!='PUSH_CONDITION' or ops[start].condition!=b: return None
    end=pop[start]
    states={f'q{i}':{1<<i} for i in range(44)}
    original={q:v.copy() for q,v in states.items()}
    phase=set()
    for o in ops[start+1:end]:
        if o.condition is not None: return None
        a=o.arguments
        if o.kind=='X':states[a[0]]^={0}
        elif o.kind=='CX':states[a[1]]^=states[a[0]]
        elif o.kind in ('Z','CZ','NEG'):
            value={0}
            for w in a:value=product(value,states[w])
            phase^=value
        else:return None
    if states!=original or any(m.bit_count()>2 or m>>(int(q[1:]))&1 for m in phase):return None
    quadratic={m for m in phase if m.bit_count()==2}
    variables=sorted({i for m in quadratic for i in range(44) if m>>i&1})
    if len(variables)>8 or not quadratic:return None
    # A constructive exact rank-two factorization; no heuristic rank claim.
    values=[sum(1<<variables[i] for i in range(len(variables)) if mask>>i&1) for mask in range(1,1<<len(variables))]
    for a in values:
        for b in values:
            if a>=b or not a&~b or not b&~a:continue
            actual=product({1<<i for i in range(44) if a>>i&1},{1<<i for i in range(44) if b>>i&1})
            if {m for m in actual if m.bit_count()==2}==quadratic:
                linear=phase^actual
                assert all(m.bit_count()<=1 for m in linear)
                return dict(interval=[start,end+1],polynomial=sorted(phase),factor_masks=[a,b],linear_remainder=sorted(linear),
                            controls=[f'q{i}' for i in range(44) if (a|b|sum(linear))>>i&1])
    return None


def find(program):
    ops=program.operations
    enclosing=[];stack=[];pops={}
    for i,o in enumerate(ops):
        enclosing.append(tuple(stack))
        if o.kind=='PUSH_CONDITION':stack.append(i)
        elif o.kind=='POP_CONDITION':pops[stack.pop()]=i
    assert not stack
    out=[]
    for h,o in enumerate(ops):
        if not 11040<=h<15445 or o.kind!='HMR' or enclosing[h] or o.condition:continue
        fb=feedback(ops,h,pops)
        if fb is None:continue
        q=o.arguments[0]
        previous=max((i for i in range(h) if q in targets(ops[i])),default=-1)
        if previous<0:continue
        unguarded=[i for i in range(previous,h) if q in ops[i].arguments and not enclosing[i] and ops[i].condition is None]
        if not unguarded:continue
        start=unguarded[-1]+1
        covered=[i for i,(a,b) in enumerate(PEAKS) if start<=a and b<=h]
        if not covered:continue
        reads=[i for i in range(start,h) if q in ops[i].arguments]
        if not reads:continue
        blocks={enclosing[i][0] if enclosing[i] else -1 for i in reads}
        if len(blocks)!=1 or -1 in blocks:continue
        block=next(iter(blocks));end=pops[block]
        if block<start or end>=h:continue
        if any(q in targets(ops[i]) for i in reads):continue
        controls=set(fb['controls'])
        if any(targets(o)&controls for o in ops[start:h]):continue
        if any(ops[i].kind in ('BIT_STORE0','BIT_STORE1','BIT_INVERT','HMR') and ops[block].condition in ops[i].arguments for i in range(block+1,end)):
            continue
        out.append(dict(id=len(out),owner=q,start=start,old_HMR=h,old_event=o.event,old_classical_owner=o.arguments[1],
                        reconstruction_block=[block,end+1],reconstruction_guard=ops[block].condition,
                        original_read_operations=reads,feedback=fb,covered_peak_ids=covered,
                        covered_peak_windows=[PEAKS[i] for i in covered],covered_peak_cuts=sum(PEAKS[i][1]-PEAKS[i][0] for i in covered),
                        actual_preparation_ANDs=1,full_value_identity_and_guard_probability_pending=True))
    return out


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True,type=Path);args=ap.parse_args()
    began=time.monotonic();assert r.sha(PARENT)==PARENT_SHA;assert not args.out.exists();args.out.mkdir(parents=True)
    program=r.Program(PARENT.read_text());plans=find(program)
    report=dict(notice=r.NOTICE,status='CONSTRUCTIVE_EARLY_CONDITIONAL_CARRY_BORROW_BINDINGS',source_sha256=r.sha(Path(__file__)),
                parent_native=str(PARENT.relative_to(r.BASE)),parent_sha256=PARENT_SHA,parent_expected_Toffolis='5837/4',
                declared_native_old_HMR_range=[11040,15445],plans=plans,plan_count=len(plans),
                union_peak_ids=sorted({i for p in plans for i in p['covered_peak_ids']}),
                original_peak_windows=PEAKS,no_complete_negative_scope_claimed=True,seconds=time.monotonic()-began)
    (args.out/'INDEX.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('plans','original_peak_windows')},indent=2))
    for p in plans:print(p['id'],p['owner'],p['start'],p['old_HMR'],p['reconstruction_block'],p['covered_peak_windows'],p['feedback']['factor_masks'])


if __name__=='__main__':main()
