# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Own exact six-input coefficient-loader synthesis, independent certificates.

Uses our pre-existing binary codebook algebra. Every affine frame retains all
64 input distinctions; all measured coordinates carry raw64 table truths.
The search result is a mathematical certificate until native emission/proof.
"""
import argparse,dataclasses,hashlib,json,random,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'fusion/runtime/work/c10/narrow/research/joint_loader'
sys.path.insert(0,str(OLD))
from bank_frontier import cb,serialize
from subspace_frontier import plan_expression,improve_coset,independent_complement
FULL=(1<<64)-1
NOTICE='Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.'

def affine_product(functions,left_truth,right_truth):
    span=cb.BinarySpan([FULL]+list(functions));left=span.solve(left_truth);right=span.solve(right_truth)
    assert left is not None and right is not None
    lc,rc=left&1,right&1;left>>=1;right>>=1
    linear=(right if lc else 0)^(left if rc else 0)^(left&right);edges=set()
    for a in cb.bits(left):
        for b in cb.bits(right):
            if a!=b:
                edge=tuple(sorted((a,b)))
                if edge in edges:edges.remove(edge)
                else:edges.add(edge)
    plan=cb.factor_polynomial(len(functions),bool(lc&rc),linear,edges)
    assert plan.and_count<=1 and plan.evaluate_factored_functions(functions,FULL)==left_truth&right_truth
    return plan

def distinct_rows(functions):
    return len({sum(((t>>row)&1)<<i for i,t in enumerate(functions)) for row in range(64)})

class Chart:
    def __init__(self,raw,work,steps,cap,rng):
        self.raw=list(raw);self.work=list(work);self.steps=steps;self.cap=cap;self.peak=len(work);self.rng=rng;self.ands=0
    def clean_affine(self):
        span=cb.BinarySpan([FULL]+self.raw);i=0
        while i<len(self.work):
            solution=span.solve(self.work[i])
            if solution is not None:
                self.steps.append(dict(kind='Clifford_zero_dependent_coordinate',index=i,truth=hex(self.work[i]),expression=solution,Toffolis=0));self.work.pop(i)
            else:span.add(self.work[i]);i+=1
    def frame(self,required,limit,*,label):
        self.clean_affine();old=list(self.work);offset=1+len(self.raw)
        fullspan=cb.BinarySpan([FULL]+self.raw+old);assert len(fullspan.pivots)==offset+len(old)
        selected=[];span=cb.BinarySpan([FULL]+self.raw)
        for truth in required:
            assert fullspan.solve(truth) is not None
            if span.add(truth):selected.append(truth)
        if len(selected)>limit:return False
        remaining=list(old)
        while len(selected)<min(limit,len(old)):
            candidates=[]
            for truth in remaining:
                if span.solve(truth) is not None:continue
                rank=len(cb.Codebook(self.raw+selected+[truth],64).span.pivots)
                candidates.append((rank,self.rng.random(),truth))
            if not candidates:break
            _,_,truth=max(candidates);selected.append(truth);assert span.add(truth);remaining.remove(truth)
        assert distinct_rows(self.raw+selected)==64,('NONINJECTIVE_RETIRED_CHART',label)
        rowspan=cb.BinarySpan();rows=[];truths=[]
        for truth in selected:
            expression=fullspan.solve(truth);assert rowspan.add(expression>>offset);rows.append(expression);truths.append(truth)
        for i,truth in enumerate(old):
            if rowspan.add(1<<i):rows.append(1<<(offset+i));truths.append(truth)
        assert len(rows)==len(old)
        for expression,truth in zip(rows,truths):assert cb.parity_function(expression,[FULL]+self.raw+old)==truth
        self.steps.append(dict(kind='Clifford_frame_then_HMR',label=label,affine_fixed_offset=offset,old_work=[hex(t)for t in old],full_affine_rows=rows,retained_count=len(selected),retained_truths=[hex(t)for t in selected],discarded_truths=[hex(t)for t in truths[len(selected):]],original_rows_distinguished_after=64,Toffolis=0))
        self.work=selected;return True
    def emit_plan(self,plan,functions,loaded_truths,target_truth):
        factors=[(cb.parity_function(left,functions),cb.parity_function(right,functions))for left,right,_,_ in plan.products]
        affine=(FULL if plan.constant else 0)^cb.parity_function(plan.product_linear,functions)
        accumulation=0;before=self.ands
        for stage,(left,right)in enumerate(factors):
            controls=[truth for pair in factors[stage:]for truth in pair]
            required=list(loaded_truths)+controls+[affine,accumulation]
            if self.frame(required,self.cap-1,label=f'product{stage}_new_target'):
                variables=self.raw+self.work;product=left&right;linear=cb.BinarySpan([FULL]+variables).solve(product)
                if linear is not None:self.steps.append(dict(kind='virtual_affine_product',truth=hex(product),expression=linear,Toffolis=0))
                else:
                    actual=affine_product(variables,left,right);assert actual.and_count==1
                    self.steps.append(dict(kind='CCX_new_coordinate',truth=hex(product),plan=serialize(actual),Toffolis=1));self.work.append(product);self.ands+=1;self.peak=max(self.peak,len(self.work))
            else:
                others=list(loaded_truths)+controls+[affine]
                assert cb.BinarySpan([FULL]+self.raw+others).solve(accumulation)is None
                assert self.frame([accumulation]+others,self.cap,label=f'product{stage}_accumulator');assert self.work[0]==accumulation
                variables=self.raw+self.work[1:];actual=affine_product(variables,left,right)
                self.steps.append(dict(kind='XOR_product_existing_coordinate',target_index=0,old_truth=hex(accumulation),product_truth=hex(left&right),plan=serialize(actual),Toffolis=actual.and_count));self.work[0]^=left&right;self.ands+=actual.and_count;self.clean_affine()
            accumulation^=left&right
        assert affine^accumulation==target_truth
        assert self.frame(list(loaded_truths)+[target_truth],self.cap,label='retain_complete_output')
        return self.ands-before

def small_plan(book,outputs,loaded,rng,rounds):
    linear=cb.BinarySpan([FULL]+list(book.functions))
    for mask in independent_complement(loaded,len(outputs)):
        expression=linear.solve(cb.parity_function(mask,outputs))
        if expression is not None:return cb.factor_polynomial(book.width,bool(expression&1),expression>>1,[]),mask
    span=cb.BinarySpan(book.columns);base=len(book.columns)
    for truth in outputs:span.add(truth)
    directions=cb.BinarySpan(loaded);expressions=[]
    for relation in span.nullspace:
        mask=relation>>base
        if mask and directions.add(mask):expressions.append((mask,relation&((1<<base)-1)))
    if not expressions:return None,None
    candidates=[]
    for mask,expression in expressions:
        plan=book.represent(cb.parity_function(mask,outputs),trials=3,seed=rng.randrange(1<<30))
        candidates.append((plan.and_count,rng.random(),mask,plan_expression(book,plan)))
    candidates.sort();best=None;outspan=cb.BinarySpan(outputs)
    for _,tie,anchor,expression in candidates[:2]:
        relations=list(book.span.nullspace)+[e for m,e in expressions if m!=anchor]
        plan=improve_coset(book,expression,relations,rounds=rounds,subspace_bits=5,seed=rng.randrange(1<<30))
        truth=plan.evaluate_factored_functions(book.functions,FULL);mask=outspan.solve(truth)
        assert mask is not None and cb.BinarySpan(loaded).solve(mask)is None
        candidate=plan.and_count,tie,plan,mask
        if best is None or candidate[:2]<best[:2]:best=candidate
    return best[2],best[3]

def synth(table,cap,fixed_bits,output_spec,seed=0,rounds=8,seconds=120):
    began=time.monotonic();original=cb.word_functions(range(64),6);reused=[i for i in range(6)if i not in fixed_bits]
    raw=[original[i]for i in fixed_bits];work=[original[i]for i in reused];steps=[];chart=Chart(raw,work,steps,cap,random.Random(seed))
    outputs=[cb.word_functions(table[key],max(bits)+1)[bit]for key,bits in output_spec for bit in bits]
    labels=[f'{key}{bit}'for key,bits in output_spec for bit in bits]
    # 3+3 monomial bank:8 products make the quadratic chart universal on64 rows.
    for a,b in [(0,1),(0,2),(1,2),(3,4),(3,5),(4,5)]:
        functions=chart.raw+chart.work;plan=affine_product(functions,original[a],original[b]);truth=original[a]&original[b]
        steps.append(dict(kind='bank',plan=serialize(plan),truth=hex(truth),Toffolis=1));chart.work.append(truth);chart.ands+=1
    for a,b,c in [(0,1,2),(3,4,5)]:
        functions=chart.raw+chart.work;plan=affine_product(functions,original[a]&original[b],original[c]);truth=original[a]&original[b]&original[c]
        steps.append(dict(kind='bank',plan=serialize(plan),truth=hex(truth),Toffolis=1));chart.work.append(truth);chart.ands+=1
    chart.peak=max(chart.peak,len(chart.work));assert chart.peak<=cap
    assert len(cb.Codebook(chart.raw+chart.work,64).span.pivots)==64
    loaded=[];summaries=[];status='RUNNING'
    while len(loaded)<len(outputs):
        if time.monotonic()-began>seconds:status='BOUNDED_PARTIAL';break
        truths=[cb.parity_function(mask,outputs)for mask in loaded]
        assert chart.frame(truths,cap-1,label='reserve_output')
        book=cb.Codebook(chart.raw+chart.work,64);plan,mask=small_plan(book,outputs,loaded,chart.rng,rounds)
        if plan is None:status='STUCK';break
        truth=cb.parity_function(mask,outputs);charge=chart.emit_plan(plan,book.functions,truths,truth);loaded.append(mask)
        summaries.append(dict(mask=mask,charge=charge,total=chart.ands,work=len(chart.work)))
        print(json.dumps(summaries[-1]),flush=True)
    else:
        span=cb.BinarySpan([FULL]+chart.raw);basis=[];indices=[]
        for i,truth in enumerate(outputs):
            if span.add(truth):basis.append(truth);indices.append(i)
        assert chart.frame(basis,len(basis),label='final_output_basis')and chart.work==basis
        expressions=[];span=cb.BinarySpan([FULL]+chart.raw+basis)
        for truth in outputs:
            e=span.solve(truth);assert e is not None;expressions.append(e)
        steps.append(dict(kind='materialize_final_outputs',basis_output_indices=indices,output_expressions=expressions,Toffolis=0))
        chart.peak=max(chart.peak,len(outputs));assert chart.peak<=cap;status='COMPLETE_MATHEMATICAL_LOADER_NOT_NATIVE'
    return dict(notice=NOTICE,status=status,rows=64,raw_address_bits=6,fixed_address_bits=fixed_bits,reusable_input_bits=reused,output_labels=labels,output_truths=[hex(t)for t in outputs],table=table,table_sha256=hashlib.sha256(json.dumps(table,sort_keys=True).encode()).hexdigest(),work_cap=cap,work_peak=chart.peak,Toffolis=chart.ands,steps=steps,output_summaries=summaries,seed=seed,seconds=time.monotonic()-began,native_proof=False,official_panels_run=0)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--table',type=Path,required=True);ap.add_argument('--cap',type=int,default=19);ap.add_argument('--fixed',default='0,1,2,3,4,5');ap.add_argument('--a-bits',type=int,default=13);ap.add_argument('--s-bits',default='0,1,2,3,4');ap.add_argument('--seed',type=int,default=0);ap.add_argument('--seconds',type=int,default=120);ap.add_argument('--rounds',type=int,default=8);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();table=json.loads(a.table.read_text());spec=[('A',list(range(a.a_bits))),('S',list(map(int,a.s_bits.split(','))))]
    result=synth(table,a.cap,list(map(int,a.fixed.split(','))),spec,a.seed,a.rounds,a.seconds);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k not in ('table','output_truths','steps','output_summaries')},indent=2),flush=True)
if __name__=='__main__':main()
