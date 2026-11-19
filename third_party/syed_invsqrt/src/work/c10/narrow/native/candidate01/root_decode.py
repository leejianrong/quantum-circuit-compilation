# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Restore five retired raw root coordinates from the frozen21-AND code."""
from common import *
from thermometer_cleanup import linear_frame

CERT=checked_json(NARROW/'research/quantized_producer/framed_retained5_best21_snapshot.json',
    '3b6fa7059bee77bb9abe6c7395cd8ff2f2899843523188c60d513e6c5d381def')


def decode_root(builder,v,A,H,retired_outcomes):
    """v12 has None at5,6,7,9,11; v8=R andv10=rawa5 remain.

    Return current v owners, with its R frame STILL active. The caller owns
    the final one-CCX R unframe in the separately counted4E lifecycle.
    retired_outcomes maps raw address indices0,1,2,4,6 to their HMR bits.
    """
    v=list(v);A=list(A);H=list(H);missing=(0,1,2,4,6)
    assert len(v)==12 and len(A)==13 and len(H)==5
    assert all(v[5+i] is None for i in missing)
    assert set(retired_outcomes)==set(missing)
    features=[v[8]]+A+H+[v[10]];outputs=[]
    for record in CERT['plans']:
        p=plan_from_json(record['plan']);assert p.width==len(features)
        q=builder.alloc_qubits(1)[0];cb.emit_xor(builder,features,q,p)
        outputs.append(q);features.append(q)
    rows=[CERT['raw_five_from_code'][str(i)]for i in missing]
    for kind,i,j in linear_frame(rows):
        if kind=='cx':builder.cx(outputs[i],outputs[j])
        else:builder.swap(outputs[i],outputs[j])
    for i,q in zip(missing,outputs):
        v[5+i]=q;m=retired_outcomes[i]
        builder.push_condition(m);builder.z(q);builder.pop_condition();builder.free(m)
    return v
