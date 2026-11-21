# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Native 11-bit consuming root: resource ledger and exact component proof.

For every normalized n in [2**20,2**22), this computes Q=floor(sqrt(4*n)),
v=Q-2048, h=floor((16*n-(2*Q+1)**2)/16).  The 22 owners hold
(v<<11)|(h&2047).  A phase fingerprint makes that entire forward value
observable to the pinned all-HMR checker, while the inverse restores n.
This is a component experiment, not a complete fusion candidate.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import sys
import time
import numpy as np
import precision_sensitivity as ps

HERE=Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def forward(builder,norm,root):
    norm=list(norm)
    assert len(norm)==22 and len(set(norm))==22
    builder.x(norm[20]);builder.cx(norm[20],norm[21])
    remainder=norm[20:22];roots=[]
    for j in range(1,12):
        pair=norm[20-2*j:22-2*j] if j<=10 else list(builder.alloc_qubits(2))
        if j==1:
            b=True;older=[];remainder=pair+remainder
        else:
            b=remainder[-1];builder.x(b);older=roots
            roots=[b]+roots;remainder=pair+remainder[:-1]
        root.last_step(builder,remainder,older,b,initial=j==1)
    b=remainder[-1];builder.x(b);Q=[b]+roots;W=remainder[:-1]
    # The j11 zero-pair shortcut leaves these two owners identically one.
    builder.x(root.arr(W[:2]));builder.free(root.arr(W[:2]))
    high=W[2:]
    # Carry from omitted W1 is Q1: maj(Q1,1 xor Q0,Q0)=Q1.
    builder.cx(Q[0],root.arr(high))
    root.original.add(builder,Q[2:],high,carry_in=Q[1])
    root.original._add_leading_one(builder,high)
    builder.cx(Q[0],root.arr(high))
    assert Q==norm[11:] and high==norm[:11]
    return dict(root=Q,residual=high)


def inverse(builder,norm,root):
    norm=list(norm);Q=norm[11:];high=norm[:11]
    builder.cx(Q[0],root.arr(high))
    root.original._add_leading_one(builder,high,inverse=True)
    root.original.add(builder,Q[2:],high,carry_in=Q[1],subtract=True)
    builder.cx(Q[0],root.arr(high))
    low=list(builder.alloc_qubits(2));builder.x(root.arr(low))
    W=low+high;b=Q[0];roots=Q[1:]
    builder.x(b);remainder=W+[b]
    for j in reversed(range(1,12)):
        pair=remainder[:2]
        if j==1:b=True;older=[]
        else:b=roots[0];older=roots[1:]
        root.last_step(builder,remainder,older,b,initial=j==1,inverse=True)
        if j==1:remainder=remainder[2:]
        else:
            remainder=remainder[2:]+[b];builder.x(b);roots=older
        if j==11:builder.free(root.arr(pair))
        else:assert pair==norm[20-2*j:22-2*j]
    assert remainder==norm[20:] and not roots
    builder.cx(norm[20],norm[21]);builder.x(norm[20])


def expected(n):
    n=np.asarray(n,dtype=np.int64)
    q=np.sqrt(n*4).astype(np.int64)
    assert np.all(q*q<=n*4) and np.all((q+1)*(q+1)>n*4)
    v=q-2048;h=(n*16-(2*q+1)**2)//16
    assert np.all((v>=0)&(v<2048)) and np.all((h>=-1024)&(h<1024))
    return ((v<<11)|(h&2047)).astype(np.uint64)


def build():
    variant,_,_=ps.ra.load_everything();root=variant.install()['root'];km=root.km
    from common import with_registers
    from branch_prover import generated_text
    b=km.CircuitBuilder();b.set_max_qubits(46)
    x=list(b.alloc_qubits(22));flags=list(b.alloc_qubits(4))
    forward(b,x,root);f=with_registers(b.finish_circuit(),{'x':x})
    inverse(b,x,root);p=with_registers(b.finish_circuit(),{'x':x})
    assert b.num_allocated_qubits==26
    ft=generated_text(f);pt=generated_text(p)
    assert pt.startswith(ft)
    fingerprint=''.join(f'Z_POW {wire} {2.0**(i-21):.21f}\n' for i,wire in enumerate(x))
    fp=km.Circuit(ft+fingerprint+pt[len(ft):])
    return root,f,p,fp,x,flags


