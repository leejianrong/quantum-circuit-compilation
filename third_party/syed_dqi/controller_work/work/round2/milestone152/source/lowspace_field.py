# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""In-place tower inverses and batched quotient phases with small workspace."""
from __future__ import annotations
from functools import cache
import hashlib
import io
import json
from pathlib import Path
import sys
import kickmix as km
import numpy as np
from field_tensor import invert_binary_columns,multiplication_tensor
from tower_inverse import (quadratic_basis,apply_inplace_linear,rows_from_columns,
                           init_norm,erase_norm,xor_product,erase_product,phase_product,kernel)
from quantum_reciprocal import bit_matrix,compose_mask

@cache
def transpositions_three():
    field=km.GF2Field(3);result=[]
    for value in range(1,8):
        inverse=field.invert(value)
        if value>=inverse:continue
        direction=value^inverse
        columns=[direction];span={0,direction}
        for basis in (1,2,4):
            if basis not in span:
                columns.append(basis);span|={x^basis for x in tuple(span)}
        assert len(columns)==3
        result.append((value,invert_binary_columns(columns),rows_from_columns(columns)))
    assert len(result)==3
    return tuple(result)

def inverse_three(builder,source):
    for value,to_basis,from_basis in transpositions_three():
        offset=[source[j] for j in range(3) if value>>j&1]
        builder.x(offset)
        apply_inplace_linear(builder,source,to_basis)
        builder.x(source[1:])
        builder.ccx(source[1],source[2],source[0])
        builder.x(source[1:])
        apply_inplace_linear(builder,source,from_basis)
        builder.x(offset)

def invert(builder,source):
    degree=len(source)
    if degree==3:
        inverse_three(builder,source);return
    assert degree in (6,12)
    info=quadratic_basis(degree);half=degree//2
    apply_inplace_linear(builder,source,info['to_tower'])
    left,right=source[:half],source[half:]
    norm=init_norm(builder,left,right,info['delta'])
    invert(builder,norm)
    temporary=builder.alloc_qubits(half)
    measured=[]
    for word in (left,right):
        xor_product(builder,word,norm,temporary)
        builder.swap(word,temporary)
        mask=builder.alloc_bits(half);builder.hmr(temporary,mask);measured.append(mask)
    builder.free(temporary)
    builder.cx(right,left)
    # norm currently holds inverse(old norm). Temporarily restore the old norm
    # to repay both old-coordinate phases using the new inverse coordinates.
    invert(builder,norm)
    builder.cx(right,left)
    phase_product(builder,left,norm,measured[0],kernel(half))
    builder.cx(right,left)
    phase_product(builder,right,norm,measured[1],kernel(half))
    for mask in measured:builder.free(mask)
    invert(builder,norm)
    erase_norm(builder,left,right,norm,info['delta']);builder.free(norm)
    apply_inplace_linear(builder,source,info['from_tower'])

@cache
def partial_inverse_product_terms(component,frobenius_power):
    assert component in (0,1)
    assert frobenius_power>=1 and frobenius_power&(frobenius_power-1)==0
    field=km.GF2Field(12);rows=quadratic_basis(12)['from_tower']
    columns=[]
    for bit in range(6):
        original=sum(((row>>(6*component+bit))&1)<<out for out,row in enumerate(rows))
        columns.append(field.pow(original,frobenius_power))
    result=[]
    for left,right,output in multiplication_tensor():
        projected=compose_mask(right,columns)
        if projected:result.append((left,projected,output))
    return tuple(result)

def phase_quotients(builder,source,targets):
    """Phase by sum dot(mask,word*inverse(source)^power).

    targets contains(word,classical_mask,power), with power a power of two.
    Source is restored; inverse(0) is defined as0. Targets must not alias source.
    """
    assert len(source)==12
    info=quadratic_basis(12)
    apply_inplace_linear(builder,source,info['to_tower'])
    left,right=source[:6],source[6:]
    norm=init_norm(builder,left,right,info['delta'])
    invert(builder,norm)
    temporary=builder.alloc_qubits(6)
    for component,word in enumerate((left,right)):
        if component==0:builder.cx(right,left)
        xor_product(builder,word,norm,temporary)
        for value,mask,power in targets:
            phase_product(builder,value,temporary,mask,partial_inverse_product_terms(component,power))
        erase_product(builder,word,norm,temporary)
        if component==0:builder.cx(right,left)
    builder.free(temporary)
    invert(builder,norm)
    erase_norm(builder,left,right,norm,info['delta']);builder.free(norm)
    apply_inplace_linear(builder,source,info['from_tower'])

def build_inverse(degree):
    builder=km.CircuitBuilder();source=builder.create_quantum_register(degree,'value')
    mask=builder.create_classical_register(degree,'inverse_phase_probe')
    invert(builder,source);builder.cz(mask,source);invert(builder,source)
    return builder.finish_circuit(),source,mask

