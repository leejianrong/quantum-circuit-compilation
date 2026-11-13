# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Fixed degree-34/infinity finish for 35-word full Bezout preimages.

Input: explicit degree35 squarefree D, independent X35, unit leading D35,
and gcd(D,M)=1 for M=product(q_i, i=35,...,51). Prefix returns the polynomial
K=D*H(M)X + M*H(D)X, degree<=34. At a D-root a, K(a)=M(a)*H(D)X(a).
It preserves D and pairs with a phase-exact restoring return.

The 35th projective coordinate is the leading output coefficient, and its
input coordinate is dot(M_coefficients,X). This uses no finite sentinel,
contact identity, quantum count or extra field word.
"""
from dataclasses import dataclass
from functools import cache
import kickmix as km
from monic_forney import add_scaled, flat
from tower_inverse import apply_inplace_linear
from field_tensor import invert_field_matrix
import gf24_arithmetic as Arithmetic
import fixed_modular_finish as Prior
from fused_crt_synthesis import node, residue_powers, field_rows

F = km.GF2Field(12)


def product(a, b):
    out = [0]*(len(a)+len(b)-1)
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            out[i+j] ^= F.mul(x, y)
    return out


@cache
def geometry():
    M = [1]
    for i in range(35, 52):
        M = product(M, [node(i)[1], 1, 1])
    assert len(M) == 35 and M[-1] == 1
    crt, pre, powers = [], [], []
    for i in range(35, 52):
        pw = residue_powers(i, 36)
        powers.append(pw)
        for c in range(2):
            crt.append([pw[k][c] for k in range(35)])
            row = []
            for j in range(35):
                value = 0
                for k in range(34-j):
                    value ^= F.mul(pw[k][c], M[k+j+1])
                row.append(value)
            pre.append(row)
    crt.append([0]*34+[1])
    pre.append(M[:])
    return dict(M=tuple(M), powers=tuple(powers), crt_rows=field_rows(crt),
                crt_inverse_rows=field_rows(invert_field_matrix(crt, F)),
                pre_rows=field_rows(pre),
                pre_inverse_rows=field_rows(invert_field_matrix(pre, F)))


def source_view(builder, D, index, inverse=False):
    i = 35+index
    t, _ = node(i)
    powers = geometry()['powers'][index]
    if not inverse:
        add_scaled(builder, D[1], D[0], t)
    for k in reversed(range(2, 36)) if inverse else range(2, 36):
        add_scaled(builder, D[k], D[0], powers[k][0])
        add_scaled(builder, D[k], D[1], powers[k][1])
    if inverse:
        add_scaled(builder, D[1], D[0], t)


@dataclass
class Record:
    builder_id: int
    quadratic_records: list
    scalar_record: object


def emit_prefix(builder, D, X):
    assert len(D) == 36 and len(X) == 35
    spec = geometry()
    apply_inplace_linear(builder, flat(X), spec['pre_rows'])
    records = []
    for i in range(17):
        source_view(builder, D, i)
        records.append(Arithmetic.emit_prefix(builder, flat(D[:2]), flat(X[2*i:2*i+2])))
        source_view(builder, D, i, True)
    scalar = Prior.scalar_prefix(builder, D[35], X[34])
    apply_inplace_linear(builder, flat(X), spec['crt_inverse_rows'])
    return Record(id(builder), records, scalar)


def emit_closing(builder, D, X, record):
    assert id(builder) == record.builder_id
    spec = geometry()
    apply_inplace_linear(builder, flat(X), spec['crt_rows'])
    Prior.scalar_closing(builder, D[35], X[34], record.scalar_record)
    for i in reversed(range(17)):
        source_view(builder, D, i)
        Arithmetic.emit_closing(builder, flat(D[:2]), flat(X[2*i:2*i+2]), record.quadratic_records[i])
        source_view(builder, D, i, True)
    apply_inplace_linear(builder, flat(X), spec['pre_inverse_rows'])
