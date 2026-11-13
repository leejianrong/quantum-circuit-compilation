# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""Normalize a locator/numerator pair, retaining the nonzero leading scalar."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import sys
import kickmix as km
import numpy as np
from compact_inverse import compact_inverse_twelve,phase_inverse_twelve
from tower_inverse import apply_inplace_linear,quadratic_basis
from dual_scale import scale_word,FIELD
from quantum_reciprocal import bit_matrix
from projective_carry import erase_inverse_word,repay_inverse_mask


def emit(builder,words,leading,reverse=False,defer=False,deferred_mask=None):
    inverse=compact_inverse_twelve(builder,leading)
    if deferred_mask is not None:repay_inverse_mask(builder,inverse,deferred_mask)
    temporary=builder.alloc_qubits(12)
    for word in words:
        if reverse:scale_word(builder,word,leading,inverse,temporary)
        else:scale_word(builder,word,inverse,leading,temporary)
    builder.free(temporary)
    return erase_inverse_word(builder,leading,inverse,defer)


def build(degree):
    builder=km.CircuitBuilder()
    locator=[builder.create_quantum_register(12,f'D{i}') for i in range(degree)]
    numerator=[builder.create_quantum_register(12,f'Omega{i}') for i in range(degree)]
    leading=builder.create_quantum_register(12,'retained_leading_scalar')
    probe=builder.create_classical_register(24*degree,'normalized_phase_probe')
    words=locator+numerator
    emit(builder,words,leading)
    builder.cz(probe,km.array([wire for word in words for wire in word]))
    emit(builder,words,leading,reverse=True)
    return builder.finish_circuit(),words,leading,probe


def run_checks(destination=None):
    rng=np.random.default_rng(2026110821)
    report=dict(status='PASS_fixed_degree_normalization_adapter_only',failures=0,cases=[])
    for degree in (1,3,7):
        shots=8192
        leading=rng.integers(1,4096,size=shots,dtype=np.int64)
        leading[:4095]=np.arange(1,4096)
        values=rng.integers(0,4096,size=(shots,2*degree),dtype=np.int64)
        masks=rng.integers(0,4096,size=(shots,2*degree),dtype=np.int64)
        expected=[]
        for row,kappa in zip(values,leading):
            inverse=FIELD.invert(int(kappa))
            expected.append([FIELD.mul(int(v),inverse) for v in row])
        phases=np.array([sum((v&int(m)).bit_count() for v,m in zip(row,mask))&1
                         for row,mask in zip(expected,masks)],dtype=bool)
        circuit,words,scalar,probe=build(degree)
        payload,repeated=io.BytesIO(),io.BytesIO()
        circuit.to_file(payload,format='kmb');build(degree)[0].to_file(repeated,format='kmb')
        assert payload.getvalue()==repeated.getvalue()
        input_qubits=12*(2*degree+1)
        scratch=[km.q(i) for i in range(input_qubits,circuit.num_qubits)]
        for seed in range(4):
            sim=km.Simulator(batch_size=shots,seed=seed);sim.use_same_registers_as(circuit)
            sim.write_across_shots(scalar,bit_matrix(leading,12))
            for j,word in enumerate(words):
                sim.write_across_shots(word,bit_matrix(values[:,j],12))
                sim.write_across_shots(probe[12*j:12*(j+1)],bit_matrix(masks[:,j],12))
            sim.do(circuit)
            assert np.array_equal(sim.read_across_shots(scalar),bit_matrix(leading,12))
            for j,word in enumerate(words):assert np.array_equal(sim.read_across_shots(word),bit_matrix(values[:,j],12))
            assert not sim.read_across_shots(scratch).any()
            assert np.array_equal(sim.read_phase_flipped_across_shots(),phases)
        report['cases'].append(dict(degree=degree,T=circuit.operation_statistics().num_toffoli_like,
                                    Q=circuit.num_qubits,scratch_qubits=circuit.num_qubits-input_qubits,
                                    retained_scalar_qubits=12,shots_per_seed=shots,seeds=4,
                                    byte_identical_fresh_builds=True,sha256=hashlib.sha256(payload.getvalue()).hexdigest()))
        if destination:(destination.parent.parent/'circuits'/f'normalize-d{degree}.kmb').write_bytes(payload.getvalue())
    report['degree35_model']=dict(T_per_direction=3042,T_roundtrip=6084,
                                  Q_including_retained_scalar=876,Q_with_parity_bit=877,
                                  status='extrapolation; degree routing, padding and residue layout excluded')
    if destination:destination.write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    print(json.dumps(run_checks(Path(sys.argv[1]) if len(sys.argv)>1 else None),indent=2))
