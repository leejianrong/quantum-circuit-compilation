# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""Normal confluent extraction with one reversible carried scale.

Zero final normalizers require a separate lookahead/terminal controller.
They are deliberately excluded from this component's acceptance claim.
"""
from __future__ import annotations
from functools import cache
import hashlib
import io
import json
from pathlib import Path
import sys
import kickmix as km
import numpy as np
from compact_inverse import compact_inverse_twelve,phase_inverse_twelve
from tower_inverse import apply_inplace_linear,quadratic_basis,rows_from_columns,xor_product
from quantum_reciprocal import bit_matrix,xor_linear
from dual_scale import scale_word,FIELD

def flat(words):return km.array([wire for word in words for wire in word])

@cache
def power_rows(exponent):
    return rows_from_columns([FIELD.pow(1<<bit,exponent) for bit in range(12)])

@cache
def fixed_rows(coefficient):
    assert coefficient
    return rows_from_columns([FIELD.mul(coefficient,1<<bit) for bit in range(12)])

def linear_scale(builder,word,coefficient):
    apply_inplace_linear(builder,word,fixed_rows(coefficient))

def square(builder,word,reverse=False):
    apply_inplace_linear(builder,word,power_rows(1<<11 if reverse else 2))

def erase_inverse_word(builder,scale,inverse,defer=False):
    apply_inplace_linear(builder,inverse,quadratic_basis(12)['to_tower'])
    mask=builder.alloc_bits(12)
    builder.hmr(inverse,mask);builder.free(inverse)
    if defer:return mask
    phase_inverse_twelve(builder,scale,mask)
    builder.free(mask)

def repay_inverse_mask(builder,inverse,mask):
    info=quadratic_basis(12)
    apply_inplace_linear(builder,inverse,info['to_tower'])
    builder.cz(mask,inverse)
    apply_inplace_linear(builder,inverse,info['from_tower'])
    builder.free(mask)

def scale_pair(builder,value,slope,scale,inverse,divide=False):
    temporary=builder.alloc_qubits(12)
    if divide:scale_word(builder,value,inverse,scale,temporary)
    else:scale_word(builder,value,scale,inverse,temporary)
    square(builder,scale);square(builder,inverse)
    if divide:scale_word(builder,slope,inverse,scale,temporary)
    else:scale_word(builder,slope,scale,inverse,temporary)
    square(builder,inverse,True);square(builder,scale,True)
    builder.free(temporary)

def xor_evaluation_product(builder,parameter,node_difference,value,target):
    columns=tuple(FIELD.mul(node_difference,1<<bit) for bit in range(12))
    xor_linear(builder,parameter[1],parameter[0],columns)
    xor_product(builder,parameter[0],value,target)
    xor_linear(builder,parameter[1],parameter[0],columns)

def homogeneous(builder,value,slope,scale,parameter,node_difference,reverse=False):
    p=FIELD.mul(node_difference,node_difference)
    assert p
    if reverse:
        linear_scale(builder,scale,FIELD.invert(p))
        builder.swap(value,scale)
        xor_evaluation_product(builder,parameter,node_difference,value,scale)
        linear_scale(builder,slope,FIELD.invert(p))
        square(builder,value);xor_product(builder,parameter[1],value,slope);square(builder,value,True)
    else:
        square(builder,value);xor_product(builder,parameter[1],value,slope);square(builder,value,True)
        linear_scale(builder,slope,p)
        xor_evaluation_product(builder,parameter,node_difference,value,scale)
        builder.swap(value,scale)
        linear_scale(builder,scale,p)

def emit(builder,jets,scale,reverse=False,keep_inverse=False,initial_inverse=None,deferred_masks=None):
    nodes=len(jets)
    if reverse:
        inverse=initial_inverse if initial_inverse is not None else compact_inverse_twelve(builder,scale)
        if deferred_masks is not None:
            assert len(deferred_masks)==nodes
            repay_inverse_mask(builder,inverse,deferred_masks[-1])
        for i in reversed(range(nodes)):
            u,v=jets[i]
            scale_pair(builder,u,v,scale,inverse)
            erase_inverse_word(builder,scale,inverse)
            builder.swap(u,scale)
            for j in reversed(range(i)):homogeneous(builder,u,v,scale,jets[j],i^j,True)
            if i:
                inverse=compact_inverse_twelve(builder,scale)
                if deferred_masks is not None:repay_inverse_mask(builder,inverse,deferred_masks[i-1])
                scale_pair(builder,u,v,scale,inverse,True)
        return
    inverse=None
    for i,(u,v) in enumerate(jets):
        if i:
            scale_pair(builder,u,v,scale,inverse)
            mask=erase_inverse_word(builder,scale,inverse,defer=deferred_masks is not None)
            if deferred_masks is not None:deferred_masks.append(mask)
        for j in range(i):homogeneous(builder,u,v,scale,jets[j],i^j)
        builder.swap(u,scale)
        inverse=compact_inverse_twelve(builder,scale)
        scale_pair(builder,u,v,scale,inverse,True)
    if keep_inverse:return inverse
    mask=erase_inverse_word(builder,scale,inverse,defer=deferred_masks is not None)
    if deferred_masks is not None:deferred_masks.append(mask)

def build(nodes):
    builder=km.CircuitBuilder()
    jets=[(builder.create_quantum_register(12,f'value_{i}'),
           builder.create_quantum_register(12,f'derivative_{i}')) for i in range(nodes)]
    scale=builder.alloc_qubits(12);builder.x(scale[0])
    mask=builder.create_classical_register(24*nodes+12,'parameters_and_scale_probe')
    emit(builder,jets,scale)
    builder.cz(mask,flat([word for jet in jets for word in jet]+[scale]))
    emit(builder,jets,scale,True)
    builder.x(scale[0]);builder.free(scale)
    return builder.finish_circuit(),jets,mask

def source_from_parameters(parameters):
    """Invert the projective maps algebraically, rejecting an initial pole."""
    inputs=[]
    for i,(a,b) in enumerate(parameters):
        N,D,W=1,int(a),int(b)
        for j in reversed(range(i)):
            point=i^j;p=FIELD.mul(point,point)
            P=int(parameters[j][0])^FIELD.mul(point,int(parameters[j][1]))
            oldN=FIELD.mul(D,FIELD.invert(p))
            N,D=oldN,N^FIELD.mul(P,oldN)
            W=FIELD.mul(W,FIELD.invert(p))^FIELD.mul(int(parameters[j][1]),FIELD.mul(oldN,oldN))
        if not D:return None
        reciprocal=FIELD.invert(D)
        inputs.append((FIELD.mul(N,reciprocal),FIELD.mul(W,FIELD.mul(reciprocal,reciprocal))))
    return inputs

def reference(inputs):
    parameters=[];scale=1
    for i,(u,v) in enumerate(inputs):
        N,D,W=FIELD.mul(scale,u),scale,FIELD.mul(FIELD.mul(scale,scale),v)
        for j,(a,b) in enumerate(parameters):
            point=i^j;p=FIELD.mul(point,point);P=a^FIELD.mul(point,b)
            W=FIELD.mul(p,W^FIELD.mul(b,FIELD.mul(N,N)))
            N,D=D^FIELD.mul(P,N),FIELD.mul(p,N)
        assert N
        inverse=FIELD.invert(N)
        parameters.append((FIELD.mul(D,inverse),FIELD.mul(W,FIELD.mul(inverse,inverse))))
        scale=N
    return parameters,scale

def run_checks(destination=None):
    rng=np.random.default_rng(2026110825)
    report=dict(status='PASS_normal_carried_scale_component_only',failures=0,cases=[])
    for nodes in (2,4,8):
        shots=2048;inputs=[];outputs=[];pole_parameters=0;double_pole_parameters=0;rejected=0
        while len(inputs)<shots:
            parameters=rng.integers(0,4096,size=(nodes,2),dtype=np.int64)
            parameters[0,0]=rng.integers(1,4096)
            if len(inputs)%4==0:parameters[-1,0]=0
            if len(inputs)%8==0:parameters[-1,1]=0
            source=source_from_parameters(parameters)
            if source is None:rejected+=1;continue
            computed,scale=reference(source)
            assert computed==[tuple(int(x) for x in row) for row in parameters]
            pole_parameters+=sum(int(row[0]==0) for row in parameters)
            double_pole_parameters+=sum(int(row[0]==0 and row[1]==0) for row in parameters)
            inputs.append([x for row in source for x in row])
            outputs.append([int(x) for row in parameters for x in row]+[scale])
        values=np.array(inputs,dtype=np.int64);expected=np.array(outputs,dtype=np.int64)
        masks=rng.integers(0,4096,size=expected.shape,dtype=np.int64)
        phases=np.array([sum((int(x)&int(m)).bit_count() for x,m in zip(row,mask))&1
                         for row,mask in zip(expected,masks)],dtype=bool)
        circuit,jets,probe=build(nodes)
        payload,repeated=io.BytesIO(),io.BytesIO()
        circuit.to_file(payload,format='kmb');build(nodes)[0].to_file(repeated,format='kmb')
        assert payload.getvalue()==repeated.getvalue()
        assert circuit.operation_statistics().num_toffoli_like==84*nodes*nodes+456*nodes-168
        assert circuit.num_qubits==24*nodes+36
        scratch=[km.q(i) for i in range(24*nodes,circuit.num_qubits)]
        for seed in range(4):
            sim=km.Simulator(batch_size=shots,seed=seed);sim.use_same_registers_as(circuit)
            for j,word in enumerate([word for jet in jets for word in jet]):
                sim.write_across_shots(word,bit_matrix(values[:,j],12))
            for j in range(2*nodes+1):
                sim.write_across_shots(probe[12*j:12*(j+1)],bit_matrix(masks[:,j],12))
            sim.do(circuit)
            for j,word in enumerate([word for jet in jets for word in jet]):
                assert np.array_equal(sim.read_across_shots(word),bit_matrix(values[:,j],12))
            assert not sim.read_across_shots(scratch).any()
            assert np.array_equal(sim.read_phase_flipped_across_shots(),phases)
        report['cases'].append(dict(nodes=nodes,T=circuit.operation_statistics().num_toffoli_like,
                                    Q=circuit.num_qubits,extra_qubits=circuit.num_qubits-24*nodes,
                                    shots_per_seed=shots,seeds=4,pole_parameters=pole_parameters,
                                    double_pole_parameters=double_pole_parameters,
                                    parameter_samples_rejected_initial_pole=rejected,
                                    byte_identical_fresh_builds=True,operations=len(circuit),
                                    sha256=hashlib.sha256(payload.getvalue()).hexdigest()))
        if destination:(destination.parent.parent/'circuits'/f'carry-key-t{nodes}.kmb').write_bytes(payload.getvalue())
    report['degree35_model']=dict(T_roundtrip=84*35*35+456*35-168,Q=876,Q_with_one_bit=877,
                                  status='normal extraction extrapolation only; finite-zero lookahead and terminal controller excluded')
    if destination:destination.write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':print(json.dumps(run_checks(Path(sys.argv[1]) if len(sys.argv)>1 else None),indent=2))
