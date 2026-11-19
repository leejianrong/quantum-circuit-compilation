#!/usr/bin/env python3
# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Fresh ring26 exact50 native proofs with an explicitly local new oracle.

The pinned generic checker and its full positive/negative tests are retained.
No candidate04 oracle import or old37-unit wrapper is used for this phase.
"""
from pathlib import Path
from fractions import Fraction
import argparse,hashlib,importlib.util,json,resource,sys,time
import variant
import numpy as np
from common import km,array,MODEL_SHA
from branch_prover import Program,generated_text

HERE=Path(__file__).resolve().parent
CHECKER_SHA='5c8ac00c902d6d202bf2cb1cde47a8014047482876e356a0741c11c85e171220'
PARSER_SHA='3d009334f8d4f37e10368ea5d46b21fa67eace7c3076f476a0b83f166cc769c2'
assert Path(variant.__file__).resolve()==(HERE/'variant.py').resolve()
assert hashlib.sha256((variant.common.ENGINE/'branch_prover.py').read_bytes()).hexdigest()==PARSER_SHA
_oracle_name='candidate07_explicit_local_ring26_oracle50'
if _oracle_name not in sys.modules:
    _spec=importlib.util.spec_from_file_location(_oracle_name,HERE/'oracle50.py')
    _oracle=importlib.util.module_from_spec(_spec);sys.modules[_oracle_name]=_oracle;_spec.loader.exec_module(_oracle)
oracle=sys.modules[_oracle_name]
assert Path(oracle.__file__).resolve()==(HERE/'oracle50.py').resolve()
phase_units50=oracle.phase_units50;MAX_X=oracle.MAX_X;MODULUS=oracle.MODULUS
assert MODULUS==1<<50 and MAX_X==3133452


def atomic(path,value):
    path=Path(path);temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,default=str)+'\n');temporary.replace(path)


def checker50():
    name='candidate07_pinned_whole_text_symbolic_50'
    if name not in sys.modules:
        path=variant.BASE/'whole_text_symbolic.py'
        assert hashlib.sha256(path.read_bytes()).hexdigest()==CHECKER_SHA
        spec=importlib.util.spec_from_file_location(name,path)
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
        assert module.CANDIDATE_MODULUS==1<<37
        module.CANDIDATE_MODULUS=MODULUS
    module=sys.modules[name];assert module.CANDIDATE_MODULUS==MODULUS==1<<50
    return module


def checked_chunk(program,xs,wanted):
    assert program.modulus==MODULUS and program.denominator==MODULUS//2
    receipt=checker50().prove_native_chunk(program,xs,wanted)
    assert receipt['modulus']==MODULUS and receipt['phase_denominator']==MODULUS//2
    assert receipt['every_HMR_transcript_proved'] and receipt['all_resets_provably_zero']
    return receipt


def selftest50():
    checker=checker50()
    header='\n'.join([f'APPEND_TO_REGISTER q{i} 0'for i in range(22)]+['REGISTER 0 x'])+'\n'
    unit=f'Z_POW q24 1/{1<<49}\n'
    xs=np.arange(1,18,dtype=np.uint64);zero=np.zeros(len(xs),dtype=np.uint64)
    mask=np.uint64(MODULUS-1);bit0=xs&np.uint64(1)
    mixed=header+unit+f'Z_POW q0 3/{1<<49}\nZ q1\nZ_POW q2 -1/{1<<48}\n'
    wanted=(3*bit0+np.uint64(1<<49)*((xs>>np.uint64(1))&1)-2*((xs>>np.uint64(2))&1))&mask
    positives=[
        ('positive single50-unit phase',header+unit+f'Z_POW q0 1/{1<<49}\n',bit0),
        ('negative single50-unit phase',header+unit+f'Z_POW q0 -1/{1<<49}\n',(-bit0)&mask),
        ('mixed exact50-unit phase',mixed,wanted),
        ('affine HMR correction',header+unit+'CX q0 q22\nHMR q22 b0\nZ q0 if b0\nR q22\n',zero),
        ('constant HMR correction',header+unit+'X q22\nHMR q22 b0\nZ b0\nR q22\n',zero),
    ]
    for label,text,expected in positives:
        receipt=checked_chunk(Program(text),xs,expected);assert receipt['inputs']==17,label
    wrong37=(3*bit0+np.uint64(1<<36)*((xs>>np.uint64(1))&1)-2*((xs>>np.uint64(2))&1))&np.uint64((1<<37)-1)
    negatives=[
        ('omitted HMR correction',header+unit+'CX q0 q22\nHMR q22 b0\n',zero,AssertionError),
        ('dirty reset',header+unit+'X q22\nR q22\n',zero,AssertionError),
        ('wrong restored input',header+unit+'X q0\n',zero,AssertionError),
        ('HMR-dependent fractional phase',header+unit+f'HMR q22 b0\nZ_POW q0 1/{1<<49} if b0\n',zero,AssertionError),
        ('wrong expected phase',mixed,zero,AssertionError),
        ('one50-unit phase error',mixed,(wanted+np.uint64(1))&mask,AssertionError),
        ('old37-unit expected integers',mixed,wrong37,AssertionError),
        ('old37-unit native modulus',header+f'Z_POW q0 1/{1<<36}\n',bit0,ValueError),
        ('noncanonical50-unit expectation',header+unit,np.full(len(xs),MODULUS,dtype=np.uint64),ValueError),
    ]
    for label,text,expected,error in negatives:
        try:checker.prove_native_chunk(Program(text),xs,expected)
        except error:pass
        else:raise AssertionError('Exact50-unit checker accepted negative test: '+label)
    return dict(status='PASS_EXACT_50_UNIT_POSITIVE_NEGATIVE_SELFTEST',phase_modulus=MODULUS,
        half_turn_denominator=MODULUS//2,positive_cases=len(positives),negative_cases=len(negatives),inputs_per_case=17,
        positive_checks=[r[0]for r in positives],negative_checks=[r[0]for r in negatives],
        checker_source_sha256=CHECKER_SHA,old37_unit_wrapper_or_selftest_used=False,
        all_phase_data_scratch_and_HMR_checks_enabled=True,phase_basis='ring26_global_zero33')


def bits(values,n):return((values[None,:]>>np.arange(n,dtype=np.uint64)[:,None])&1).astype(bool)
def read(sim,wires):return(sim.read_across_shots(array(wires)).astype(np.uint64)<<np.arange(len(wires),dtype=np.uint64)[:,None]).sum(axis=0)


def native_sample(circuit,count,seeds):
    assert count>=1024 and count%256==0
    original=list(circuit.register_data['x']);scratch=[km.q(i)for i in range(circuit.num_qubits)if km.q(i)not in original]
    boundaries=sorted(set([1,MAX_X]+[min(MAX_X,v)for i in range(22)for v in((1<<i)-1,1<<i,(1<<i)+1)if v>0]))
    records=[]
    for seed in seeds:
        started=time.monotonic();sim=km.Simulator(batch_size=256,counting_operations=True,seed=seed)
        rng=np.random.default_rng(171711+seed)
        for first in range(0,count,256):
            xs=rng.integers(1,MAX_X+1,256,dtype=np.uint64)
            if first==0:xs[:len(boundaries)]=boundaries
            wanted=phase_units50(xs)
            sim.clear_for_shot();sim.write_across_shots(array(original),bits(xs,22));sim.do(circuit)
            observed=read(sim,original)
            assert np.array_equal(observed,xs),('native_input_restoration',seed,first,int(xs[np.flatnonzero(observed!=xs)[0]]))
            assert not sim.read_across_shots(array(scratch)).any(),('native_scratch',seed,first)
            for i,target in enumerate(wanted):
                actual=sim.read_shot_phase(i);expected=Fraction(2*int(target),MODULUS)
                assert(actual-expected)%2==0,('native_exact50_ring26_phase',seed,int(xs[i]),str(actual),str(expected))
        stats=sim.operation_statistics()
        record=dict(seed=seed,shots=count,status='PASS_SAMPLED_NATIVE_EXACT50_PHASE_INPUT_AND_SCRATCH',
                    sampled_mean_Toffolis=stats.num_toffoli_like/count,seconds=time.monotonic()-started)
        records.append(record);print(json.dumps(record),flush=True)
    return dict(status='PASS_NATIVE_SAMPLED_CANDIDATE07_NOT_OFFICIAL',checks=records,
        original_input_register_restored=True,scratch_zero=True,
        phase_exactly_matches_quantized_integer50_model=True,phase_exactly_matches_frozen_integer_model=True,
        new_ring26_oracle_used=True)


def exhaustive_text(circuit,first,last,chunk_size,out,fit):
    assert 1<=first<last<=MAX_X+1 and 1<=chunk_size<=65536
    text=generated_text(circuit);program=Program(text)
    assert program.modulus==MODULUS and program.denominator==MODULUS//2
    checker=checker50();rows=[];splits=[];phase_sha=hashlib.sha256();began=time.monotonic()
    pending=[(start,min(last,start+chunk_size))for start in range(first,last,chunk_size)]
    while pending:
        start,stop=pending.pop(0);xs=np.arange(start,stop,dtype=np.uint64);wanted=phase_units50(xs)
        try:receipt=checked_chunk(program,xs,wanted)
        except checker.SymbolicLimitError as error:
            if stop-start<=1:raise
            middle=start+(stop-start)//2;pending[:0]=[(start,middle),(middle,stop)]
            splits.append(dict(first=start,stop=stop,split=middle,reason=str(error)))
            print(json.dumps(dict(event='exact_symbolic_chunk_split',**splits[-1])),flush=True);continue
        phase_sha.update(wanted.astype('<u8',copy=False).tobytes());rows.append(dict(first=start,stop=stop,**receipt))
        status=dict(status='PARTIAL_EXACT_NATIVE_TEXT_50_UNITS',phase_basis='ring26_global_zero33',
            phase_modulus=MODULUS,requested_interval=[first,last],proved_inputs=sum(r['inputs']for r in rows),
            chunks=rows,representation_splits=splits,seconds=time.monotonic()-began)
        atomic(out.with_suffix('.partial.json'),status)
        print(json.dumps(dict(progress='exact_native_text50_ring26',first=start,stop=stop,
            proved_inputs=status['proved_inputs'],seconds=status['seconds'])),flush=True)
    whole=first==1 and last==MAX_X+1
    assert sum(r['inputs']for r in rows)==last-first and rows[0]['first']==first and rows[-1]['stop']==last
    assert all(a['stop']==b['first']for a,b in zip(rows,rows[1:]))
    if whole:
        assert phase_sha.hexdigest()==fit['exact_screen']['phase50_sha256']==oracle.EXPECTED_PHASE_SHA256, 'Independent complete ring26 fit/oracle digest mismatch.'
    return dict(status='PASS_EXACT_NATIVE_TEXT_ALL_REQUESTED_INPUTS_ALL_HMR_TRANSCRIPTS',
        phase_modulus=MODULUS,phase_denominator=MODULUS//2,input_interval=[first,last],input_interval_end_exclusive=True,
        proved_inputs=last-first,whole_official_domain=whole,original_input_register_restored=True,scratch_zero=True,
        all_resets_provably_zero=True,every_HMR_transcript_proved=True,all_phase_checks_enabled=True,
        phase_exactly_matches_quantized_integer50_model=True,phase_exactly_matches_frozen_integer_model=True,
        phase_units50_sha256=phase_sha.hexdigest(),independent_full_quantize50_digest_matched=whole,
        independent_full_ring26_fit_digest_matched=whole,independent_full_ring26_digest_matched=whole,new_ring26_oracle_used=True,
        native_operations=len(program.operations),independent_HMR_variables=program.measurements,
        native_text_sha256=hashlib.sha256(text.encode()).hexdigest(),checker_source_sha256=CHECKER_SHA,
        chunks=rows,representation_splits=splits,seconds=time.monotonic()-began)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=('selftest','sample','text'),required=True)
    ap.add_argument('--circuit',type=Path,default=HERE/'candidate07.kmb')
    ap.add_argument('--shots',type=int,default=8192);ap.add_argument('--seeds',default='0,1,2,3')
    ap.add_argument('--first',type=int,default=1);ap.add_argument('--last',type=int,default=MAX_X+1)
    ap.add_argument('--chunk',type=int,default=65536);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();began=time.monotonic();gate=variant.variant_gate();fit,fit_sha=variant.accuracy_receipt()
    assert(gate['Q'],gate['Toffolis_expected'],gate['T'],gate['R'])==(48,1584,4,33)
    tests=selftest50()
    if args.mode=='selftest':result=tests
    else:
        digest=hashlib.sha256(args.circuit.read_bytes()).hexdigest();circuit=km.Circuit.from_file(str(args.circuit))
        assert circuit.num_qubits==48 and list(circuit.register_data)==['x']and len(circuit.register_data['x'])==22
        build=json.loads(args.circuit.with_suffix('.build.json').read_text())
        assert build['kmb_sha256']==digest and build['accuracy_receipt_sha256']==fit_sha
        assert build['parent_authorization_sha256']==variant.GATE_SHA and build['paper_gate_sha256']==variant.PAPER_SHA
        assert build['phase_basis']=='ring26_global_zero33'
        assert build['independent_phase_units50_sha256']==fit['exact_screen']['phase50_sha256']
        assert build['exact_native_expectation']['mean_numeric']==dict(toffoli_like=1584.0,T=4.0,generic_rotations=33.0)
        assert Program(generated_text(circuit)).modulus==MODULUS
        result=native_sample(circuit,args.shots,list(map(int,args.seeds.split(','))))if args.mode=='sample'else exhaustive_text(circuit,args.first,args.last,args.chunk,args.output,fit)
        result.update(circuit_sha256=digest,Q=48,exact50_unit_selftest=tests)
    result.update(candidate='candidate07_complete_Q48_ring26',phase_basis='ring26_global_zero33',
        phase_modulus=MODULUS,arithmetic_model_sha256=MODEL_SHA,
        accuracy_receipt_sha256=fit_sha,
        accuracy_receipt_path='research/ring26_phase/frozen/global_zero33.json',
        quantized_exact_minimum_margin_units64=fit['exact_screen']['statistics']['grid50']['minimum_margin_units'],
        independent_phase_units50_sha256=fit['exact_screen']['phase50_sha256'],
        expected_native_Toffolis=1584.0,expected_T=4,expected_R=33,
        unchanged_candidate04_angles=False,unchanged_original_tolerance=True,
        local_oracle_sha256=hashlib.sha256((HERE/'oracle50.py').read_bytes()).hexdigest(),
        local_proof_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        phase_source_sha256=hashlib.sha256((HERE/'phase07.py').read_bytes()).hexdigest(),
        parent_authorization_sha256=variant.GATE_SHA,paper_gate_sha256=variant.PAPER_SHA,
        official_verifier=False,no_submission=True,elapsed_seconds=time.monotonic()-began,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    atomic(args.output,result);print(json.dumps({k:v for k,v in result.items()if k!='chunks'},indent=2),flush=True)


if __name__=='__main__':main()
