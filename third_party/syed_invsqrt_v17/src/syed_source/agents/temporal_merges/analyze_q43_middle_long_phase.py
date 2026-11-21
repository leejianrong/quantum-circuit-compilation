# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Universal virtual-q21 value and phase contract for the105-cut middle packet."""
import argparse
import json
from collections import Counter
from pathlib import Path
from temporal_core import NOTICE, Program, captures, sha, bits
from analyze_q43_long_virtual_phase import add,mul,QMASK
from lift_q43_joint_overflow_C_fibers import atomic

HERE=Path(__file__).resolve().parent
TRANSFER=['CX q43 q30','CX q34 q43','CCX q43 q30 q0','CX q34 q0','CX q34 q43','CX q43 q30']


def replay(p,initial,a,b,omit):
    state=dict(initial);one=frozenset([0]);stack=[one];phase=frozenset();skipped=[]
    def act(o,guard):
        nonlocal phase
        k,aa=o.kind,o.arguments
        if k in ('X','BIT_INVERT'):state[aa[0]]=add(state[aa[0]],guard)
        elif k=='CX':state[aa[1]]=add(state[aa[1]],mul(guard,state[aa[0]]))
        elif k=='CCX':state[aa[2]]=add(state[aa[2]],mul(guard,mul(state[aa[0]],state[aa[1]])))
        elif k in ('Z','CZ','CCZ','NEG'):
            value=guard
            for q in aa:value=mul(value,state[q])
            phase=add(phase,value)
        elif k=='HMR':
            outcome=frozenset([1<<(44+o.event)])
            phase=add(phase,mul(guard,mul(outcome,state[aa[0]])))
            state[aa[0]]=add(state[aa[0]],mul(guard,state[aa[0]]))
            state[aa[1]]=add(state[aa[1]],mul(guard,add(state[aa[1]],outcome)))
        else:raise AssertionError(k)
    for i in range(a,b):
        o=p.operations[i];k,aa=o.kind,o.arguments
        guard=stack[-1] if o.condition is None else mul(stack[-1],state[o.condition])
        if k=='PUSH_CONDITION':stack.append(guard);continue
        if k=='POP_CONDITION':stack.pop();continue
        if omit and i==16636:
            for new in Program('\n'.join(TRANSFER)).operations:act(new,guard)
            continue
        skip=(k in ('CCX','CX','X') and aa[-1]=='q21') or (k in ('Z','CZ','CCZ') and 'q21' in aa)
        if omit and skip:skipped.append(i);continue
        act(o,guard)
    assert stack==[one]
    return state,phase,skipped


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();args.out.mkdir(exist_ok=False)
    native=HERE/'q43_late_short_affine_native_v1/candidate_text.kmx'
    assert sha(native)=='70eaa20cbe8a658ecaa634eb42d6c9fc521310ef385300be124cf34e397fea7a'
    p=Program(native.read_text());a,b=16576,16691
    cap=captures(p,{a},[1],formal=True,include_classical=True)[a];assert not cap['q21']
    initial={q:frozenset([1<<int(q[1:])]) if q.startswith('q') else frozenset(m<<44 for m,v in poly.items() if v) for q,poly in cap.items()}
    initial['q21']=frozenset()
    old,op,_=replay(p,initial,a,b,False);new,np,skipped=replay(p,initial,a,b,True)
    assert old==new,'UNIVERSAL_ENDPOINT_VALUES_DIFFER'
    debt=op^np;by={}
    for m in debt:by.setdefault(m>>44,[]).append(m&QMASK)
    future=p.operations[b-1].event
    assert p.operations[b-1].arguments==('q21','b978')
    # The omitted value at the final frame is a free quadratic, so the original
    # HMR phase can be repaid without undoing the nonlinear q0 transfer.
    end_factor_A=add(new['q43'],new['q34']);end_factor_B=add(new['q30'],new['q43'],new['q36'])
    end_value=mul(new['b359'],add(mul(end_factor_A,end_factor_B),new['q34']))
    assert mul(frozenset([1<<(44+future)]),end_value)==frozenset(m for m in debt if (m>>(44+future))&1)
    report=dict(notice=NOTICE,status='UNIVERSAL_MIDDLE_LONG_VALUE_AND_PHASE_CONTRACT',
        numerical_verification='AGENT_VERIFIED_ROOT_REPLAY_PENDING',qualified=False,
        source_sha256=sha(__file__),native_sha256=sha(native),interval=[a,b],skipped_operations=skipped,
        direct_value_transfer_operation=16636,direct_value_transfer_gates=TRANSFER,
        old_and_new_universal_values_equal=True,phase_debt_terms=len(debt),
        future_HMR_event=future,future_HMR_outcome='b978',
        free_future_phase_formula='b359*b978*((q43+q34)*(q30+q43+q36)+q34)',
        free_future_phase_verified_in_endpoint_coordinates=True,
        quantum_degree_histogram=dict(Counter((m&QMASK).bit_count() for m in debt)),
        coefficients=[dict(HMR_events=list(bits(h)),quantum_terms=[list(bits(q)) for q in sorted(terms)],
                           degree_histogram=dict(Counter(q.bit_count() for q in terms))) for h,terms in sorted(by.items())],
        raw_phase_debt_monomial_hex=[hex(m) for m in sorted(debt)],actual_old_phase_repair_pending=True)
    atomic(args.out/'REPORT.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('coefficients','raw_phase_debt_monomial_hex')}))
    print(json.dumps([dict(events=c['HMR_events'],degrees=c['degree_histogram']) for c in report['coefficients']]))


if __name__=='__main__':main()