def build_phase():
    builder=km.CircuitBuilder()
    source=builder.create_quantum_register(12,'denominator')
    values=[builder.create_quantum_register(12,f'numerator_{i}') for i in range(3)]
    masks=[builder.create_classical_register(12,f'phase_mask_{i}') for i in range(3)]
    phase_quotients(builder,source,[(word,mask,power) for word,mask,power in zip(values,masks,(1,2,4))])
    return builder.finish_circuit(),source,values,masks

def run_checks(destination=None):
    rng=np.random.default_rng(2026110828)
    result=dict(status='PASS_lowspace_field_components_only',failures=0,inverses=[])
    for degree,one_pass,scratch_expected in ((3,3,0),(6,27,6),(12,126,12)):
        field=km.GF2Field(degree);shots=8192
        data=np.arange(shots,dtype=np.int64)%(1<<degree)
        masks=rng.integers(0,1<<degree,size=shots,dtype=np.int64)
        inverse=[field.invert(int(value)) if value else 0 for value in data]
        phases=np.array([(value&int(mask)).bit_count()&1 for value,mask in zip(inverse,masks)],dtype=bool)
        circuit,source,probe=build_inverse(degree)
        payload,repeated=io.BytesIO(),io.BytesIO()
        circuit.to_file(payload,format='kmb');build_inverse(degree)[0].to_file(repeated,format='kmb')
        assert payload.getvalue()==repeated.getvalue()
        assert circuit.operation_statistics().num_toffoli_like==2*one_pass
        assert circuit.num_qubits==degree+scratch_expected
        scratch=[km.q(i) for i in range(degree,circuit.num_qubits)]
        for seed in range(4):
            sim=km.Simulator(batch_size=shots,seed=seed);sim.use_same_registers_as(circuit)
            sim.write_across_shots(source,bit_matrix(data,degree))
            sim.write_across_shots(probe,bit_matrix(masks,degree));sim.do(circuit)
            assert np.array_equal(sim.read_across_shots(source),bit_matrix(data,degree))
            assert not sim.read_across_shots(scratch).any()
            assert np.array_equal(sim.read_phase_flipped_across_shots(),phases)
        result['inverses'].append(dict(degree=degree,T_per_direction=one_pass,T_roundtrip=2*one_pass,
                                       Q=circuit.num_qubits,scratch_qubits=scratch_expected,
                                       exhaustive_values=1<<degree,shots_per_seed=shots,seeds=4,
                                       byte_identical_fresh_builds=True,sha256=hashlib.sha256(payload.getvalue()).hexdigest()))
        if destination:(destination.parent.parent/'circuits'/f'low-inverse-{degree}.kmb').write_bytes(payload.getvalue())
    field=km.GF2Field(12);shots=8192
    denominators=np.arange(shots,dtype=np.int64)%4096
    numerators=rng.integers(0,4096,size=(shots,3),dtype=np.int64)
    masks=rng.integers(0,4096,size=(shots,3),dtype=np.int64)
    phases=[]
    for denominator,row,mask in zip(denominators,numerators,masks):
        inverse=field.invert(int(denominator)) if denominator else 0
        products=[field.mul(int(value),field.pow(inverse,power)) for value,power in zip(row,(1,2,4))]
        phases.append(sum((value&int(m)).bit_count() for value,m in zip(products,mask))&1)
    circuit,source,words,probes=build_phase()
    payload,repeated=io.BytesIO(),io.BytesIO()
    circuit.to_file(payload,format='kmb');build_phase()[0].to_file(repeated,format='kmb')
    assert payload.getvalue()==repeated.getvalue()
    assert circuit.operation_statistics().num_toffoli_like==99
    assert circuit.num_qubits==60
    scratch=[km.q(i) for i in range(48,circuit.num_qubits)]
    for seed in range(4):
        sim=km.Simulator(batch_size=shots,seed=seed);sim.use_same_registers_as(circuit)
        sim.write_across_shots(source,bit_matrix(denominators,12))
        for j,(word,probe) in enumerate(zip(words,probes)):
            sim.write_across_shots(word,bit_matrix(numerators[:,j],12))
            sim.write_across_shots(probe,bit_matrix(masks[:,j],12))
        sim.do(circuit)
        assert np.array_equal(sim.read_across_shots(source),bit_matrix(denominators,12))
        for j,word in enumerate(words):assert np.array_equal(sim.read_across_shots(word),bit_matrix(numerators[:,j],12))
        assert not sim.read_across_shots(scratch).any()
        assert np.array_equal(sim.read_phase_flipped_across_shots(),np.array(phases,dtype=bool))
    result['quotient_phase']=dict(T=99,Q=circuit.num_qubits,scratch_qubits=12,
                                   simultaneous_words=3,inverse_powers=[1,2,4],
                                   shots_per_seed=shots,seeds=4,all_denominator_values=True,
                                   byte_identical_fresh_builds=True,sha256=hashlib.sha256(payload.getvalue()).hexdigest())
    if destination:
        (destination.parent.parent/'circuits'/'low-quotient-phase.kmb').write_bytes(payload.getvalue())
        destination.write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(run_checks(Path(sys.argv[1]) if len(sys.argv)>1 else None),indent=2))
