# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Isolated degree32 finite / length-three infinity projective finish.

M is the product of sixteen unused irreducible quadratics. The same exact
Bezout finish K=D*H(M)X+M*H(D)X is implemented in 35 physical target words.
Its final three CRT coordinates are K34,K33,K32, with preserved unit source
D35,D34,D33. No assertion that D0 is a unit is made. In particular the
accepted even-terminal padding factor x is retained and covered.

Source ledger: sixteen462-T quadratic pairs plus one512-T Taylor pair,
7904 static T, 24 helpers. Nested66 changes only the sixteen quadratic
pairs, giving7856. A separate retained-inverse return supports the existing
full35 outer seam without modifying either accepted production module.
Native checks and integration are required before crediting any saving.
"""
from dataclasses import dataclass
from functools import cache

import kickmix as km
from field_tensor import invert_field_matrix
from fused_crt_synthesis import node, residue_powers, field_rows
from monic_forney import add_scaled, flat
from tower_inverse import apply_inplace_linear
import gf24_arithmetic as Arithmetic
import unit_jet_tensor as Jet

F = km.GF2Field(12)


def product(left, right):
    out = [0]*(len(left)+len(right)-1)
    for i, a in enumerate(left):
        for j, b in enumerate(right):
            out[i+j] ^= F.mul(a, b)
    return out


@cache
def geometry():
    M = [1]
    for i in range(35, 51):
        M = product(M, [node(i)[1], 1, 1])
    assert len(M) == 33 and M[-1] == 1
    crt, pre, powers = [], [], []
    for i in range(35, 51):
        pw = residue_powers(i, 36)
        powers.append(pw)
        for coordinate in range(2):
            crt.append([pw[k][coordinate] for k in range(35)])
            row = []
            for j in range(35):
                value = 0
                for k in range(max(0, 32-j)):
                    value ^= F.mul(pw[k][coordinate], M[k+j+1])
                row.append(value)
            pre.append(row)
    # Physical order X32,X33,X34 is reversed relative to Taylor order.
    # The last three precoordinates are Z2,Z1,Z0, where
    # Z_l=sum_{j=0}^{32} M_j X_{j+l}.
    for k, shift in zip(range(32, 35), (2, 1, 0)):
        crt.append([int(j == k) for j in range(35)])
        pre.append([M[j-shift] if shift <= j <= shift+32 else 0 for j in range(35)])
    assert len(pre) == len(crt) == 35
    return dict(M=tuple(M), powers=tuple(powers), pre_matrix=tuple(map(tuple, pre)),
                crt_matrix=tuple(map(tuple, crt)),
                pre_rows=field_rows(pre),
                pre_inverse_rows=field_rows(invert_field_matrix(pre, F)),
                crt_rows=field_rows(crt),
                crt_inverse_rows=field_rows(invert_field_matrix(crt, F)))


def source_view(builder, D, index, inverse=False):
    assert len(D) == 36 and 0 <= index < 16
    t, _ = node(35+index)
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
    infinity_record: object
    source: tuple
    targets: tuple
    closed: bool = False


def emit_prefix(builder, D, X):
    assert len(D) == 36 and len(X) == 35
    assert len(set(flat(D+X))) == 852
    spec = geometry()
    apply_inplace_linear(builder, flat(X), spec['pre_rows'])
    records = []
    for i in range(16):
        source_view(builder, D, i)
        records.append(Arithmetic.emit_prefix(builder, flat(D[:2]), flat(X[2*i:2*i+2])))
        source_view(builder, D, i, True)
    infinity = Jet.emit_prefix(builder, [D[35], D[34], D[33]], [X[34], X[33], X[32]])
    apply_inplace_linear(builder, flat(X), spec['crt_inverse_rows'])
    return Record(id(builder), records, infinity, tuple(flat(D)), tuple(flat(X)))


def emit_closing(builder, D, X, record, *, keep_inverse=False):
    assert record.builder_id == id(builder) and not record.closed
    assert tuple(flat(D)) == record.source and tuple(flat(X)) == record.targets
    spec = geometry()
    apply_inplace_linear(builder, flat(X), spec['crt_rows'])
    # All finite pairs close before the infinity return can retain a
    # reciprocal. Every finite source view restores the complete D bank.
    for i in reversed(range(16)):
        source_view(builder, D, i)
        Arithmetic.emit_closing(builder, flat(D[:2]), flat(X[2*i:2*i+2]), record.quadratic_records[i])
        source_view(builder, D, i, True)
    reciprocal = Jet.emit_closing(builder, [D[35], D[34], D[33]], [X[34], X[33], X[32]],
                                  record.infinity_record, keep_inverse=keep_inverse)
    # No target-dependent debt survives the public mixed-coordinate map.
    apply_inplace_linear(builder, flat(X), spec['pre_inverse_rows'])
    record.closed = True
    return reciprocal


def emit_closing_keep_inverse(builder, D, X, record):
    return emit_closing(builder, D, X, record, keep_inverse=True)


def reference_finish(D, X):
    """Coefficient oracle independent of both CRT matrices and the tensor."""
    M = list(geometry()['M'])

    def hankel(poly):
        out = []
        for i in range(35):
            value = 0
            for j in range(len(poly)-i-1):
                value ^= F.mul(poly[i+j+1], X[j])
            out.append(value)
        return out

    first, second = product(D, hankel(M)), product(M, hankel(D))
    full = [(first[k] if k < len(first) else 0) ^ (second[k] if k < len(second) else 0)
            for k in range(max(len(first), len(second)))]
    assert not any(full[35:])
    return (full+[0]*35)[:35]
