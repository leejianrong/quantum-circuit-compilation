# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Native emission and all-branch64-row component proof of own loader certificates."""
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np
from loader64 import cb,FULL,NOTICE,serialize
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'fusion'))
import precision_sensitivity as ps
from root11_unit import checker

def plan(data):return cb.QuadraticCodePlan(data['width'],data['constant'],data['linear'],tuple(map(tuple,data['edges'])),tuple(map(tuple,data['products'])),data['product_linear'])
def xor(b,variables,target,expression):
    if expression&1:b.x(target)
    for i in cb.bits(expression>>1):b.cx(variables[i],target)
def frame(b,fixed,work,rows):
    offset=1+len(fixed);matrix=[row>>offset for row in rows];ops=[];n=len(work)
    for col in range(n):
        pivot=next(row for row in range(col,n)if matrix[row]>>col&1)
        if pivot!=col:matrix[pivot],matrix[col]=matrix[col],matrix[pivot];ops.append(('swap',pivot,col))
        for row in range(n):
            if row!=col and matrix[row]>>col&1:matrix[row]^=matrix[col];ops.append(('cx',col,row))
    assert matrix==[1<<i for i in range(n)]
    for kind,i,j in reversed(ops):
        if kind=='cx':b.cx(work[i],work[j])
        else:b.cx(work[i],work[j]);b.cx(work[j],work[i]);b.cx(work[i],work[j])
    for target,row in zip(work,rows):xor(b,fixed,target,row&((1<<offset)-1))

class Debts:
    def __init__(self):self.pending=[];self.recorded=0
    def erase(self,b,q,truth,free=True):
        m=b.alloc_bits(1)[0];b.hmr(q,m);self.pending.append((m,truth));self.recorded+=1
        if free:b.free(q)
    def flush(self,b,variables,functions):
        book=cb.Codebook(functions,64);assert len(book.span.pivots)==64
        for m,truth in self.pending:
            expression=book.span.solve(truth);assert expression is not None
            p=book.decode_expression(expression);assert p.evaluate_functions(functions,FULL)==truth
            cb.emit_phase(b,variables,m,p);b.free(m)
        self.pending=[]

def emit(b,address,data,debts):
    assert data['status']=='COMPLETE_MATHEMATICAL_LOADER_NOT_NATIVE'
    fixed=[address[i]for i in data['fixed_address_bits']];work=[address[i]for i in data['reusable_input_bits']]
    cap=data['work_cap'];available=list(b.alloc_qubits(cap-len(work)));count=0
    for item in data['steps']:
        kind=item['kind']
        if kind in ('bank','CCX_new_coordinate'):
            q=available.pop(0);p=plan(item['plan']);cb.emit_xor(b,fixed+work,q,p);work.append(q);count+=p.and_count
        elif kind=='Clifford_zero_dependent_coordinate':
            i=item['index'];q=work[i];xor(b,fixed+work[:i],q,item['expression']);work.pop(i);available.append(q)
        elif kind=='Clifford_frame_then_HMR':
            frame(b,fixed,work,item['full_affine_rows']);keep=item['retained_count']
            for q,truth in zip(work[keep:],item['discarded_truths']):debts.erase(b,q,int(truth,16),free=False);available.append(q)
            work=work[:keep]
        elif kind=='virtual_affine_product':pass
        elif kind=='XOR_product_existing_coordinate':
            p=plan(item['plan']);cb.emit_xor(b,fixed+work[1:],work[0],p);count+=p.and_count
        elif kind=='materialize_final_outputs':
            outputs=[None]*len(item['output_expressions'])
            for i,q in zip(item['basis_output_indices'],work):outputs[i]=q
            for i,expression in enumerate(item['output_expressions']):
                if outputs[i]is None:q=available.pop(0);xor(b,fixed+work,q,expression);outputs[i]=q
            work=outputs
        else:raise ValueError(kind)
        assert len(work)+len(available)==cap
    for q in available:b.free(q)
    assert count==data['Toffolis'];return work

def decode(b,address,outputs,data,debts):
    original=cb.word_functions(range(64),6);truths=list(map(lambda t:int(t,16),data['output_truths']))
    missing=list(data['reusable_input_bits']);variables=[q for i,q in enumerate(address)if i not in missing]+outputs
    functions=[t for i,t in enumerate(original)if i not in missing]+truths
    reports=[]
    while missing:
        book=cb.Codebook(functions,64);choices=[]
        for i in missing:
            p=book.represent(original[i],trials=64,seed=i+100)
            if p is not None:
                p=book.improve_preserving_kernel(p,rounds=24,subspace_bits=6,seed=i+400);choices.append((p.and_count,i,p))
        assert choices,('root_decoder_not_quadratic',missing)
        _,i,p=min(choices,key=lambda row:row[:2]);q=b.alloc_qubits(1)[0];cb.emit_xor(b,variables,q,p);address[i]=q
        variables.append(q);functions.append(original[i]);missing.remove(i);reports.append(dict(bit=i,Toffolis=p.and_count,plan=serialize(p)))
    return reports

