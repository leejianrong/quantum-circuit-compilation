# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""GF(2^24) inverse with a smaller, explicitly recycled norm scaffold."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import kickmix as km
import numpy as np

from quantum_reciprocal import bit_matrix
from tower_inverse import (quadratic_basis, apply_inplace_linear, init_norm,
                           erase_norm, init_inverse, erase_inverse_three,
                           xor_product, erase_product, phase_product, kernel,
                           extension_inverse)


def erase_norm_original_basis(builder, source, norm):
    info=quadratic_basis(len(source))
    half=len(source)//2
    apply_inplace_linear(builder,source,info['to_tower'])
    erase_norm(builder,source[:half],source[half:],norm,info['delta'])
    apply_inplace_linear(builder,source,info['from_tower'])


def inverse_with_supplied_norm_inverse(builder, source, norm_inverse, target, erase=False):
    info=quadratic_basis(len(source))
    half=len(source)//2
    apply_inplace_linear(builder,source,info['to_tower'])
    if erase:
        apply_inplace_linear(builder,target,info['to_tower'])
    left,right=source[:half],source[half:]
    operation=erase_product if erase else xor_product
    builder.cx(right,left)
    operation(builder,left,norm_inverse,target[:half])
    builder.cx(right,left)
    operation(builder,right,norm_inverse,target[half:])
    apply_inplace_linear(builder,source,info['from_tower'])
    if not erase:
        apply_inplace_linear(builder,target,info['from_tower'])


def invert_inplace_low_space(builder, source):
    assert len(source)==24
    info12=quadratic_basis(12)
    info6=quadratic_basis(6)
    info24=quadratic_basis(24)
    left,right=source[:12],source[12:]
    norm=init_norm(builder,left,right,info24['delta'])

    # Build inverse(norm) lazily. The second output half is not allocated
    # until a three-bit leaf has been erased.
    apply_inplace_linear(builder,norm,info12['to_tower'])
    nleft,nright=norm[:6],norm[6:]
    small_norm=init_norm(builder,nleft,nright,info12['delta'])
    small_inverse=builder.alloc_qubits(6)
    child=init_inverse(builder,small_norm,small_inverse)
    leaf_norm,leaf_inverse=child['norm'],child['inverse_norm']
    first_half=builder.alloc_qubits(6)
    builder.cx(nright,nleft)
    xor_product(builder,nleft,small_inverse,first_half)
    builder.cx(nright,nleft)
    erase_inverse_three(builder,leaf_norm,leaf_inverse)
    builder.free(leaf_inverse)
    second_half=builder.alloc_qubits(6)
    xor_product(builder,nright,small_inverse,second_half)
    inverse_norm=km.array([*first_half,*second_half])
    apply_inplace_linear(builder,norm,info12['from_tower'])
    apply_inplace_linear(builder,inverse_norm,info12['from_tower'])

    # These are norms of the two available inverse words. Erase them
    # directly, retaining only the three-bit deepest norm.
    erase_norm_original_basis(builder,inverse_norm,small_inverse)
    builder.free(small_inverse)
    erase_norm_original_basis(builder,norm,small_norm)
    builder.free(small_norm)

    temporary=builder.alloc_qubits(12)
    for word in (left,right):
        xor_product(builder,word,inverse_norm,temporary)
        builder.swap(word,temporary)
        erase_product(builder,word,norm,temporary)
    builder.free(temporary)
    builder.cx(right,left)

    # Measure the old norm in its quadratic basis and free it BEFORE
    # constructing the small phase-correction scaffold.
    apply_inplace_linear(builder,norm,info12['to_tower'])
    measured=builder.alloc_bits(12)
    builder.hmr(norm,measured)
    builder.free(norm)
    apply_inplace_linear(builder,inverse_norm,info12['to_tower'])
    ileft,iright=inverse_norm[:6],inverse_norm[6:]
    recovered_inverse=init_norm(builder,ileft,iright,info12['delta'])
    recovered_norm=builder.alloc_qubits(6)
    # norm(recovered_inverse)^-1 is precisely the retained three-bit leaf.
    inverse_with_supplied_norm_inverse(builder,recovered_inverse,leaf_norm,recovered_norm)
    builder.cx(iright,ileft)
    phase_product(builder,ileft,recovered_norm,measured[:6],kernel(6))
    builder.cx(iright,ileft)
    phase_product(builder,iright,recovered_norm,measured[6:],kernel(6))
    builder.free(measured)
    inverse_with_supplied_norm_inverse(builder,recovered_inverse,leaf_norm,recovered_norm,erase=True)
    builder.free(recovered_norm)

    # Clean the retained leaf using the norm of its inverse, then erase
    # the last recovered norm and the top inverse norm.
    apply_inplace_linear(builder,recovered_inverse,info6['to_tower'])
    rleft,rright=recovered_inverse[:3],recovered_inverse[3:]
    inverse_leaf=init_norm(builder,rleft,rright,info6['delta'])
    erase_inverse_three(builder,inverse_leaf,leaf_norm)
    builder.free(leaf_norm)
    erase_norm(builder,rleft,rright,inverse_leaf,info6['delta'])
    builder.free(inverse_leaf)
    apply_inplace_linear(builder,recovered_inverse,info6['from_tower'])
    erase_norm(builder,ileft,iright,recovered_inverse,info12['delta'])
    builder.free(recovered_inverse)
    apply_inplace_linear(builder,inverse_norm,info12['from_tower'])
    erase_norm(builder,left,right,inverse_norm,info24['delta'])
    builder.free(inverse_norm)


