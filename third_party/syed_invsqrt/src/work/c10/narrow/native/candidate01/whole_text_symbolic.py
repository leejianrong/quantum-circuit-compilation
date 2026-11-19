# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Bounded exact proof of emitted native text for every HMR transcript.

Each coefficient is a finite bitset over the concrete original inputs in one
chunk. Square-free monomials name independent syntactic HMR outcomes. Quantum
data and integral half-turn phases are exact Boolean polynomials. Fractional
phases are admitted only when their effective control/data predicate has no
HMR dependence; their native integer phase steps are summed modulo2**37.

This module never changes resource limits and never starts a worker. The
parent's strict serial guard owns those policies and chunk scheduling.
"""
from __future__ import annotations

import hashlib
import resource
import time
import numpy as np
from common import ENGINE

PARSER_SHA='3d009334f8d4f37e10368ea5d46b21fa67eace7c3076f476a0b83f166cc769c2'
assert hashlib.sha256((ENGINE/'branch_prover.py').read_bytes()).hexdigest()==PARSER_SHA
from branch_prover import Program

CANDIDATE_MODULUS=1<<37
MAX_CHUNK=65536


class SymbolicLimitError(RuntimeError):
    """The exact representation reached a finite memory guard; split inputs."""


def _xor(left,right):
    if not left:return right
    if not right:return left
    if left==right:return {}
    result=dict(left)
    for monomial,coefficient in right.items():
        coefficient^=result.get(monomial,0)
        if coefficient:result[monomial]=coefficient
        else:result.pop(monomial,None)
    return result


def _truth(values):
    packed=np.packbits(np.asarray(values,dtype=np.uint8),bitorder='little')
    return int.from_bytes(packed.tobytes(),'little')


def _unpack(truth,count):
    raw=int(truth).to_bytes((count+7)//8,'little')
    return np.unpackbits(np.frombuffer(raw,dtype=np.uint8),bitorder='little',count=count).astype(np.uint64)


def prove_native_chunk(text_or_program,x_values,expected_phase_units):
    """Return an exact receipt for all inputs and all measurement transcripts.

    The expected integers are in the native Program's phase-unit denominator:
    for this candidate, one turn is2**37 units and one half turn is2**36.
    ``Program`` may be supplied to avoid parsing identical text in each chunk.
    """
    began=time.monotonic()
    source_text=text_or_program if isinstance(text_or_program,str) else None
    program=Program(source_text) if source_text is not None else text_or_program
    if program.modulus!=CANDIDATE_MODULUS:
        raise ValueError(f'Expected native phase modulus2**37, received{program.modulus}; phase units must match exactly.')
    assert program.denominator==CANDIDATE_MODULUS//2
    raw_x=np.asarray(x_values);raw_expected=np.asarray(expected_phase_units)
    if raw_x.dtype.kind not in 'ui' or raw_expected.dtype.kind not in 'ui':
        raise TypeError('Input values and expected phase units must be integer arrays, never rounded floats.')
    if raw_x.ndim!=1 or raw_expected.ndim!=1 or len(raw_x)!=len(raw_expected):
        raise ValueError('Expected equally sized one-dimensional input and phase arrays.')
    count=len(raw_x)
    if not 1<=count<=MAX_CHUNK:raise ValueError('The exact input chunk must contain1..65536 values.')
    if np.any(raw_x<0) or np.any(raw_x>=(1<<22)):raise ValueError('Input does not fit the original22 wires.')
    if np.any(raw_expected<0) or np.any(raw_expected>=CANDIDATE_MODULUS):raise ValueError('Expected phase units are not canonical modulo2**37.')
    xs=np.asarray(raw_x,dtype=np.uint64);expected=np.asarray(raw_expected,dtype=np.uint64)
    original=list(program.registers.get('x',()))
    if len(original)!=22 or len(set(original))!=22:raise ValueError('Native text must expose exactly22 distinct registered x owners.')

    full=(1<<count)-1;one={0:full};zero={}
    state={wire:zero for wire in program.wires}
    state.update({'0':zero,'1':one,'False':zero,'True':one})
    original_truths={}
    for bit,wire in enumerate(original):
        truth=_truth((xs>>np.uint64(bit))&np.uint64(1))
        value={0:truth} if truth else zero;state[wire]=value;original_truths[wire]=value
    phase={};stack=[one];fractional_terms=[];maximum_terms=0;fractional_gates=0;resets=0
    # This explicit representation cap is below the inherited512MiB worker
    # cap. It is a rejection/split boundary, never a skipped check or fallback.
    estimated_term_bytes=(count+7)//8+128+(program.measurements+7)//8
    term_limit=max(512,min(200000,(192*1024**2)//max(1,estimated_term_bytes)))

    def multiply(left,right):
        if not left or not right:return zero
        if left==one:return right
        if right==one:return left
        result={}
        for a,ca in left.items():
            for b,cb in right.items():
                coefficient=(ca&cb)^result.get(a|b,0)
                if coefficient:result[a|b]=coefficient
                else:result.pop(a|b,None)
            if len(result)>term_limit:
                raise SymbolicLimitError(f'One polynomial exceeds{term_limit} terms for{count} inputs; split this chunk.')
        return result

    def product(values):
        result=one
        for value in values:
            result=multiply(result,value)
            if not result:break
        return result

    def update_peak(index):
        nonlocal maximum_terms
        terms=len(phase)+sum(len(value) for value in state.values())+sum(len(value) for value in stack)+len(fractional_terms)
        maximum_terms=max(maximum_terms,terms)
        if terms>term_limit:
            raise SymbolicLimitError(f'Exact symbolic state reaches{terms} terms at instruction{index}, cap{term_limit}; split the{count}-input chunk.')

    for index,operation in enumerate(program.operations):
        kind,args=operation.kind,operation.arguments
        condition=stack[-1]
        if operation.condition is not None:condition=multiply(condition,state[operation.condition])
        if kind=='PUSH_CONDITION':stack.append(condition);continue
        if kind=='POP_CONDITION':
            if len(stack)==1:raise AssertionError('Unmatched native POP_CONDITION.')
            stack.pop();continue
        if not condition:continue
        if kind in ('X','BIT_INVERT'):
            state[args[0]]=_xor(state[args[0]],condition)
        elif kind=='CX':
            state[args[1]]=_xor(state[args[1]],multiply(condition,state[args[0]]))
        elif kind=='CCX':
            state[args[2]]=_xor(state[args[2]],product((condition,state[args[0]],state[args[1]])))
        elif kind in ('SWAP','CSWAP'):
            if kind=='CSWAP':condition=multiply(condition,state[args[0]]);a,b=args[1:]
            else:a,b=args
            delta=multiply(condition,_xor(state[a],state[b]));state[a]=_xor(state[a],delta);state[b]=_xor(state[b],delta)
        elif kind in ('Z','CZ','CCZ','NEG'):
            effective=product([condition]+[state[wire] for wire in args]);phase=_xor(phase,effective)
        elif kind=='Z_POW':
            effective=product([condition]+[state[wire] for wire in args])
            if operation.half_turns.denominator==1:
                if operation.half_turns.numerator&1:phase=_xor(phase,effective)
            else:
                dependent=[monomial for monomial in effective if monomial]
                if dependent:
                    first=dependent[0];truth=effective[first];row=(truth&-truth).bit_length()-1
                    raise AssertionError(('HMR-dependent fractional phase',index,int(xs[row]),hex(first)))
                truth=effective.get(0,0)
                if truth:fractional_terms.append((int(program.phase_steps[index])%program.modulus,truth))
                fractional_gates+=1
        elif kind=='HMR':
            target,outcome_wire=args;outcome={1<<operation.event:full}
            phase=_xor(phase,product((condition,outcome,state[target])))
            state[target]=_xor(state[target],multiply(condition,state[target]))
            state[outcome_wire]=_xor(state[outcome_wire],multiply(condition,_xor(state[outcome_wire],outcome)))
        elif kind=='R':
            active=multiply(condition,state[args[0]])
            if active:raise AssertionError(('Dirty native reset',index,args[0],[(hex(m),hex(c)) for m,c in list(active.items())[:3]]))
            resets+=1
        elif kind in ('BIT_STORE0','BIT_STORE1'):
            desired=one if kind=='BIT_STORE1' else zero
            state[args[0]]=_xor(state[args[0]],multiply(condition,_xor(state[args[0]],desired)))
        else:raise AssertionError(f'Unsupported native operation{kind}')
        if index%256==0:update_peak(index)
    update_peak(len(program.operations))
    if len(stack)!=1:raise AssertionError('Unclosed native condition stack.')
    for wire in set(program.quantum_wires)|set(original):
        wanted=original_truths.get(wire,zero)
        if state.get(wire,zero)!=wanted:
            delta=_xor(state.get(wire,zero),wanted);m,c=next(iter(delta.items()));row=(c&-c).bit_length()-1
            raise AssertionError(('Native output/scratch mismatch',wire,int(xs[row]),hex(m)))
    dependent=[m for m in phase if m]
    if dependent:
        monomial=dependent[0];truth=phase[monomial];row=(truth&-truth).bit_length()-1
        raise AssertionError(('Unpaid native HMR phase',int(xs[row]),hex(monomial),len(dependent)))

    actual=np.zeros(count,dtype=np.uint64);mask=np.uint64(program.modulus-1)
    for step,truth in fractional_terms:
        actual=(actual+_unpack(truth,count)*np.uint64(step))&mask
    if phase.get(0,0):actual=(actual+_unpack(phase[0],count)*np.uint64(program.denominator))&mask
    mismatch=np.flatnonzero(actual!=expected)
    if len(mismatch):
        row=int(mismatch[0]);raise AssertionError(('Exact native phase mismatch',int(xs[row]),int(actual[row]),int(expected[row]),int(program.modulus)))
    receipt=dict(status='PROVED_EXACT_NATIVE_TEXT_ALL_HMR_TRANSCRIPTS',inputs=count,
                 modulus=program.modulus,phase_denominator=program.denominator,
                 native_operations=len(program.operations),HMR_variables=program.measurements,
                 every_HMR_transcript_proved=True,original_x_restored=True,all_scratch_zero=True,
                 all_resets_provably_zero=True,resets_checked=resets,
                 all_fractional_phase_predicates_HMR_independent=True,fractional_phase_gates=fractional_gates,
                 accumulated_fractional_terms=len(fractional_terms),final_HMR_phase_terms=0,
                 maximum_total_polynomial_terms=maximum_terms,symbolic_term_limit=term_limit,
                 input_values_sha256=hashlib.sha256(xs.astype('<u8',copy=False).tobytes()).hexdigest(),
                 expected_phase_units_sha256=hashlib.sha256(expected.astype('<u8',copy=False).tobytes()).hexdigest(),
                 seconds=time.monotonic()-began,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                 official_verifier=False)
    if source_text is not None:receipt['native_text_sha256']=hashlib.sha256(source_text.encode()).hexdigest()
    return receipt


def selftest():
    header='\n'.join([f'APPEND_TO_REGISTER q{i} 0' for i in range(22)]+['REGISTER 0 x'])+'\n'
    # A zero-valued dyadic rotation fixes the test's exact native phase unit.
    unit='Z_POW q24 1/68719476736\n';xs=np.arange(1,18,dtype=np.uint64);zero=np.zeros(len(xs),dtype=np.uint64)
    good=[(header+unit+'CX q0 q22\nHMR q22 b0\nZ q0 if b0\nR q22\n',zero),
          (header+unit+'X q22\nHMR q22 b0\nZ b0\nR q22\n',zero)]
    fractional=header+unit+'Z_POW q0 3/68719476736\nZ q1\nZ_POW q2 -1/34359738368\n'
    expected=(3*(xs&1)+np.uint64(1<<36)*((xs>>1)&1)-2*((xs>>2)&1))&np.uint64((1<<37)-1)
    good.append((fractional,expected))
    for text,wanted in good:
        receipt=prove_native_chunk(Program(text),xs,wanted);assert receipt['inputs']==len(xs)
    wrong=[('omitted HMR correction',header+unit+'CX q0 q22\nHMR q22 b0\n',zero),
           ('dirty reset',header+unit+'X q22\nR q22\n',zero),
           ('wrong restored input',header+unit+'X q0\n',zero),
           ('HMR-controlled fractional phase',header+unit+'HMR q22 b0\nZ_POW q0 1/68719476736 if b0\n',zero),
           ('wrong expected phase',fractional,zero)]
    for label,text,wanted in wrong:
        try:prove_native_chunk(Program(text),xs,wanted)
        except AssertionError:pass
        else:raise AssertionError(f'The exact checker accepted negative test:{label}')
    return dict(status='PASS_BOUNDED_SYMBOLIC_SELFTEST',positive_cases=len(good),negative_cases=len(wrong),
                negative_checks=[label for label,_,_ in wrong],inputs_per_case=len(xs),native_worker_started=False)


if __name__=='__main__':
    import json
    print(json.dumps(selftest(),indent=2))