def cleanup(b,address,outputs,data,debts):
    original=cb.word_functions(range(64),6)
    for q,truth in zip(outputs,data['output_truths']):debts.erase(b,q,int(truth,16))
    helpers=[];functions=list(original);variables=list(address);products=[]
    for a,c in [(0,1),(0,2),(1,2),(3,4),(3,5),(4,5),(6,2),(9,5)]:
        q=b.alloc_qubits(1)[0];b.ccx(variables[a],variables[c],q);helpers.append(q);products.append((a,c,q));variables.append(q);functions.append(functions[a]&functions[c])
    debts.flush(b,variables,functions)
    for a,c,q in reversed(products):b.del_and(variables[a],variables[c],q);b.free(q)

def cleanup_certificate(b,address,outputs,data,debts,certificate):
    assert certificate['loader_table_sha256']==data['table_sha256']
    fs=cb.word_functions(range(64),6)+[int(t,16)for t in data['output_truths']]
    debts.flush(b,list(address)+list(outputs),fs)
    wires={f'r{i}':q for i,q in enumerate(address)};wires.update({f'o{i}':q for i,q in enumerate(outputs)})
    count=0
    for item in certificate['steps']:
        variables=[wires[name]for name in item['inputs']];p=plan(item['plan'])
        if item['kind']=='helper':
            q=b.alloc_qubits(1)[0];cb.emit_xor(b,variables,q,p);wires[item['name']]=q;count+=p.and_count
        else:
            q=wires.pop(item['name']);cb.emit_erase(b,variables,[q],[p]);b.free(q)
    assert set(wires)=={f'r{i}'for i in range(6)} and count==certificate['Toffolis']

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--certificate',type=Path,required=True);ap.add_argument('--entry',type=int,required=True);ap.add_argument('--cap',type=int,default=45);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--cleanup',type=Path);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    data=json.loads(a.certificate.read_text());variant,_,_=ps.ra.load_everything();mods=variant.install();km=mods['root'].km
    from common import with_registers
    from branch_prover import generated_text,Program
    from fourier_resource_expectation import exact_expectation
    b=km.CircuitBuilder();b.set_max_qubits(a.cap);x=list(b.alloc_qubits(22));spectators=list(b.alloc_qubits(a.entry-22));address=x[:6];debts=Debts()
    outputs=emit(b,address,data,debts);f=with_registers(b.finish_circuit(),{'x':x});ft=generated_text(f)
    # Spectator zeros stand for owners absent by the real lifecycle's tail.
    for q in spectators:b.free(q)
    decoder=decode(b,address,outputs,data,debts)
    if a.cleanup:cleanup_certificate(b,address,outputs,data,debts,json.loads(a.cleanup.read_text()))
    else:cleanup(b,address,outputs,data,debts)
    current=address+x[6:]
    # Exact input-wire layout restoration, three-CNOT SWAPs through empty owners.
    for i in range(22):
        if current[i]==x[i]:continue
        if x[i]in current:
            j=current.index(x[i]);u,v=current[i],current[j];b.cx(u,v);b.cx(v,u);b.cx(u,v);current[i],current[j]=current[j],current[i]
        else:
            occupied=set(current);tmp=[]
            while x[i]not in occupied:
                q=b.alloc_qubits(1)[0];tmp.append(q);occupied.add(q)
                if q==x[i]:break
            q=current[i];b.cx(q,x[i]);b.cx(x[i],q);b.free(q);current[i]=x[i]
            for q in tmp:
                if q!=x[i]:b.free(q)
    assert current==x and b.num_allocated_qubits==22 and not debts.pending
    c=with_registers(b.finish_circuit(),{'x':x});ct=generated_text(c);assert ct.startswith(ft)
    width=len(outputs);fingerprint=''.join(f'Z_POW {q} {2.0**(i-width+1):.20f}\n'for i,q in enumerate(outputs))
    fp=km.Circuit(ft+fingerprint+ct[len(ft):]);program=Program(generated_text(fp));assert program.modulus==1<<width
    proof,path=checker(mods['root']);proof.CANDIDATE_MODULUS=1<<width
    expected=np.array([sum(((int(t,16)>>row)&1)<<i for i,t in enumerate(data['output_truths']))for row in range(64)],np.uint64)
    checked=proof.prove_native_chunk(program,np.arange(64,dtype=np.uint64),expected)
    for name,circuit in [('forward',f),('roundtrip',c),('fingerprint',fp)]:circuit.to_file(str(a.out/(name+'.kmb')),format='kmb');(a.out/(name+'.kmx')).write_text(generated_text(circuit))
    record=dict(notice=NOTICE,status='PASS64_ROW_LOADER_ALL_HMR_COMPONENT_ONLY',rows=64,entry=a.entry,Q=c.num_qubits,certificate_sha256=hashlib.sha256(a.certificate.read_bytes()).hexdigest(),forward=exact_expectation(ft),roundtrip=exact_expectation(ct),decoder=decoder,table_debts=debts.recorded,proof=checked,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),checker_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),whole_fusion=False,official_panels_run=0)
    (a.out/'proof.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:v for k,v in record.items()if k not in ('forward','roundtrip','decoder')},indent=2),flush=True)
if __name__=='__main__':main()
