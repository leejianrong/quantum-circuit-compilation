# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""Normal syndrome->monic pair->syndrome pilot, without exceptions or scan."""
from __future__ import annotations
from functools import cache
import hashlib
import io
import json
from pathlib import Path
import random
import sys
import kickmix as km
import numpy as np
from confluent_reference import Algebra,modulus,from_errors
from field_tensor import invert_field_matrix,invert_binary_columns
from tower_inverse import rows_from_columns,apply_inplace_linear
from quantum_reciprocal import bit_matrix,xor_linear
from compact_inverse import compact_inverse_twelve
from dual_scale import scale_word
from projective_carry import emit as key,erase_inverse_word,reference as key_reference
from deferred_fold import emit_forward,emit_paired_reverse
from normalization import emit as normalize

ALG=Algebra(12);FIELD=ALG.field

def flat(words):return km.array([wire for word in words for wire in word])

@cache
def input_map(t):
    nodes=list(range(t));M=modulus(ALG,nodes);n=2*t;columns=[]
    for index in range(n):
        h=[M[index+ell+1] if index+ell+1<=n else 0 for ell in range(n)]
        columns.append([value for node in nodes for value in ALG.jet(h,node)])
    matrix=[[columns[j][i] for j in range(n)] for i in range(n)]
    invert_field_matrix(matrix,FIELD)
    binary=[]
    for word in range(n):
        for bit in range(12):
            binary.append(sum(FIELD.mul(matrix[out][word],1<<bit)<<(12*out) for out in range(n)))
    return M,tuple(binary)

def parameter_coordinates(builder,jets):
    for node,(a,b) in enumerate(jets):
        xor_linear(builder,b,a,tuple(FIELD.mul(node,1<<bit) for bit in range(12)))

def scale_head(builder,words,scale,inverse,divide=False):
    temporary=builder.alloc_qubits(12)
    for word in words:
        if divide:scale_word(builder,word,inverse,scale,temporary)
        else:scale_word(builder,word,scale,inverse,temporary)
    builder.free(temporary)

def build(t,repay_fold_masks=True):
    assert t>=2
    builder=km.CircuitBuilder();_,binary=input_map(t)
    words=[builder.create_quantum_register(12,f'S{i}') for i in range(2*t)]
    jets=[words[2*i:2*i+2] for i in range(t)]
    probe=builder.create_classical_register(12*(2*t+1),'monic_pair_and_scale_probe')
    apply_inplace_linear(builder,flat(words),rows_from_columns(binary))
    scale=builder.alloc_qubits(12);builder.x(scale[0])
    key_masks=[]
    inverse=key(builder,jets,scale,keep_inverse=True,deferred_masks=key_masks)
    parameter_coordinates(builder,jets)
    scale_head(builder,jets[-1],scale,inverse)
    key_masks.append(erase_inverse_word(builder,scale,inverse,defer=True))
    N=[scale];D=list(jets[-1]);history=[]
    for node in reversed(range(t-1)):
        P=jets[node]
        measured=emit_forward(builder,P,N,D,node)
        history.append((P,N,D,node,measured))
        N,D=D,list(P)+N
    leading=D[-1];normalized_words=D[:-1]+N
    normalizer_mask=normalize(builder,normalized_words,leading,defer=True)
    builder.cz(probe,flat(normalized_words+[leading]))
    normalize(builder,normalized_words,leading,True,deferred_mask=normalizer_mask)
    for P,oldN,oldD,node,measured in reversed(history):
        emit_paired_reverse(builder,P,oldN,oldD,node,measured,repay_fold_masks)
    inverse=compact_inverse_twelve(builder,scale)
    scale_head(builder,jets[-1],scale,inverse,True)
    parameter_coordinates(builder,jets)
    key(builder,jets,scale,True,initial_inverse=inverse,deferred_masks=key_masks)
    builder.x(scale[0]);builder.free(scale)
    apply_inplace_linear(builder,flat(words),invert_binary_columns(binary))
    return builder.finish_circuit(),words,probe

def polynomial_reference(parameters,scale):
    pairs=[[int(a)^FIELD.mul(i,int(b)),int(b)] for i,(a,b) in enumerate(parameters)]
    N=[scale];D=[FIELD.mul(scale,c) for c in pairs[-1]]
    for node in reversed(range(len(pairs)-1)):
        assert ALG.evaluate_polynomial(D,node)
        parent=ALG.add(ALG.product(pairs[node],D),ALG.product([FIELD.mul(node,node),0,1],N))
        N,D=D,parent
    return N,D

def direct_pair(errors,M):
    locator=[1]
    for root,_ in errors:locator=ALG.product(locator,[root,1])
    numerator=[0]*len(errors)
    for j,(root,amplitude) in enumerate(errors):
        cofactor=[FIELD.mul(FIELD.mul(amplitude,root),ALG.evaluate_polynomial(M,root))]
        for k,(other,_) in enumerate(errors):
            if k!=j:cofactor=ALG.product(cofactor,[other,1])
        for k,value in enumerate(cofactor):numerator[k]^=value
    return numerator,locator

