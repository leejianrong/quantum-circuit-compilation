# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Derive the exact universal phase debt of omitting one long q21 packet.

Quantum inputs at the packet entry are independent symbolic variables except
the proven clean q21. Classical controls are their actual native HMR ANFs.
Only q21 creation, target toggles, diagonal reads, and its paired phase-only
q43 conjugations are suppressed. The original q21 HMR remains on zero.
"""
import argparse
import gzip
import json
import time
from collections import Counter
from pathlib import Path
from temporal_core import NOTICE, Program, captures, sha, bits
from lift_q43_joint_overflow_C_fibers import atomic

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
QMASK=(1<<44)-1


def add(*polys):
    out=set()
    for p in polys:out.symmetric_difference_update(p)
    return frozenset(out)


def mul(a,b):
    out=set()
    for x in a:
        for y in b:
            z=x|y
            if z in out:out.remove(z)
            else:out.add(z)
    return frozenset(out)


def replay(p,state,a,b,omit):
    state=dict(state);one=frozenset([0]);stack=[one];phase=frozenset();skipped=[]
    for i in range(a,b):
        o=p.operations[i];k=o.kind;aa=o.arguments
        guard=stack[-1] if o.condition is None else mul(stack[-1],state[o.condition])
        if k=='PUSH_CONDITION':stack.append(guard);continue
        if k=='POP_CONDITION':stack.pop();continue
        skip=(k in ('CCX','CX','X') and aa[-1]=='q21') or (k in ('Z','CZ','CCZ') and 'q21' in aa) or i in (19069,19071)
        if omit and skip:skipped.append(i);continue
        if k in ('X','BIT_INVERT'):state[aa[0]]=add(state[aa[0]],guard)
        elif k=='CX':state[aa[1]]=add(state[aa[1]],mul(guard,state[aa[0]]))
        elif k=='CCX':state[aa[2]]=add(state[aa[2]],mul(guard,mul(state[aa[0]],state[aa[1]])))
        elif k in ('BIT_STORE0','BIT_STORE1'):
            desired=one if k=='BIT_STORE1' else frozenset()
            state[aa[0]]=add(state[aa[0]],mul(guard,add(state[aa[0]],desired)))
        elif k in ('Z','CZ','CCZ','NEG'):
            value=guard
            for q in aa:value=mul(value,state[q])
            phase=add(phase,value)
        elif k=='HMR':
            outcome=frozenset([1<<(44+o.event)])
            phase=add(phase,mul(guard,mul(outcome,state[aa[0]])))
            state[aa[0]]=add(state[aa[0]],mul(guard,state[aa[0]]))
            state[aa[1]]=add(state[aa[1]],mul(guard,add(state[aa[1]],outcome)))
        else:raise AssertionError((i,k))
    assert stack==[one]
    return state,phase,skipped


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();args.out.mkdir(exist_ok=False);started=time.monotonic()
    native=HERE/'q43_late_short_affine_native_v1/candidate_text.kmx'
    assert sha(native)=='70eaa20cbe8a658ecaa634eb42d6c9fc521310ef385300be124cf34e397fea7a'
    p=Program(native.read_text());a,b=18941,19140
    cap=captures(p,{a},[1],formal=True,include_classical=True)[a]
    assert not cap['q21']
    initial={q:frozenset([1<<int(q[1:])]) if q.startswith('q') else frozenset(m<<44 for m,v in poly.items() if v)
             for q,poly in cap.items()}
    initial['q21']=frozenset()
    old,oldphase,_=replay(p,initial,a,b,False)
    new,newphase,skipped=replay(p,initial,a,b,True)
    assert old==new,'OMISSION_CHANGED_ENDPOINT_VALUES'
    debt=oldphase^newphase;by_hmr={}
    for m in debt:
        h=m>>44;q=m&QMASK
        by_hmr.setdefault(h,[]).append(q)
    records=[]
    for h,terms in sorted(by_hmr.items()):
        record=dict(HMR_events=list(bits(h)),quantum_terms=[list(bits(m)) for m in sorted(terms)],
                    quantum_degree_histogram=dict(Counter(m.bit_count() for m in terms)))
        records.append(record)
    hmr=p.operations[b-1]
    assert hmr.kind=='HMR' and hmr.arguments==('q21','b197')
    report=dict(notice=NOTICE,status='UNIVERSAL_VALUE_CORRECT_VIRTUAL_PACKET_WITH_EXACT_PHASE_DEBT',
                numerical_verification='AGENT_VERIFIED_ROOT_REPLAY_PENDING',qualified=False,
                source_sha256=sha(__file__),native_sha256=sha(native),interval=[a,b],
                initial_quantum_variables='All44 literal owners, with q21 fixed0; all others freely independent.',
                actual_native_classical_HMR_ANFs=True,old_and_new_endpoint_values_identical=True,
                skipped_operations=skipped,original_HMR_kept=dict(operation=b-1,event=hmr.event,outcome='b197'),
                phase_debt_terms=len(debt),HMR_coefficient_count=len(by_hmr),
                quantum_degree_histogram=dict(Counter((m&QMASK).bit_count() for m in debt)),
                coefficients=records,actual_phase_repair_not_yet_synthesized=True,
                raw_phase_debt_monomial_hex=[hex(m) for m in sorted(debt)],
                seconds=time.monotonic()-started)
    atomic(args.out/'REPORT.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('coefficients','raw_phase_debt_monomial_hex')}),flush=True)
    print(json.dumps([dict(events=r['HMR_events'],degrees=r['quantum_degree_histogram']) for r in records]),flush=True)


if __name__=='__main__':main()