def build():
    builder=km.CircuitBuilder()
    source=builder.create_quantum_register(24,'value')
    invert_inplace_low_space(builder,source)
    return builder.finish_circuit(),source


def run_checks(destination=None):
    rng=np.random.default_rng(2026110806)
    values=rng.integers(0,1<<24,size=16384,dtype=np.int64)
    values[:4096]=np.arange(4096)
    values[4096:4120]=1<<np.arange(24)
    expected=np.array([extension_inverse(int(x)) for x in values])
    circuit,source=build()
    stream=io.BytesIO()
    circuit.to_file(stream,format='kmb')
    repeated=io.BytesIO()
    build()[0].to_file(repeated,format='kmb')
    assert stream.getvalue()==repeated.getvalue()
    scratch=[km.q(i) for i in range(24,circuit.num_qubits)]
    for seed in range(4):
        sim=km.Simulator(batch_size=len(values),seed=seed)
        sim.use_same_registers_as(circuit)
        sim.write_across_shots(source,bit_matrix(values,24))
        sim.do(circuit)
        assert np.array_equal(sim.read_across_shots(source),bit_matrix(expected,24))
        assert not sim.read_across_shots(scratch).any()
        assert not sim.read_phase_flipped_across_shots().any()
        sim.do(circuit)
        assert np.array_equal(sim.read_across_shots(source),bit_matrix(values,24))
        assert not sim.read_across_shots(scratch).any()
        assert not sim.read_phase_flipped_across_shots().any()
    report=dict(status='PASS_component_only',failures=0,
                T=circuit.operation_statistics().num_toffoli_like,Q=circuit.num_qubits,
                scratch_qubits=circuit.num_qubits-24,shots_per_seed=len(values),seeds=4,
                operations=len(circuit),byte_identical_fresh_builds=True,
                sha256=hashlib.sha256(stream.getvalue()).hexdigest())
    if destination:
        destination.write_text(json.dumps(report,indent=2)+'\n')
        (destination.parent.parent/'circuits'/'inverse-24-low-space.kmb').write_bytes(stream.getvalue())
    return report


if __name__=='__main__':
    print(json.dumps(run_checks(Path(sys.argv[1]) if len(sys.argv)>1 else None),indent=2))