def run_checks(destination=None):
    rng=random.Random(2026110826)
    report=dict(status='PASS_full_weight_normal_pipeline_only',failures=0,cases=[])
    for t in (2,4,8):
        M,_=input_map(t);inputs=[];expected=[];rejected=0
        while len(inputs)<1024:
            errors=[(x,rng.randrange(1,4096)) for x in rng.sample(range(t,4096),t)]
            values,_=from_errors(ALG,errors,list(range(t)),M)
            try:
                parameters,scale=key_reference(list(zip(values[::2],values[1::2])))
                N,D=polynomial_reference(parameters,scale)
            except AssertionError:
                rejected+=1;continue
            if len(D)!=t+1 or len(N)>t:
                rejected+=1;continue
            kappa=D[-1];reciprocal=FIELD.invert(kappa)
            normalizedN=[FIELD.mul(v,reciprocal) for v in N]+[0]*(t-len(N))
            normalizedD=[FIELD.mul(v,reciprocal) for v in D]
            directN,directD=direct_pair(errors,M)
            assert normalizedD==directD and normalizedN==directN
            syndrome=[]
            for power in range(1,2*t+1):
                value=0
                for root,amplitude in errors:value^=FIELD.mul(amplitude,FIELD.pow(root,power))
                syndrome.append(value)
            inputs.append(syndrome);expected.append(normalizedD[:-1]+normalizedN+[kappa])
        inputs=np.array(inputs,dtype=np.int64);expected=np.array(expected,dtype=np.int64)
        masks=np.array([[rng.randrange(4096) for _ in row] for row in expected],dtype=np.int64)
        phases=np.array([sum((int(x)&int(m)).bit_count() for x,m in zip(row,mask))&1
                         for row,mask in zip(expected,masks)],dtype=bool)
        circuit,words,probe=build(t)
        payload,repeated=io.BytesIO(),io.BytesIO()
        circuit.to_file(payload,format='kmb');build(t)[0].to_file(repeated,format='kmb')
        assert payload.getvalue()==repeated.getvalue()
        model=126*t*t+900*t-228
        assert circuit.operation_statistics().num_toffoli_like==model
        assert circuit.num_qubits==24*t+36
        scratch=[km.q(i) for i in range(24*t,circuit.num_qubits)]
        for seed in range(4):
            sim=km.Simulator(batch_size=len(inputs),seed=seed);sim.use_same_registers_as(circuit)
            for j,word in enumerate(words):sim.write_across_shots(word,bit_matrix(inputs[:,j],12))
            for j in range(2*t+1):sim.write_across_shots(probe[12*j:12*(j+1)],bit_matrix(masks[:,j],12))
            sim.do(circuit)
            for j,word in enumerate(words):assert np.array_equal(sim.read_across_shots(word),bit_matrix(inputs[:,j],12))
            assert not sim.read_across_shots(scratch).any()
            assert np.array_equal(sim.read_phase_flipped_across_shots(),phases)
        if t==2:
            negative,negative_words,negative_probe=build(t,repay_fold_masks=False)
            sim=km.Simulator(batch_size=len(inputs),seed=0);sim.use_same_registers_as(negative)
            for j,word in enumerate(negative_words):sim.write_across_shots(word,bit_matrix(inputs[:,j],12))
            for j in range(2*t+1):sim.write_across_shots(negative_probe[12*j:12*(j+1)],bit_matrix(masks[:,j],12))
            sim.do(negative)
            for j,word in enumerate(negative_words):assert np.array_equal(sim.read_across_shots(word),bit_matrix(inputs[:,j],12))
            errors=int(np.count_nonzero(sim.read_phase_flipped_across_shots()!=phases))
            assert errors>len(inputs)//4
            report['negative_control']=dict(omitted='forward-fold measurement phase repayment',
                                             shots=len(inputs),phase_errors=errors,value_errors=0,
                                             status='PASS_detected_required_repayment')
        report['cases'].append(dict(nodes=t,T=circuit.operation_statistics().num_toffoli_like,model_T=model,
                                    Q=circuit.num_qubits,extra_qubits=circuit.num_qubits-24*t,
                                    shots_per_seed=len(inputs),seeds=4,rejected_non_normal=rejected,
                                    byte_identical_fresh_builds=True,operations=len(circuit),
                                    sha256=hashlib.sha256(payload.getvalue()).hexdigest()))
        if destination:(destination.parent.parent/'circuits'/f'normal-pipeline-t{t}.kmb').write_bytes(payload.getvalue())
    report['degree35_model']=dict(T_roundtrip=185622,Q=876,Q_with_one_bit=877,
                                  components=dict(extraction=117432,head=168,synthesis=61974,normalization=6048),
                                  retained_deferred_classical_bits=12*35+24*34+12,
                                  status='normal full-weight no-node-collision pipeline only; no exceptions or scan')
    report['numerator_contract']='A(root)=error*root*M(root)*Dprime(root), so a known classical root*M(root) amplitude reweighting is required in the scan. Node collisions are excluded from this pilot.'
    if destination:destination.write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':print(json.dumps(run_checks(Path(sys.argv[1]) if len(sys.argv)>1 else None),indent=2))
