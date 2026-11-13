# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""70-T field inverse and quotient phases using an invariant norm difference."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import sys
import kickmix as km
import numpy as np
from tower_inverse import (quadratic_basis,apply_inplace_linear,init_norm,erase_norm,
                           init_inverse,init_inverse_three,erase_inverse_three,
                           xor_product,erase_product,phase_product,kernel)
from lowspace_field import partial_inverse_product_terms
from quantum_reciprocal import bit_matrix

from scalar_inverse_phase import phase_inverse_six


def difference_cache(builder,norm):
    """Return n+1/n, erasing the temporary21T inverse's scaffolds."""
    assert len(norm)==6
    cached=builder.alloc_qubits(6)
    scaffold=init_inverse(builder,norm,cached)
    assert scaffold['child'] is None
    erase_inverse_three(builder,scaffold['norm'],scaffold['inverse_norm'])
    builder.free(scaffold['inverse_norm'])
    info=quadratic_basis(6)
    apply_inplace_linear(builder,norm,info['to_tower'])
    erase_norm(builder,norm[:3],norm[3:],scaffold['norm'],info['delta'])
    builder.free(scaffold['norm'])
    apply_inplace_linear(builder,norm,info['from_tower'])
    builder.cx(norm,cached)
    return cached

def erase_difference_cache(builder,current_norm,cached):
    """The same difference is valid at either n or1/n, includingzero."""
    info=quadratic_basis(6)
    apply_inplace_linear(builder,cached,info['to_tower'])
    mask=builder.alloc_bits(6);builder.hmr(cached,mask);builder.free(cached)
    apply_inplace_linear(builder,current_norm,info['to_tower'])
    builder.cz(mask,current_norm)
    apply_inplace_linear(builder,current_norm,info['from_tower'])
    phase_inverse_six(builder,current_norm,mask)
    builder.free(mask)

def invert_twelve(builder,source):
    assert len(source)==12
    info=quadratic_basis(12)
    apply_inplace_linear(builder,source,info['to_tower'])
    left,right=source[:6],source[6:]
    norm=init_norm(builder,left,right,info['delta'])
    cached=difference_cache(builder,norm)
    builder.cx(cached,norm)
    temporary=builder.alloc_qubits(6);masks=[]
    for word in (left,right):
        xor_product(builder,word,norm,temporary)
        builder.swap(word,temporary)
        mask=builder.alloc_bits(6);builder.hmr(temporary,mask);masks.append(mask)
    builder.free(temporary)
    builder.cx(right,left)
    builder.cx(cached,norm)
    builder.cx(right,left)
    phase_product(builder,left,norm,masks[0],kernel(6))
    builder.cx(right,left)
    phase_product(builder,right,norm,masks[1],kernel(6))
    for mask in masks:builder.free(mask)
    builder.cx(cached,norm)
    erase_difference_cache(builder,norm,cached)
    erase_norm(builder,left,right,norm,info['delta']);builder.free(norm)
    apply_inplace_linear(builder,source,info['from_tower'])

def phase_quotients(builder,source,targets):
    assert len(source)==12
    info=quadratic_basis(12)
    apply_inplace_linear(builder,source,info['to_tower'])
    left,right=source[:6],source[6:]
    norm=init_norm(builder,left,right,info['delta'])
    cached=difference_cache(builder,norm);builder.cx(cached,norm)
    temporary=builder.alloc_qubits(6)
    for component,word in enumerate((left,right)):
        if component==0:builder.cx(right,left)
        xor_product(builder,word,norm,temporary)
        for value,mask,power in targets:
            phase_product(builder,value,temporary,mask,partial_inverse_product_terms(component,power))
        erase_product(builder,word,norm,temporary)
        if component==0:builder.cx(right,left)
    builder.free(temporary)
    builder.cx(cached,norm)
    erase_difference_cache(builder,norm,cached)
    erase_norm(builder,left,right,norm,info['delta']);builder.free(norm)
    apply_inplace_linear(builder,source,info['from_tower'])

def build_inverse():
    builder=km.CircuitBuilder();source=builder.create_quantum_register(12,'value')
    mask=builder.create_classical_register(12,'inverse_phase_probe')
    invert_twelve(builder,source);builder.cz(mask,source);invert_twelve(builder,source)
    return builder.finish_circuit(),source,mask

def build_phase():
    builder=km.CircuitBuilder();source=builder.create_quantum_register(12,'denominator')
    values=[builder.create_quantum_register(12,f'numerator_{j}') for j in range(3)]
    masks=[builder.create_classical_register(12,f'mask_{j}') for j in range(3)]
    phase_quotients(builder,source,list(zip(values,masks,(1,2,4))))
    return builder.finish_circuit(),source,values,masks

