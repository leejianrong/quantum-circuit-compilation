# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""Root-mask scan using the two existing constant-coefficient words."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import sys
import kickmix as km
import numpy as np
from quantum_reciprocal import bit_matrix,xor_linear
from tower_inverse import apply_inplace_linear,rows_from_columns,sum_trace

def product(a,b,field):
    out=[0]*(len(a)+len(b)-1)
    for i,x in enumerate(a):
        for j,y in enumerate(b):out[i+j]^=field.mul(int(x),int(y))
    return out

def evaluate(poly,x,field):
    value=0
    for coefficient in reversed(poly):value=field.mul(value,x)^int(coefficient)
    return value

def known_reweight(x,field,nodes):
    """Invert x*M(x), omitting its squared vanishing factor at a node.

    The proper numerator's residue at a physical node a is e*a*M_a(a).
    The node-zero scan position is absent. Distinct interpolation nodes and
    a nonzero x therefore always give a unit scale in this stated gauge.
    """
    assert x and len(set(nodes))==len(nodes)
    value=x
    for node in nodes:
        if node!=x:value=field.mul(value,field.mul(x^node,x^node))
    assert value
    return field.invert(value)

def fixed_scale(builder,word,value,field):
    assert value
    if value==1:return
    columns=[field.mul(value,1<<bit) for bit in range(field.degree)]
    apply_inplace_linear(builder,word,rows_from_columns(columns))

def emit(builder,locator,values,masks,field,nodes=(),leading=None):
    degree=len(locator);bits=field.degree
    assert degree==len(values) and len(masks)==(1<<bits)-1
    ladder=builder.alloc_qubits(bits-1)
    previous=[1]+[0]*degree
    def move(point):
        nonlocal previous
        powers=[1]
        for _ in range(degree):powers.append(field.mul(powers[-1],point))
        for i in range(1,degree):
            coefficient=powers[i]^previous[i]
            columns=tuple(field.mul(coefficient,1<<bit) for bit in range(bits))
            xor_linear(builder,locator[i],locator[0],columns)
            xor_linear(builder,values[i],values[0],columns)
        constant=powers[degree]^previous[degree]
        if leading is None:
            for bit in range(bits):
                if constant>>bit&1:builder.x(locator[0][bit])
        else:
            assert len(leading)==bits and not set(leading)&set(locator[0])
            columns=tuple(field.mul(constant,1<<bit) for bit in range(bits))
            xor_linear(builder,leading,locator[0],columns)
        previous=powers
    point=1
    for position,mask in enumerate(masks):
        move(point)
        factor=known_reweight(point,field,nodes) if nodes else 1
        fixed_scale(builder,values[0],factor,field)
        builder.x(locator[0])
        builder.init_and(locator[0][0],locator[0][1],ladder[0])
        for i in range(1,bits-1):builder.init_and(ladder[i-1],locator[0][i+1],ladder[i])
        builder.ccz(mask,ladder[-1],values[0])
        for i in reversed(range(1,bits-1)):builder.del_and(ladder[i-1],locator[0][i+1],ladder[i])
        builder.del_and(locator[0][0],locator[0][1],ladder[0])
        builder.x(locator[0])
        fixed_scale(builder,values[0],field.invert(factor),field)
        point=field.mul(point,field.primitive_element)
    assert point==1
    move(0)
    builder.free(ladder)

def build(bits,degree,reweighted=True):
    field=km.GF2Field(bits);builder=km.CircuitBuilder()
    locator=[builder.create_quantum_register(bits,f'D{i}') for i in range(degree)]
    values=[builder.create_quantum_register(bits,f'R{i}') for i in range(degree)]
    retained=builder.create_quantum_register(bits,'retained_scale')
    masks=[builder.create_classical_register(bits,f'E{i}') for i in range((1<<bits)-1)]
    emit(builder,locator,values,masks,field,tuple(range(degree)) if reweighted else ())
    return builder.finish_circuit(),locator,values,retained,masks

