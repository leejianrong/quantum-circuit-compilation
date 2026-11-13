# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""A 228-T, 36-scratch-qubit extension inverse; optional zero flag costs 2 T."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import kickmix as km
import numpy as np

from quantum_reciprocal import bit_matrix
from tower_inverse import (quadratic_basis, apply_inplace_linear, init_norm, erase_norm,
                           init_inverse, erase_inverse, erase_inverse_three,
                           xor_product, erase_product, phase_product, kernel,
                           extension_inverse)
from low_space_inverse import erase_norm_original_basis
from cubic_inverse130 import compact_inverse_twelve,phase_inverse_twelve_35


def toggle_zero_three(builder, value, target):
    builder.x(value)
    temporary=builder.alloc_qubits(1)
    builder.init_and(value[0],value[1],temporary[0])
    builder.ccx(temporary[0],value[2],target)
    builder.del_and(value[0],value[1],temporary[0])
    builder.free(temporary)
    builder.x(value)


def legacy_compact_inverse_twelve(builder, source, zero_flag=None):
    """Return an allocated inverse word; all internal scaffolds are erased."""
    info12,info6=quadratic_basis(12),quadratic_basis(6)
    apply_inplace_linear(builder,source,info12['to_tower'])
    left,right=source[:6],source[6:]
    norm=init_norm(builder,left,right,info12['delta'])
    inverse_norm=builder.alloc_qubits(6)
    child=init_inverse(builder,norm,inverse_norm)
    if zero_flag is not None:
        # Successive irreducible quadratic norms vanish exactly at zero.
        toggle_zero_three(builder,child['norm'],zero_flag)
    erase_inverse_three(builder,child['norm'],child['inverse_norm'])
    builder.free(child['inverse_norm'])
    erase_norm_original_basis(builder,norm,child['norm'])
    builder.free(child['norm'])
    target=builder.alloc_qubits(12)
    builder.cx(right,left)
    xor_product(builder,left,inverse_norm,target[:6])
    builder.cx(right,left)
    xor_product(builder,right,inverse_norm,target[6:])
    apply_inplace_linear(builder,target,info12['from_tower'])
    erase_norm_original_basis(builder,target,inverse_norm)
    builder.free(inverse_norm)
    erase_norm(builder,left,right,norm,info12['delta'])
    builder.free(norm)
    apply_inplace_linear(builder,source,info12['from_tower'])
    return target


def legacy_phase_inverse_twelve(builder, source, mask_in_tower_basis):
    """Phase by a classical linear functional of inverse(source), at 36 T."""
    info=quadratic_basis(12)
    apply_inplace_linear(builder,source,info['to_tower'])
    left,right=source[:6],source[6:]
    norm=init_norm(builder,left,right,info['delta'])
    inverse_norm=builder.alloc_qubits(6)
    scaffold=init_inverse(builder,norm,inverse_norm)
    builder.cx(right,left)
    phase_product(builder,left,inverse_norm,mask_in_tower_basis[:6],kernel(6))
    builder.cx(right,left)
    phase_product(builder,right,inverse_norm,mask_in_tower_basis[6:],kernel(6))
    erase_inverse(builder,norm,inverse_norm,scaffold)
    builder.free(inverse_norm)
    erase_norm(builder,left,right,norm,info['delta'])
    builder.free(norm)
    apply_inplace_linear(builder,source,info['from_tower'])


def phase_inverse_twelve(builder,source,mask_in_tower_basis):
    from inverse_phase27 import phase_inverse_twelve as phase27
    return phase27(builder,source,mask_in_tower_basis)


def invert_compact(builder, source, zero_flag=None):
    assert len(source)==24
    info24,info12=quadratic_basis(24),quadratic_basis(12)
    left,right=source[:12],source[12:]
    norm=init_norm(builder,left,right,info24['delta'])
    inverse_norm=compact_inverse_twelve(builder,norm,zero_flag)
    temporary=builder.alloc_qubits(12)
    for word in (left,right):
        xor_product(builder,word,inverse_norm,temporary)
        builder.swap(word,temporary)
        erase_product(builder,word,norm,temporary)
    builder.free(temporary)
    builder.cx(right,left)
    apply_inplace_linear(builder,norm,info12['to_tower'])
    measured=builder.alloc_bits(12)
    builder.hmr(norm,measured)
    builder.free(norm)
    phase_inverse_twelve(builder,inverse_norm,measured)
    builder.free(measured)
    erase_norm(builder,left,right,inverse_norm,info24['delta'])
    builder.free(inverse_norm)


def build(flag=False):
    builder=km.CircuitBuilder()
    source=builder.create_quantum_register(24,'value')
    register=builder.create_quantum_register(1,'zero_flag') if flag else None
    invert_compact(builder,source,register[0] if flag else None)
    return builder.finish_circuit(),source,register


def run_checks(destination=None):
    rng=np.random.default_rng(2026110807)
    values=rng.integers(0,1<<24,size=16384,dtype=np.int64)
    values[:4096]=np.arange(4096)
    values[4096:4120]=1<<np.arange(24)
    expected=np.array([extension_inverse(int(x)) for x in values])
    flags=rng.integers(0,2,size=len(values),dtype=np.int64)
    report=dict(status='PASS_component_only',failures=0)
    for flag in (False,True):
        circuit,source,register=build(flag)
        stream=io.BytesIO()
        circuit.to_file(stream,format='kmb')
        repeat=io.BytesIO()
        build(flag)[0].to_file(repeat,format='kmb')
        assert stream.getvalue()==repeat.getvalue()
        scratch=[km.q(i) for i in range(24+int(flag),circuit.num_qubits)]
        for seed in range(4):
            sim=km.Simulator(batch_size=len(values),seed=seed)
            sim.use_same_registers_as(circuit)
            sim.write_across_shots(source,bit_matrix(values,24))
            if flag:
                sim.write_across_shots(register,bit_matrix(flags,1))
            sim.do(circuit)
            assert np.array_equal(sim.read_across_shots(source),bit_matrix(expected,24))
            if flag:
                assert np.array_equal(sim.read_across_shots(register),bit_matrix(flags^(values==0),1))
            assert not sim.read_across_shots(scratch).any()
            assert not sim.read_phase_flipped_across_shots().any()
            sim.do(circuit)
            assert np.array_equal(sim.read_across_shots(source),bit_matrix(values,24))
            if flag:
                assert np.array_equal(sim.read_across_shots(register),bit_matrix(flags,1))
            assert not sim.read_across_shots(scratch).any()
            assert not sim.read_phase_flipped_across_shots().any()
        entry=dict(T=circuit.operation_statistics().num_toffoli_like,Q=circuit.num_qubits,
                   scratch_qubits=circuit.num_qubits-24-int(flag),shots_per_seed=len(values),seeds=4,
                   operations=len(circuit),byte_identical_fresh_builds=True,
                   sha256=hashlib.sha256(stream.getvalue()).hexdigest())
        report['zero_flag' if flag else 'plain']=entry
        if destination:
            (destination.parent.parent/'circuits'/f'inverse-24-compact-{flag}.kmb').write_bytes(stream.getvalue())
    if destination:
        destination.write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    print(json.dumps(run_checks(Path(sys.argv[1]) if len(sys.argv)>1 else None),indent=2))