def checker(root):
    path=root.NARROW/'native/candidate01/whole_text_symbolic.py'
    spec=importlib.util.spec_from_file_location('_fusion_root11_pinned_checker',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    module.CANDIDATE_MODULUS=1<<22
    return module,path


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--prove',action='store_true');ap.add_argument('--chunk',type=int,default=65536)
    ap.add_argument('--limit',type=int,default=0)
    a=ap.parse_args();assert 1<=a.chunk<=65536;a.out.mkdir(parents=True,exist_ok=True);began=time.monotonic()
    root,f,p,fp,x,flags=build()
    from branch_prover import Program,generated_text
    from fourier_resource_expectation import exact_expectation
    resources={}
    for name,circuit in [('forward',f),('roundtrip',p),('fingerprint',fp)]:
        binary=a.out/(name+'.kmb');text=a.out/(name+'.kmx')
        circuit.to_file(str(binary),format='kmb');text.write_text(generated_text(circuit))
        resources[name]=dict(Q=circuit.num_qubits,expectation=exact_expectation(text.read_text()),
                             kmb_sha256=sha(binary),kmx_sha256=sha(text))
    report=dict(status='NATIVE_ROOT11_COMPONENT_RESOURCE_LEDGER',resources=resources,
                source_sha256=sha(__file__),inherited_root_sha256=sha(root.__file__),
                normalized_tuple='Q=isqrt(4*n); v=Q-2048; h=(16*n-(2*Q+1)**2)//16',
                official_salt_panels_run=0,complete_fusion_candidate=False)
    path=a.out/'ledger.json';path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)
    # A full-domain data simulation is a quick diagnosis before all-HMR proof.
    import kmsim
    ops,registers=kmsim.parse(generated_text(f))
    first=1<<20;stop=min(1<<22,first+a.limit) if a.limit else 1<<22
    xs=np.arange(first,stop,dtype=np.uint64)
    sim=kmsim.Sim(ops,registers['x'],xs=xs).run()
    actual=sim.value(registers['x']);wanted=expected(xs)
    bad=np.flatnonzero(actual!=wanted)
    if len(bad):
        i=int(bad[0]);raise AssertionError(('forward tuple mismatch',int(xs[i]),int(actual[i]),int(wanted[i])))
    report['forward_value_check']=dict(inputs=len(xs),interval=[first,stop],every_HMR_branch=False,
                                      status='PASS_FULL_INPUT_DATA_SIMULATION' if not a.limit else 'PASS_PARTIAL_INPUT_DATA_SIMULATION',
                                      packed_output_sha256=hashlib.sha256(actual.astype('<u8').tobytes()).hexdigest())
    path.write_text(json.dumps(report,indent=2)+'\n')
    del sim,actual,wanted,xs
    if a.prove:
        proof,proofpath=checker(root);program=Program(generated_text(fp));assert program.modulus==1<<22
        rows=[]
        for start in range(first,stop,a.chunk):
            end=min(stop,start+a.chunk);xx=np.arange(start,end,dtype=np.uint64)
            receipt=proof.prove_native_chunk(program,xx,expected(xx));rows.append(dict(first=start,stop=end,**receipt))
            report.update(status='PARTIAL_ROOT11_FINGERPRINT_PROOF_NOT_COMPLETE',proof_chunks=rows,
                          checker_sha256=sha(proofpath),seconds=time.monotonic()-began)
            path.write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps(dict(proved_inputs=end-first,seconds=report['seconds'])),flush=True)
        report['status']='PASS_ROOT11_ALL_NORMALIZED_INPUTS_ALL_HMR_COMPONENT' if not a.limit else 'PASS_ROOT11_PARTIAL_INPUTS_ALL_HMR_COMPONENT'
        report['proved_inputs']=stop-first;report['every_HMR_transcript_proved']=True
        report['forward_packed_tuple_proved_by_injective_phase_fingerprint']=True
        report['all_input_restoration_scratch_and_resets_proved']=True
        path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('resources','proof_chunks')}),flush=True)


if __name__=='__main__':main()