def padding(field,gap):
    result=[0,1] if gap&1 else [1]
    deltas=[x for x in range(1,1<<field.degree) if sum_trace(x,field)==1]
    assert len(deltas)>=gap//2
    for delta in deltas[:gap//2]:result=product(result,[delta,1,1],field)
    return result

def run_checks(full=False,destination=None):
    rng=np.random.default_rng(2026110832)
    result=dict(status='PASS_FIXED_DEGREE_SCAN_ONLY',failures=0,cases=[])
    configurations=((12,35,256),) if full else ((3,3,1024),(4,5,1024))
    for bits,degree,shots in configurations:
        field=km.GF2Field(bits);q=1<<bits;positions=q-1
        points=[field.pow(field.primitive_element,j) for j in range(positions)]
        assert len(set(points))==positions
        index={point:j for j,point in enumerate(points)}
        locator_inputs=[];supports=[];weights=[]
        for shot in range(shots):
            weight=shot%(degree+1)
            support=[int(x) for x in rng.choice(np.arange(1,q),size=weight,replace=False)]
            if weight and shot%4==0 and 1 not in support:support[0]=1
            locator=[1]
            for root in support:locator=product(locator,[root,1],field)
            locator=product(locator,padding(field,degree-weight),field)
            assert len(locator)==degree+1 and locator[-1]==1
            locator_inputs.append(locator[:-1]);supports.append(support);weights.append(weight)
        locator_inputs=np.array(locator_inputs,dtype=np.int64)
        value_inputs=rng.integers(0,q,size=(shots,degree),dtype=np.int64)
        mask_inputs=rng.integers(0,q,size=(shots,positions),dtype=np.int64)
        scale_inputs=rng.integers(0,q,size=shots,dtype=np.int64)
        expected=[]
        for shot,support in enumerate(supports):
            parity=0
            for root in support:
                value=evaluate(value_inputs[shot],root,field)
                value=field.mul(value,known_reweight(root,field,tuple(range(degree))))
                parity^=(value&int(mask_inputs[shot,index[root]])).bit_count()&1
            expected.append(parity)
        circuit,D,R,scale,masks=build(bits,degree)
        payload,repeated=io.BytesIO(),io.BytesIO()
        circuit.to_file(payload,format='kmb');build(bits,degree)[0].to_file(repeated,format='kmb')
        assert payload.getvalue()==repeated.getvalue()
        expected_T=(bits-1)*positions;input_count=(2*degree+1)*bits
        assert circuit.operation_statistics().num_toffoli_like==expected_T
        assert circuit.num_qubits==input_count+bits-1
        scratch=[km.q(i) for i in range(input_count,circuit.num_qubits)]
        for seed in range(4):
            sim=km.Simulator(batch_size=shots,seed=seed);sim.use_same_registers_as(circuit)
            for j,word in enumerate(D):sim.write_across_shots(word,bit_matrix(locator_inputs[:,j],bits))
            for j,word in enumerate(R):sim.write_across_shots(word,bit_matrix(value_inputs[:,j],bits))
            sim.write_across_shots(scale,bit_matrix(scale_inputs,bits))
            for j,mask in enumerate(masks):sim.write_across_shots(mask,bit_matrix(mask_inputs[:,j],bits))
            sim.do(circuit)
            for j,word in enumerate(D):assert np.array_equal(sim.read_across_shots(word),bit_matrix(locator_inputs[:,j],bits))
            for j,word in enumerate(R):assert np.array_equal(sim.read_across_shots(word),bit_matrix(value_inputs[:,j],bits))
            assert np.array_equal(sim.read_across_shots(scale),bit_matrix(scale_inputs,bits))
            assert not sim.read_across_shots(scratch).any()
            assert np.array_equal(sim.read_phase_flipped_across_shots(),np.array(expected,dtype=bool))
        result['cases'].append(dict(field_bits=bits,locator_degree=degree,T=expected_T,Q=circuit.num_qubits,
                                    scratch_qubits=bits-1,retained_scale_qubits=bits,
                                    scanned_positions=positions,shots_per_seed=shots,seeds=4,
                                    real_root_weights=sorted(set(weights)),
                                    cases_with_interpolation_node_roots=sum(any(x in range(degree) for x in support) for support in supports),
                                    squarefree_padding_included=True,known_reweighting_enabled=True,
                                    byte_identical_fresh_builds=True,operations=len(circuit),
                                    sha256=hashlib.sha256(payload.getvalue()).hexdigest()))
        if destination:(destination.parent.parent/'circuits'/f'scan-b{bits}-d{degree}.kmb').write_bytes(payload.getvalue())
    result['limitations']='Requires a fixed-degree monic locator and a supplied scan-ready value polynomial. Does not implement conversion, variable-degree preparation or key node-residue integration.'
    if destination:destination.write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    full='--full' in sys.argv
    destination=Path(next(x for x in sys.argv[1:] if x!='--full')) if len(sys.argv)>1 else None
    print(json.dumps(run_checks(full,destination),indent=2))
