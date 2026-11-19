# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Restore five root values; only a6 retains a direct HMR phase outcome."""
from common import km, cb, NARROW, checked_json, plan_from_json
from tables06 import _BASE

CERT=checked_json(NARROW/'research/quantized_producer/framed_retained5_best21_snapshot.json',
    '3b6fa7059bee77bb9abe6c7395cd8ff2f2899843523188c60d513e6c5d381def')
MISSING=(0,1,2,4,6)
EARLY_TABLE_DEBT=(0,1,2,4)
RESOURCES=dict(Toffolis=21,T=0,R=0,new_value_owners=5,complete_peak=44,
               deferred_table_phase_indices=list(EARLY_TABLE_DEBT),direct_phase_indices=[6])


def decode_root(builder,v,A,H,retired_outcomes):
    """Return v with all five values restored and its R frame still active.

    Keys0,1,2,4 MUST map to None: their exact mixed signs are owned by the
    table ledger, not by a direct raw-bit outcome. Key6 MUST be the actual
    late HMR bit. This function creates no placeholder classical bits.
    """
    v=list(v);A=list(A);H=list(H)
    assert len(v)==12 and len(A)==13 and len(H)==5
    assert all(v[5+i]is None for i in MISSING)
    assert set(retired_outcomes)==set(MISSING)
    assert all(retired_outcomes[i]is None for i in EARLY_TABLE_DEBT)
    assert isinstance(retired_outcomes[6],km.b)
    assert isinstance(v[8],km.q)and isinstance(v[10],km.q)
    features=[v[8]]+A+H+[v[10]];outputs=[];count=0
    for record in CERT['plans']:
        plan=plan_from_json(record['plan']);assert plan.width==len(features)
        q=builder.alloc_qubits(1)[0];cb.emit_xor(builder,features,q,plan)
        outputs.append(q);features.append(q);count+=plan.and_count
    assert count==21 and len(outputs)==5
    rows=[CERT['raw_five_from_code'][str(i)]for i in MISSING]
    for kind,i,j in _BASE._row_matrix_inverse_operations(rows,len(outputs)):
        if kind=='cx':builder.cx(outputs[i],outputs[j])
        else:builder.swap(outputs[i],outputs[j])
    for i,q in zip(MISSING,outputs):
        v[5+i]=q
        outcome=retired_outcomes[i]
        if outcome is not None:
            assert i==6
            builder.push_condition(outcome);builder.z(q);builder.pop_condition();builder.free(outcome)
    return v
