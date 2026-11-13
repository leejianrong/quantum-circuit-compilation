# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""In-place multiplication by a nonzero dual number, with retained norm."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import sys
import kickmix as km
import numpy as np
from quantum_reciprocal import bit_matrix
from tower_inverse import (init_inverse,erase_inverse,init_inverse_three,erase_inverse_three,
                           xor_product,erase_product)
FIELD=km.GF2Field(12)


def scale_word(builder,word,multiplier,inverse_multiplier,temporary):
    xor_product(builder,word,multiplier,temporary)
    builder.swap(word,temporary)
    erase_product(builder,word,inverse_multiplier,temporary)


def emit(builder,a,b,c,d,reverse=False,trim=False):
    inverse=builder.alloc_qubits(12)
    scaffold=init_inverse(builder,c,inverse)
    leaf=scaffold['child']
    if trim:
        erase_inverse_three(builder,leaf['norm'],leaf['inverse_norm'])
        builder.free(leaf['inverse_norm']);leaf['inverse_norm']=None
    temporary=builder.alloc_qubits(12)
    if reverse:
        scale_word(builder,a,inverse,c,temporary)
        xor_product(builder,a,d,b)
        scale_word(builder,b,inverse,c,temporary)
    else:
        scale_word(builder,b,c,inverse,temporary)
        xor_product(builder,a,d,b)
        scale_word(builder,a,c,inverse,temporary)
    builder.free(temporary)
    if trim:
        leaf['inverse_norm']=builder.alloc_qubits(3)
        init_inverse_three(builder,leaf['norm'],leaf['inverse_norm'])
    erase_inverse(builder,c,inverse,scaffold)
    builder.free(inverse)


def build(reverse=False,trim=False):
    builder=km.CircuitBuilder()
    words=[builder.create_quantum_register(12,name) for name in ('a','b','c','d')]
    emit(builder,*words,reverse=reverse,trim=trim)
    return builder.finish_circuit(),words


def serialized(circuit):
    stream=io.BytesIO();circuit.to_file(stream,format='kmb');return stream.getvalue()


def run_checks(destination=None):
    rng=np.random.default_rng(2026110815)
    data=rng.integers(0,4096,size=(8192,4),dtype=np.int64)
    data[:,2]=rng.integers(1,4096,size=len(data),dtype=np.int64)
    data[:4095,2]=np.arange(1,4096)
    data[4095:4120,:2]=0
    expected=data.copy()
    for i,(a,b,c,d) in enumerate(data):
        expected[i,0]=FIELD.mul(int(a),int(c))
        expected[i,1]=FIELD.mul(int(b),int(c))^FIELD.mul(int(a),int(d))
    report=dict(status='PASS_nonzero_dual_scale_component_only',failures=0)
    for trim in (False,True):
        forward,words=build(trim=trim);reverse,_=build(reverse=True,trim=trim)
        payload=serialized(forward);back=serialized(reverse)
        assert payload==serialized(build(trim=trim)[0])
        assert back==serialized(build(reverse=True,trim=trim)[0])
        scratch=[km.q(i) for i in range(48,forward.num_qubits)]
        assert reverse.num_qubits==forward.num_qubits
        for seed in range(4):
            sim=km.Simulator(batch_size=len(data),seed=seed);sim.use_same_registers_as(forward)
            for j,word in enumerate(words):sim.write_across_shots(word,bit_matrix(data[:,j],12))
            sim.do(forward)
            for j,word in enumerate(words):assert np.array_equal(sim.read_across_shots(word),bit_matrix(expected[:,j],12))
            assert not sim.read_across_shots(scratch).any()
            assert not sim.read_phase_flipped_across_shots().any()
            sim.do(reverse)
            for j,word in enumerate(words):assert np.array_equal(sim.read_across_shots(word),bit_matrix(data[:,j],12))
            assert not sim.read_across_shots(scratch).any()
            assert not sim.read_phase_flipped_across_shots().any()
        label='trimmed' if trim else 'fast'
        report[label]=dict(T_forward=forward.operation_statistics().num_toffoli_like,
                           T_reverse=reverse.operation_statistics().num_toffoli_like,
                           Q=forward.num_qubits,scratch_qubits=forward.num_qubits-48,
                           shots_per_seed=len(data),seeds=4,byte_identical_fresh_builds=True,
                           sha256_forward=hashlib.sha256(payload).hexdigest(),sha256_reverse=hashlib.sha256(back).hexdigest())
        if destination:
            (destination.parent.parent/'circuits'/f'dual-scale-{label}-forward.kmb').write_bytes(payload)
            (destination.parent.parent/'circuits'/f'dual-scale-{label}-reverse.kmb').write_bytes(back)
    if destination:destination.write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    print(json.dumps(run_checks(Path(sys.argv[1]) if len(sys.argv)>1 else None),indent=2))
