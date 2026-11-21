# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Exact own width-bounded joint loader with freely chosen output XOR basis.

Search is heuristic; every emitted mathematical XOR/AND plan and final basis is
checked on all128 original model rows. This does not emit a native circuit.
"""
from pathlib import Path
import argparse
import dataclasses
import json
import random
import resource
import signal
import subprocess
import time
from bank_frontier import checked_model,raw_functions,make_bank,serialize,HERE,MODEL,MODEL_SHA,CODE_SHA,cb
from atomic_io import atomic_text


def product_subspace(book,targets,*,products,trials,seconds,seed):
    binary=HERE/'random_product_subspace.bin'
    if not binary.exists():
        subprocess.run(['g++','-std=c++17','-O3',str(HERE/'random_product_subspace.cpp'),'-o',str(binary)],check=True,timeout=30)
    text=f'{book.width} {len(targets)} {products} {trials} {seed} {seconds}\n'
    text+='\n'.join(hex(v) for v in book.functions)+'\n'
    text+='\n'.join(hex(v) for v in targets)+'\n'
    answer=subprocess.run([str(binary)],input=text,text=True,capture_output=True,check=True,timeout=seconds+4).stdout.split()
    if not answer or answer[0]!='FOUND':return None,dict(status=answer[0] if answer else 'EMPTY',trials=int(answer[1]) if len(answer)>1 else 0)
    targetmask=int(answer[2]);factors=list(map(int,answer[3:]));assert len(factors)==products
    columns=[book.full]+list(book.functions)
    columns += [cb.parity_function(left,book.functions)&right for left in factors for right in book.functions]
    target=cb.parity_function(targetmask,targets);solution=cb.BinarySpan(columns).solve(target);assert solution is not None
    constant=bool(solution&1);linear=(solution>>1)&((1<<book.width)-1);edges=set()
    for j,left in enumerate(factors):
        right=(solution>>(1+book.width+j*book.width))&((1<<book.width)-1)
        for a in cb.bits(left):
            for b in cb.bits(right):
                if a==b:linear^=1<<a
                else:
                    edge=tuple(sorted((a,b)))
                    if edge in edges:edges.remove(edge)
                    else:edges.add(edge)
    plan=cb.factor_polynomial(book.width,constant,linear,edges)
    assert plan.and_count<=products and plan.evaluate_factored_functions(book.functions,book.full)==target
    return plan,dict(status='FOUND',trials=int(answer[1]),left_factors=factors,target_combination=targetmask)


def plan_expression(book,plan):
    lookup={m:i for i,m in enumerate(book.monomials)};expression=int(plan.constant)
    for bit in cb.bits(plan.linear):expression^=1<<lookup[(bit,)]
    for edge in plan.edges:expression^=1<<lookup[edge]
    return expression


def adjacency(book,expression):
    rows=[0]*book.width
    for index in cb.bits(expression):
        monomial=book.monomials[index]
        if len(monomial)==2:
            a,b=monomial;rows[a]^=1<<b;rows[b]^=1<<a
    return rows


def products_below(matrix,limit):
    rows=list(matrix);remaining=(1<<len(rows))-1;count=0
    while remaining:
        i=(remaining&-remaining).bit_length()-1;remaining^=1<<i
        partners=rows[i]&remaining
        if not partners:continue
        j=(partners&-partners).bit_length()-1;remaining^=1<<j;count+=1
        if count>=limit:return count
        ri,rj=rows[i],rows[j]
        for k in cb.bits(remaining):
            old=rows[k]
            if old>>j&1:rows[k]^=ri
            if old>>i&1:rows[k]^=rj
    return count


def improve_coset(book,expression,relations,*,rounds,subspace_bits,seed):
    """Same own quadratic kernel descent, with target-XOR basis changes allowed.

