# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""A certified scalar inverse-trace circuit, derived by this task's SAT search."""
from functools import cache
import hashlib
import io
import json
from pathlib import Path
import sys
import kickmix as km
import numpy as np
from field_tensor import invert_binary_columns,parity_pivot
from tower_inverse import apply_inplace_linear,quadratic_basis,xor_product,kernel
from quantum_reciprocal import bit_matrix,xor_linear

# Original search certificate: thirteen small integers, not a truth table.
GATES=((27,28),(32,50),(89,127),(228,273),(146,293),(26,843))
OUTPUT=3100
FIELD=km.GF2Field(6)

def model():
    return dict(T=4,scratch=6,fixed_phase_scratch=4,expected_uniform_mask_T=4*63/64,
                quantum_controlled_T=6,quantum_controlled_scratch=6)


def trace(value):
    answer=0
    for _ in range(6):answer^=value;value=FIELD.mul(value,value)
    assert answer in (0,1)
    return answer


@cache
def certificate():
    for value in range(64):
        bits=value
        for j,(a,b) in enumerate(GATES):
            bits|=(((a&bits).bit_count()%2)&((b&bits).bit_count()%2))<<(6+j)
        expected=trace(FIELD.invert(value)) if value else 0
        assert (bits&OUTPUT).bit_count()%2==expected
    return True


def independent(vectors):
    pivots={}
    for value in vectors:
        while value:
            bit=value.bit_length()-1
            if bit not in pivots:pivots[bit]=value;break
            value^=pivots[bit]
        if not value:return False
    return True


@cache
def operand_basis(width,left,right):
    rows=[left,right]
    assert independent(rows)
    for j in range(width):
        if independent(rows+[1<<j]):rows.append(1<<j)
    assert len(rows)==width
    columns=[sum(((row>>j)&1)<<i for i,row in enumerate(rows)) for j in range(width)]
    return tuple(rows),invert_binary_columns(columns)


def fixed_trace_phase(builder,source,root=True):
    assert len(source)==6 and certificate()
    signals=list(source);records=[]
    # The last two AND outputs are leaves used only by the final Z phase.
    # With a fixed outer phase their AND/Z/erase is exactly a Clifford CZ.
    count=4 if root is True else 6
    assert all((left|right)<1<<10 for left,right in GATES[4:])
    for left,right in GATES[:count]:
        rows,undo=operand_basis(len(signals),left,right)
        view=km.array(signals);apply_inplace_linear(builder,view,rows)
        target=builder.alloc_qubits(1);builder.init_and(view[0],view[1],target[0])
        apply_inplace_linear(builder,view,undo)
        records.append((view,target,rows,undo));signals.append(target[0])
    if count==4:
        for left,right in GATES[4:]:
            rows,undo=operand_basis(len(signals),left,right)
            view=km.array(signals);apply_inplace_linear(builder,view,rows)
            builder.cz(view[0],view[1])
            apply_inplace_linear(builder,view,undo)
    chosen=km.array([wire for j,wire in enumerate(signals) if OUTPUT>>j&1])
    builder.cz(root,chosen)
    for view,target,rows,undo in reversed(records):
        apply_inplace_linear(builder,view,rows)
        builder.del_and(view[0],view[1],target[0]);builder.free(target)
        apply_inplace_linear(builder,view,undo)


@cache
def trace_dual_columns():
    rows=quadratic_basis(6)['to_tower'];answer=[]
    for row in rows:
        scalar=next(mu for mu in range(64) if all(trace(FIELD.mul(mu,1<<j))==((row>>j)&1) for j in range(6)))
        answer.append(scalar)
    return tuple(answer)


def classical_word(builder):
    word=builder.alloc_bits(6);builder.bit_store(word,False);return word


def classical_product(builder,left,right):
    target=classical_word(builder)
    for a,b,output in kernel(6):
        x=parity_pivot(builder,left,a);y=parity_pivot(builder,right,b)
        builder.push_condition(x)
        builder.cx(y,km.array([target[j] for j in range(6) if output>>j&1]))
        builder.pop_condition()
        parity_pivot(builder,right,b);parity_pivot(builder,left,a)
    return target


def classical_inverse(builder,source):
    value=source;owned=[]
    columns=tuple(FIELD.mul(1<<j,1<<j) for j in range(6))
    for bit in bin(62)[3:]:
        squared=classical_word(builder);owned.append(squared)
        xor_linear(builder,value,squared,columns);value=squared
        if bit=='1':value=classical_product(builder,value,source);owned.append(value)
    return value,owned


