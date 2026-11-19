# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Return current logical input values to the original registered owners."""
from common import km,array


def restore_input_layout(builder,current,original,cap=49):
    current=list(current);original=list(original)
    assert len(current)==len(original)==22
    assert len(set(current))==len(set(original))==22
    assert builder.num_allocated_qubits==22
    spare=list(builder.alloc_qubits(cap-22));all_wires=set(current+spare)
    assert len(all_wires)==cap and set(original)<=all_wires
    swaps=[]
    for bit,target in enumerate(original):
        source=current[bit]
        if source==target:continue
        builder.swap(source,target);swaps.append((str(source),str(target)))
        for other in range(bit+1,22):
            if current[other]==target:current[other]=source
        current[bit]=target
    assert current==original
    builder.free(array(sorted(all_wires-set(original),key=str)))
    assert builder.num_allocated_qubits==22
    return swaps
