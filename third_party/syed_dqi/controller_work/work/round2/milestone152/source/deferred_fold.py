# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""Forward polynomial fold with phase repayment after its paired inverse.

Do not use this as a phase-clean standalone forward transformation.
The returned classical mask must be applied to restored P after inverse folding.
"""
import kickmix as km
from normal_fold import add_linear_product,emit_reverse,FIELD
from quantum_reciprocal import xor_linear

def flat(words):return km.array([wire for word in words for wire in word])

def emit_forward(builder,P,N,D,node):
    temporary=builder.alloc_qubits(24)
    low=[temporary[:12],temporary[12:]]
    Y=low+list(N)
    constant=FIELD.mul(node,node)
    columns=tuple(FIELD.mul(constant,1<<bit) for bit in range(12))
    # Y initially equals z²*N. Ascending targets preserve all needed old sources.
    for i in range(len(N)):xor_linear(builder,Y[i+2],Y[i],columns)
    add_linear_product(builder,P,D,Y)
    measured=builder.alloc_bits(24)
    builder.hmr(flat(P),measured)
    for destination,source in zip(P,low):builder.swap(destination,source)
    builder.free(temporary)
    return measured

def emit_paired_reverse(builder,P,N,D,node,measured,repay=True):
    emit_reverse(builder,P,N,D,node)
    if repay:builder.cz(measured,flat(P))
    builder.free(measured)
