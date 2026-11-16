# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""20-T, ten-helper phase Tr(numerator * inv0(denominator)) over GF64.

Use the existing eleven-T cubic scaffold and contract each of its nine
reassembly outputs directly with the quantum numerator. The inverse output
is never allocated. The resulting three-quantum parity phase costs one T
per reassembly term. Every scaffold debt is paid before returning.
"""
from functools import cache
import kickmix as km
import cubic_inverse130 as Cubic
from field_tensor import parity_pivot

STATIC_T = 20
HELPERS = 10


@cache
def contracted_terms():
    field = km.GF2Field(6)
    assert field.modulus == 0x43
    def trace(value):
        answer = 0
        for _ in range(6):
            answer ^= value
            value = field.mul(value, value)
        assert answer in (0,1)
        return answer
    terms = tuple((left, right,
                   sum(trace(field.mul(output,1 << bit)) << bit for bit in range(6)))
                  for left,right,output in Cubic.cubic_data()['reassembly'])
    assert len(terms) == 9 and all(a and b and c for a,b,c in terms)
    return terms


def phase_trace_quotient_six(builder, denominator, numerator):
    """Preserve two disjoint polynomial-basis words, including denominator0."""
    if len(denominator) != 6 or len(numerator) != 6:
        raise ValueError('two six-bit words are required')
    wires = [*denominator,*numerator]
    if not all(isinstance(q,km.q) for q in wires):
        raise TypeError('both source words must be quantum')
    if len(set(wires)) != 12:
        raise ValueError('two disjoint quantum words are required')
    before = builder.num_allocated_qubits
    scaffold = Cubic.init_cubic_scaffold(builder,denominator)
    signals = km.array([*denominator,*scaffold['quadratics']])
    norm = scaffold['norm']
    for left,right,trace_row in contracted_terms():
        first = parity_pivot(builder,signals,left)
        second = parity_pivot(builder,norm,right)
        third = parity_pivot(builder,numerator,trace_row)
        builder.ccz(first,second,third)
        parity_pivot(builder,numerator,trace_row)
        parity_pivot(builder,norm,right)
        parity_pivot(builder,signals,left)
    Cubic.erase_cubic_scaffold(builder,denominator,scaffold)
    assert builder.num_allocated_qubits == before
