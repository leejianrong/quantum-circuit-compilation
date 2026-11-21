# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Bounded, width-explicit own table synthesis; mathematical certificates only.

An own universal quadratic bank starts in unfilled output wires. Output bits
replace the bank gradually. Every input frame of a quadratic XOR is restored.
Dead bank helpers are X-measured and their complete high-address truth is added
to the existing deferred table-phase ledger. No quantum native code is emitted.
"""
from pathlib import Path
import argparse
import dataclasses
import hashlib
import json
import random
import resource
import signal
import sys
import time
from atomic_io import atomic_text

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'inputs'))
import codebook as cb

MODEL = 'phasefit_z1_K7_G4_m37_virtual_quadS2_36_12c0.json'
MODEL_SHA = '24fff823faa911afe93d02afc3ded0bbd156a210a85f1265c989a087f8fd1219'
CODE_SHA = '9c6073d78becea467d37805131fdcc572e530c72acef5664b08057ef883f17be'


def checked_model():
    for name, digest in [(MODEL, MODEL_SHA), ('codebook.py', CODE_SHA)]:
        assert hashlib.sha256((HERE/'inputs'/name).read_bytes()).hexdigest() == digest
    return json.loads((HERE/'inputs'/MODEL).read_text())


def raw_functions(framed=True):
    raw = cb.word_functions(range(128), 7)
    if not framed:
        return raw
    # Same physical root frame as the producer, followed by a wire reorder.
    return [raw[1], raw[2]^raw[5], raw[3]^raw[2]^(raw[1]&(raw[2]^raw[5])),
            raw[0], raw[2], raw[4], raw[6]]


def serialize(plan):
    return dataclasses.asdict(plan)


def restore(data):
    return cb.QuadraticCodePlan(data['width'], data['constant'], data['linear'],
                               tuple(map(tuple,data['edges'])),
                               tuple(map(tuple,data['products'])), data['product_linear'])


def make_bank(raw, bank):
    functions = list(raw)
    steps = []
    full = (1 << 128)-1
    for index, item in enumerate(bank['steps']):
        left,right=item['left'],item['right']
        truth=cb.parity_function(left, functions)&cb.parity_function(right,functions)
        edges=set()
        for i in cb.bits(left):
            for j in cb.bits(right):
                if i != j:
                    edge=tuple(sorted((i,j)))
                    if edge in edges: edges.remove(edge)
                    else: edges.add(edge)
        plan=cb.factor_polynomial(len(functions),False,left&right,edges)
        assert plan.and_count==1 and plan.evaluate_factored_functions(functions,full)==truth
        steps.append(dict(kind='bank', name=f'b{index}', inputs=[f'r{i}' for i in range(7)]+[f'b{i}' for i in range(index)],
                          truth=hex(truth), plan=serialize(plan), Toffolis=1))
        functions.append(truth)
    return functions[7:],steps


def rank_score(functions,targets):
    book=cb.Codebook(functions,128)
    represented=sum(book.span.solve(f) is not None for f in targets)
    return represented,len(book.span.pivots)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--name',required=True)
    ap.add_argument('--work-cap',type=int,default=18)
    ap.add_argument('--seed',type=int,default=0)
    ap.add_argument('--seconds',type=int,default=900)
    ap.add_argument('--rounds',type=int,default=32)
    ap.add_argument('--subspace-bits',type=int,default=7)
    ap.add_argument('--quick-trials',type=int,default=16)
    ap.add_argument('--kernel-trials',type=int,default=256)
    ap.add_argument('--refine-candidates',type=int,default=3)
    ap.add_argument('--unframed',action='store_true')
    ap.add_argument('--resume')
    args=ap.parse_args()
    resource.setrlimit(resource.RLIMIT_AS,(768*1024**2,768*1024**2))
    signal.alarm(args.seconds+10)
    began=time.monotonic(); rng=random.Random(args.seed)
    model=checked_model(); full=(1<<128)-1
    raw=raw_functions(not args.unframed)
    outputs=cb.word_functions(model['A'],13)+cb.word_functions(model['stored_slope'],4)
    omitted=cb.word_functions(model['stored_slope'],5)[4]
    assert omitted==outputs[12]^outputs[16]^(outputs[11]&outputs[16])
    bank=json.loads((HERE/'phase_bank7_seed0.json').read_text())
    helpers,steps=make_bank(raw,bank)
    live=[(f'b{i}',v) for i,v in enumerate(helpers)]
    remaining=list(range(17)); loaded=[]; total=len(helpers); peak=len(live)
    result_path=HERE/'search'/f'{args.name}.json'
    if args.resume:
        state=json.loads(Path(args.resume).read_text())
        assert state['model_sha256']==MODEL_SHA and state['framed_address']==(not args.unframed)
        live=[(i['name'],int(i['truth'],16)) for i in state['live']]
        steps=state['steps'];remaining=state['remaining'];loaded=state['loaded'];total=state['Toffolis'];peak=state['work_peak']

    def snapshot(status):
        result=dict(status=status,model=MODEL,model_sha256=MODEL_SHA,
                    codebook_source_sha256=CODE_SHA,framed_address=not args.unframed,
                    work_cap=args.work_cap,work_peak=peak,Toffolis=total,T=0,rotations=0,
                    outputs=17,omitted_H4_formula='A12 XOR H3 XOR (A11 AND H3)',
                    remaining=remaining,loaded=loaded,live=[dict(name=n,truth=hex(t)) for n,t in live],steps=steps,
                    seed=args.seed,seconds=time.monotonic()-began,
                    high_address_helper_debts_deferred=True,
                    final_table_phase_bank_Toffolis=11,
                    cleanup_scope='The separately priced shared 11-AND bank pays every pure-table helper/output phase from both loading intervals after the full original address is restored.',
                    logical_state_function_checks=True,physical_native_proof=False,official_verifier=False,
                    memory_guard_MiB=768,wall_limit_seconds=args.seconds)
        atomic_text(result_path,json.dumps(result,indent=2)+'\n')
        return result

    snapshot('RUNNING')
    while remaining:
        if time.monotonic()-began>=args.seconds:
            snapshot('BOUNDED_PARTIAL');break
        if len(live)>=args.work_cap:
            choices=[]
            for index,(name,truth) in enumerate(live):
                if not name.startswith('b'):continue
                funcs=raw+[t for k,(_,t) in enumerate(live) if k!=index]
                score=rank_score(funcs,[outputs[i] for i in remaining])
                choices.append((score,rng.random(),index))
            if not choices:raise AssertionError('No helper can be retired to make the target zero.')
            score,_,index=max(choices)
            name,truth=live.pop(index)
            steps.append(dict(kind='measure_bank',name=name,truth=hex(truth),Toffolis=0,
                              phase_debt='outcome AND exact truth(address), deferred to shared final bank',
                              remaining_quadratic_rank=score[1]))
        functions=raw+[t for _,t in live]
        inputs=[f'r{i}' for i in range(7)]+[n for n,_ in live]
        book=cb.Codebook(functions,128)
        candidates=[]
        for index in remaining:
            seed=rng.randrange(1<<30)
            plan=book.represent(outputs[index],trials=args.quick_trials,seed=seed)
            if plan is None:continue
            alt,meta=book.represent_kernel(outputs[index],trials=args.kernel_trials,seed=seed)
            if alt.and_count<plan.and_count:plan=alt
            candidates.append((plan.and_count,rng.random(),index,plan))
        if not candidates:
            snapshot('STUCK_NO_QUADRATIC_NEXT_OUTPUT');break
        candidates.sort(key=lambda t:t[:2]); refined=[]
        for _,tie,index,plan in candidates[:args.refine_candidates]:
            better=book.improve_preserving_kernel(plan,rounds=args.rounds,subspace_bits=args.subspace_bits,seed=rng.randrange(1<<30))
            assert better.and_count<=plan.and_count
            refined.append((better.and_count,tie,index,better))
        count,_,index,plan=min(refined,key=lambda t:t[:2])
        truth=outputs[index]
        assert plan.evaluate_functions(functions,full)==truth
        assert plan.evaluate_factored_functions(functions,full)==truth
        # Product input frames have distinct pivots and restore every variable.
        for left,right,i,j in plan.products:
            assert (left>>i)&1 and (right>>j)&1 and not (left>>j)&1 and not (right>>i)&1
        name=f'o{index}'; live.append((name,truth));loaded.append(index);remaining.remove(index)
        peak=max(peak,len(live)); assert peak<=args.work_cap
        total+=count
        steps.append(dict(kind='output',name=name,output_bit=index,inputs=inputs,truth=hex(truth),
                          plan=serialize(plan),Toffolis=count,work_owners=len(live),
                          quadratic_rank=len(book.span.pivots),exact_rows_checked=128,
                          CNOT_frames_restore_inputs=True))
        snapshot('RUNNING')
        print(json.dumps(dict(loaded=len(loaded),bit=index,Toffolis=count,total=total,work=len(live),seconds=time.monotonic()-began)),flush=True)
    else:
        # Clear any leftover pure-table bank helpers; output wires remain.
        for name,truth in list(live):
            if name.startswith('b'):
                steps.append(dict(kind='measure_bank',name=name,truth=hex(truth),Toffolis=0,
                                  phase_debt='outcome AND exact truth(address), deferred to shared final bank'))
                live.remove((name,truth))
        assert len(live)==17 and sorted(n for n,_ in live)==sorted(f'o{i}' for i in range(17))
        final=snapshot('COMPLETE_MATHEMATICAL_LOADER_NOT_NATIVE')
        print(json.dumps({k:final[k] for k in ('status','Toffolis','work_peak','seconds')}),flush=True)


if __name__=='__main__':main()