def classical_scale(builder,source,multiplier,inverse_multiplier):
    temporary=builder.alloc_qubits(6)
    xor_product(builder,source,multiplier,temporary)
    builder.swap(source,temporary)
    xor_product(builder,source,inverse_multiplier,temporary)
    builder.free(temporary)


def phase_inverse_six(builder,source,mask_in_tower_basis,root=True):
    """Phase root*dot(mask,tower(inverse(source))), restoring every input."""
    assert len(source)==len(mask_in_tower_basis)==6
    mu=classical_word(builder);xor_linear(builder,mask_in_tower_basis,mu,trace_dual_columns())
    reciprocal,owned=classical_inverse(builder,mu)
    active=builder.alloc_bits(1);builder.bit_store(active,False)
    builder.bit_store(active[0],True,control=mu)
    builder.push_condition(active[0])
    classical_scale(builder,source,reciprocal,mu)
    fixed_trace_phase(builder,source,root)
    classical_scale(builder,source,mu,reciprocal)
    builder.pop_condition()
    for word in owned:builder.free(word)
    builder.free(active);builder.free(mu)


def build():
    builder=km.CircuitBuilder();source=builder.create_quantum_register(6,'source')
    root=builder.create_quantum_register(1,'root')
    mask=builder.create_classical_register(6,'tower_mask')
    phase_inverse_six(builder,source,mask,root[0])
    return builder.finish_circuit(),source,root,mask


def run_checks(destination=None):
    shots=8192;indices=np.arange(shots,dtype=np.int64)
    values=indices%64;masks=(indices//64)%64;roots=indices//4096
    rows=quadratic_basis(6)['to_tower'];phases=[]
    for value,mask,root in zip(values,masks,roots):
        inverse=FIELD.invert(int(value)) if value else 0
        tower=sum(((row&inverse).bit_count()%2)<<j for j,row in enumerate(rows))
        phases.append(bool(root and (tower&int(mask)).bit_count()%2))
    circuit,source,root,mask=build();payload,repeated=io.BytesIO(),io.BytesIO()
    circuit.to_file(payload,format='kmb');build()[0].to_file(repeated,format='kmb')
    assert payload.getvalue()==repeated.getvalue()
    assert circuit.operation_statistics().num_toffoli_like==6,circuit.operation_statistics()
    assert circuit.num_qubits==13,circuit.num_qubits
    means=[]
    for seed in range(4):
        sim=km.Simulator(batch_size=shots,seed=seed,counting_operations=True);sim.use_same_registers_as(circuit)
        sim.write_across_shots(source,bit_matrix(values,6));sim.write_across_shots(root,bit_matrix(roots,1))
        sim.write_across_shots(mask,bit_matrix(masks,6));sim.do(circuit)
        assert np.array_equal(sim.read_across_shots(source),bit_matrix(values,6)),(seed,'source')
        assert np.array_equal(sim.read_across_shots(root),bit_matrix(roots,1)),(seed,'root')
        assert np.array_equal(sim.read_across_shots(mask),bit_matrix(masks,6)),(seed,'mask')
        assert not sim.read_across_shots([km.q(i) for i in range(7,13)]).any(),(seed,'scratch')
        assert np.array_equal(sim.read_phase_flipped_across_shots(),np.array(phases,dtype=bool)),(seed,'phase')
        mean=sim.operation_statistics().num_toffoli_like/shots;means.append(mean)
        assert mean==6*63/64,mean
    result=dict(status='PASS_SIX_AND_WEIGHTED_INVERSE_PHASE',T_static=6,Q=13,scratch=6,
                expected_uniform_mask_mean_T=6*63/64,measured_mean_T_by_seed=means,
                exhaustive_source_mask_root_triples=shots,seeds=4,certificate_all_field_inputs=True,
                byte_identical_fresh_builds=True,sha256=hashlib.sha256(payload.getvalue()).hexdigest(),
                limitations='GF64 scalar phase only. No minimum-gate proof; GF4096 inverse-trace synthesis and full decoder integration remain separate.')
    if destination:
        (destination.parent.parent/'circuits/scalar-inverse-phase-six.kmb').write_bytes(payload.getvalue())
        destination.write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps(run_checks(Path(sys.argv[1]) if len(sys.argv)>1 else None),indent=2))