The caller retains one anchor target coordinate, so the zero-target polynomial
cannot be reached. Every move is either a true zero relation or a different
unloaded target direction. Actual target truth is recovered after the search.
"""
    rng=random.Random(seed);width=book.width
    current=expression;best=book.decode_expression(current).and_count
    relation_matrices=[adjacency(book,r) for r in relations]
    for _ in range(rounds):
        matrix=adjacency(book,current);kernel=cb.BinarySpan(matrix).nullspace
        if not kernel:break
        k=min(len(kernel),max(1,width//2));mixed=list(kernel)
        for __ in range(3*len(mixed)):
            if len(mixed)<2:break
            a,b=rng.sample(range(len(mixed)),2);mixed[a]^=mixed[b]
        rng.shuffle(mixed);columns=[]
        for rmat in relation_matrices:
            column=0
            for i,vec in enumerate(mixed[:k]):
                value=sum(((row&vec).bit_count()&1)<<bit for bit,row in enumerate(rmat))
                column|=value<<(width*i)
            columns.append(column)
        moves=[]
        while k>=1:
            mask=(1<<(width*k))-1;moves=cb.BinarySpan([c&mask for c in columns]).nullspace
            if len(moves)>=3:break
            k-=1
        if not moves:continue
        if len(moves)>subspace_bits:
            compressed=[];span=cb.BinarySpan()
            while len(compressed)<subspace_bits:
                coefficients=rng.getrandbits(len(moves))
                if not coefficients or not span.add(coefficients):continue
                value=0
                for bit in cb.bits(coefficients):value^=moves[bit]
                compressed.append(value)
            moves=compressed
        deltas=[];delta_rows=[]
        for move in moves:
            value=0
            for bit in cb.bits(move):value^=relations[bit]
            deltas.append(value);delta_rows.append(adjacency(book,value))
        trial=current;rows=list(matrix);roundbest=best;roundexpr=current
        for step in range(1,1<<len(moves)):
            changed=(step&-step).bit_length()-1;trial^=deltas[changed]
            rows=[row^delta for row,delta in zip(rows,delta_rows[changed])]
            score=products_below(rows,roundbest)
            if score<roundbest:roundbest=score;roundexpr=trial
        if roundbest<best:
            best=roundbest;current=roundexpr
            if best==0:break
    plan=book.decode_expression(current)
    assert plan.and_count==best
    return plan


def independent_complement(loaded,width):
    span=cb.BinarySpan(loaded);out=[]
    for bit in range(width):
        if span.add(1<<bit):out.append(1<<bit)
    assert len(loaded)+len(out)==width
    return out


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',required=True)
    ap.add_argument('--work-cap',type=int,default=18);ap.add_argument('--seed',type=int,default=0)
    ap.add_argument('--seconds',type=int,default=900);ap.add_argument('--rounds',type=int,default=64)
    ap.add_argument('--subspace-bits',type=int,default=7);ap.add_argument('--anchors',type=int,default=3)
    ap.add_argument('--factor-trials',type=int,default=0);ap.add_argument('--factor-seconds',type=float,default=3)
    ap.add_argument('--factor-count',type=int,default=4)
    ap.add_argument('--factor-fallback',type=int,default=0)
    ap.add_argument('--bank-size',type=int,default=11)
    ap.add_argument('--unframed',action='store_true');ap.add_argument('--bits',default=','.join(map(str,range(17))))
    args=ap.parse_args();resource.setrlimit(resource.RLIMIT_AS,(768*1024**2,768*1024**2));signal.alarm(args.seconds+10)
    began=time.monotonic();rng=random.Random(args.seed);model=checked_model();raw=raw_functions(not args.unframed)
    alloutputs=cb.word_functions(model['A'],13)+cb.word_functions(model['stored_slope'],4)
    outbits=list(map(int,args.bits.split(',')));outputs=[alloutputs[i] for i in outbits];width=len(outputs)
    outspan=cb.BinarySpan(outputs);assert len(outspan.pivots)==width
    bank=json.loads((HERE/'phase_bank7_seed0.json').read_text());bank['steps']=bank['steps'][:args.bank_size]
    helpers,steps=make_bank(raw,bank)
    live=[(f'b{i}',v) for i,v in enumerate(helpers)];loaded=[];total=len(helpers);peak=len(live)
    path=HERE/'search'/f'{args.name}.json'

    def snapshot(status):
        result=dict(status=status,model=MODEL,model_sha256=MODEL_SHA,codebook_source_sha256=CODE_SHA,
                    framed_address=not args.unframed,work_cap=args.work_cap,work_peak=peak,
                    output_bits=outbits,loaded_masks=loaded,initial_bank_size=args.bank_size,Toffolis=total,T=0,rotations=0,
                    live=[dict(name=n,truth=hex(t)) for n,t in live],steps=steps,seed=args.seed,seconds=time.monotonic()-began,
                    helper_HMR_debts='Pure table debts; repay using separately priced final bank or a certified earlier full-rank table cut.',
                    output_basis_conversion='Invertible Clifford CNOT/SWAP frame; no Toffolis or additional quantum owners.',
                    physical_native_proof=False,official_verifier=False,memory_guard_MiB=768,wall_limit_seconds=args.seconds)
        atomic_text(path,json.dumps(result,indent=2)+'\n');return result
    snapshot('RUNNING')
    while len(loaded)<width:
        if time.monotonic()-began>=args.seconds:snapshot('BOUNDED_PARTIAL');break
        complement=independent_complement(loaded,width)
        if len(live)>=args.work_cap:
            candidates=[]
            for index,(name,truth) in enumerate(live):
                if not name.startswith('b'):continue
                book=cb.Codebook(raw+[t for k,(_,t) in enumerate(live) if k!=index],128)
                count=sum(book.span.solve(cb.parity_function(mask,outputs)) is not None for mask in complement)
                candidates.append(((count,len(book.span.pivots)),rng.random(),index))
            if not candidates:raise AssertionError('No helper available for next target slot.')
            _,_,index=max(candidates);name,truth=live.pop(index)
            steps.append(dict(kind='measure_bank',name=name,truth=hex(truth),Toffolis=0,phase_deferred=True))
        functions=raw+[t for _,t in live];inputs=[f'r{i}' for i in range(7)]+[n for n,_ in live]
        book=cb.Codebook(functions,128);expressions=[]
        intersection=cb.BinarySpan(book.columns);base=len(book.columns)
        for truth in outputs:intersection.add(truth)
        direction_span=cb.BinarySpan(loaded)
        for relation in intersection.nullspace:
            mask=relation>>base
            if mask and direction_span.add(mask):expressions.append((mask,relation&((1<<base)-1)))
        if not expressions:snapshot('STUCK_NO_QUADRATIC_NEW_DIRECTION');break
        # Start from easiest ordinary representations, then allow every other
        # target coordinate to change freely during rank reduction.
        ordinary=[]
        for mask,expression in expressions:
            plan=book.represent(cb.parity_function(mask,outputs),trials=16,seed=rng.randrange(1<<30))
            ordinary.append((mask,plan_expression(book,plan)))
        candidates=sorted(ordinary,key=lambda pair:(book.decode_expression(pair[1]).and_count,rng.random()))
        best=None
        for mask,expression in candidates[:args.anchors]:
            relations=list(book.span.nullspace)+[e for m,e in expressions if m!=mask]
            plan=improve_coset(book,expression,relations,rounds=args.rounds,subspace_bits=args.subspace_bits,seed=rng.randrange(1<<30))
            truth=plan.evaluate_functions(functions,(1<<128)-1)
            assert truth==plan.evaluate_factored_functions(functions,(1<<128)-1)
            targetmask=outspan.solve(truth)
            assert targetmask is not None and cb.BinarySpan(loaded).solve(targetmask) is None
            choice=(plan.and_count,rng.random(),plan,truth,targetmask)
            if best is None or choice[:2]<best[:2]:best=choice
        factor_meta=[]
        for factor_count in [args.factor_count]+([args.factor_fallback] if args.factor_fallback else []):
            if args.factor_trials and best[0]>factor_count:
                plan,meta=product_subspace(book,[cb.parity_function(m,outputs) for m in complement],products=factor_count,trials=args.factor_trials,seconds=args.factor_seconds,seed=rng.randrange(1<<30))
                factor_meta.append(dict(products=factor_count,**meta))
                if plan is not None:
                    truth=plan.evaluate_factored_functions(functions,(1<<128)-1);targetmask=outspan.solve(truth)
                    assert targetmask is not None and cb.BinarySpan(loaded).solve(targetmask) is None
                    choice=(plan.and_count,rng.random(),plan,truth,targetmask)
                    if choice[:2]<best[:2]:best=choice
        count,_,plan,truth,targetmask=best
        name=f'o{len(loaded)}';loaded.append(targetmask);live.append((name,truth));peak=max(peak,len(live));assert peak<=args.work_cap
        total+=count
        steps.append(dict(kind='output_basis',name=name,target_mask=targetmask,inputs=inputs,truth=hex(truth),plan=serialize(plan),Toffolis=count,work_owners=len(live),exact_rows_checked=128,CNOT_frames_restore_inputs=True,factor_search=factor_meta))
        snapshot('RUNNING');print(json.dumps(dict(loaded=len(loaded),mask=targetmask,Toffolis=count,total=total,work=len(live),seconds=time.monotonic()-began)),flush=True)
    else:
        for name,truth in list(live):
            if name.startswith('b'):
                steps.append(dict(kind='measure_bank',name=name,truth=hex(truth),Toffolis=0,phase_deferred=True));live.remove((name,truth))
        inverse=cb.BinarySpan(loaded);rows=[]
        for bit in range(width):
            expression=inverse.solve(1<<bit);assert expression is not None
            truth=cb.parity_function(expression,[t for _,t in live]);assert truth==outputs[bit]
            rows.append(expression)
        steps.append(dict(kind='output_Clifford_basis_conversion',input_names=[n for n,_ in live],output_bits=outbits,matrix_rows=rows,Toffolis=0,extra_helpers=0,exact_rows_checked=128))
        final=snapshot('COMPLETE_MATHEMATICAL_LOADER_NOT_NATIVE')
        print(json.dumps({k:final[k] for k in ('status','Toffolis','work_peak','seconds')}),flush=True)


if __name__=='__main__':main()