def run_checks(destination=None):
    rng=np.random.default_rng(2026110837);field=km.GF2Field(12);shots=8192
    data=np.arange(shots,dtype=np.int64)%4096
    masks=rng.integers(0,4096,size=shots,dtype=np.int64)
    inverses=[field.invert(int(value)) if value else 0 for value in data]
    phases=np.array([(value&int(mask)).bit_count()&1 for value,mask in zip(inverses,masks)],dtype=bool)
    circuit,source,probe=build_inverse()
    payload,repeated=io.BytesIO(),io.BytesIO()
    circuit.to_file(payload,format='kmb');build_inverse()[0].to_file(repeated,format='kmb')
    assert payload.getvalue()==repeated.getvalue()
    assert circuit.operation_statistics().num_toffoli_like==140 and circuit.num_qubits==30
    scratch=[km.q(i) for i in range(12,circuit.num_qubits)]
    for seed in range(4):
        sim=km.Simulator(batch_size=shots,seed=seed);sim.use_same_registers_as(circuit)
        sim.write_across_shots(source,bit_matrix(data,12));sim.write_across_shots(probe,bit_matrix(masks,12));sim.do(circuit)
        assert np.array_equal(sim.read_across_shots(source),bit_matrix(data,12))
        assert not sim.read_across_shots(scratch).any()
        assert np.array_equal(sim.read_phase_flipped_across_shots(),phases)
    result=dict(status='PASS_SCALAR_PHASE_NORM_CACHE_COMPONENTS',failures=0,
                inverse=dict(T_per_direction=70,T_roundtrip=140,Q=30,scratch_qubits=18,
                             all4096_values=True,shots_per_seed=shots,seeds=4,
                             byte_identical_fresh_builds=True,sha256=hashlib.sha256(payload.getvalue()).hexdigest()))
    if destination:(destination.parent.parent/'circuits'/'inverse-norm-cache.kmb').write_bytes(payload.getvalue())
    values=rng.integers(0,4096,size=(shots,3),dtype=np.int64)
    masks=rng.integers(0,4096,size=(shots,3),dtype=np.int64);phases=[]
    for inv,row,mask in zip(inverses,values,masks):
        products=[field.mul(int(value),field.pow(inv,power)) for value,power in zip(row,(1,2,4))]
        phases.append(sum((value&int(m)).bit_count() for value,m in zip(products,mask))&1)
    circuit,source,words,probes=build_phase();payload,repeated=io.BytesIO(),io.BytesIO()
    circuit.to_file(payload,format='kmb');build_phase()[0].to_file(repeated,format='kmb')
    assert payload.getvalue()==repeated.getvalue()
    assert circuit.operation_statistics().num_toffoli_like==70 and circuit.num_qubits==66
    scratch=[km.q(i) for i in range(48,circuit.num_qubits)]
    for seed in range(4):
        sim=km.Simulator(batch_size=shots,seed=seed);sim.use_same_registers_as(circuit)
        sim.write_across_shots(source,bit_matrix(data,12))
        for j,(word,probe) in enumerate(zip(words,probes)):
            sim.write_across_shots(word,bit_matrix(values[:,j],12));sim.write_across_shots(probe,bit_matrix(masks[:,j],12))
        sim.do(circuit)
        assert np.array_equal(sim.read_across_shots(source),bit_matrix(data,12))
        for j,word in enumerate(words):assert np.array_equal(sim.read_across_shots(word),bit_matrix(values[:,j],12))
        assert not sim.read_across_shots(scratch).any()
        assert np.array_equal(sim.read_phase_flipped_across_shots(),np.array(phases,dtype=bool))
    result['quotient_phase']=dict(T=70,Q=66,scratch_qubits=18,simultaneous_words=3,inverse_powers=[1,2,4],
                                  all4096_denominators=True,shots_per_seed=shots,seeds=4,
                                  byte_identical_fresh_builds=True,sha256=hashlib.sha256(payload.getvalue()).hexdigest())
    result['limitations']='Targets must not alias source; inverse exponents must be powers of two. Space tradeoff, not a full decoder.'
    if destination:
        (destination.parent.parent/'circuits'/'phase-norm-cache.kmb').write_bytes(payload.getvalue())
        destination.write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(run_checks(Path(sys.argv[1]) if len(sys.argv)>1 else None),indent=2))
