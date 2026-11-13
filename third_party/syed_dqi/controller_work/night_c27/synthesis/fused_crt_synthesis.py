# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Fixed physical polynomial update with a fused r+2-point prefix.

Input N has r coefficients, D has r+1, P has two. The prefix preserves D
and replaces the physical tuple N+P by q_i*N+P*D, degree <=r+1, where
q_i=x^2+x+kappa_i. A public alias supplies the parent N=D. No profile,
terminal, contact list or quantum-controlled coefficient route is used.

The paired return uses r scalar evaluations and one quadratic residue;
the latter divides by D(alpha_i) using the deferred-mask arithmetic API.
Zero source is admitted only with P=0 and only when guarded=True.
"""
from dataclasses import dataclass
from functools import cache
import kickmix as km
from field_tensor import accumulate_product, invert_field_matrix
from tower_inverse import apply_inplace_linear, rows_from_columns
from monic_forney import add_scaled, evaluate_low, flat
import gf24_arithmetic as Arithmetic

F = km.GF2Field(12)
DELTA = 2048


def node(i):
    t = 2*i
    return t, DELTA ^ F.mul(t, t) ^ t


def field_rows(matrix):
    n = len(matrix)
    assert all(len(row) == n for row in matrix)
    columns = [sum(F.mul(matrix[j][k], 1 << bit) << (12*j)
                   for j in range(n)) for k in range(n) for bit in range(12)]
    return rows_from_columns(columns)


def residue_powers(i, count):
    """Coordinates of alpha_i^k in the one common GF24 basis."""
    t, _ = node(i)
    out = [(1, 0)]
    for _ in range(1, count):
        a, b = out[-1]
        out.append((F.mul(t, a) ^ F.mul(DELTA, b), a ^ F.mul(t ^ 1, b)))
    return out


@cache
def prefix_rows(r, i):
    _, kappa = node(i)
    matrix = [[0]*(r+2) for _ in range(r+2)]
    for j in range(r):
        matrix[j][j] = kappa
        matrix[j+1][j] = 1
        matrix[j+2][j] = 1
    matrix[0][r] = matrix[1][r+1] = 1
    return field_rows(matrix)


@cache
def residue_view_rows(r, i, inverse=False):
    n = r+1
    assert n >= 2
    matrix = [[int(j == k) for k in range(n)] for j in range(n)]
    powers = residue_powers(i, n)
    matrix[0] = [p[0] for p in powers]
    matrix[1] = [p[1] for p in powers]
    if inverse:
        matrix = invert_field_matrix(matrix, F)
    return field_rows(matrix)


@cache
def crt_rows(r, i):
    n = r+2
    matrix = [[F.pow(beta, j) for j in range(n)] for beta in range(r)]
    powers = residue_powers(i, n)
    matrix += [[p[0] for p in powers], [p[1] for p in powers]]
    # All public linear factors and q_i are pairwise coprime.
    invert_field_matrix(matrix, F)
    return field_rows(matrix)


@cache
def recover_n_rows(r, i):
    _, kappa = node(i)
    matrix = [[F.mul(F.mul(beta, beta) ^ beta ^ kappa, F.pow(beta, j))
               for j in range(r)] for beta in range(r)]
    return field_rows(invert_field_matrix(matrix, F))


def evaluation_view(builder, words, beta):
    """Involutory view: words[0] becomes evaluation at beta."""
    for j in range(1, len(words)):
        add_scaled(builder, words[j], words[0], F.pow(beta, j))


@dataclass
class Record:
    builder_id: int
    r: int
    node_index: int
    pair_record: object


def emit_prefix(builder, N, D, P, i, *, guarded=False):
    N, D, P = list(N), list(D), list(P)
    r = len(N)
    assert len(D) == r+1 and len(P) == 2 and 1 <= r <= 34
    temporary = builder.alloc_qubits(24)
    T = [temporary[:12], temporary[12:]]
    out = N+T
    apply_inplace_linear(builder, flat(out), prefix_rows(r, i))
    evaluate_low(builder, out)
    for beta, target in enumerate(out):
        evaluation_view(builder, D, beta)
        evaluation_view(builder, P, beta)
        accumulate_product(builder, D[0], P[0], target)
        evaluation_view(builder, P, beta)
        evaluation_view(builder, D, beta)
    evaluate_low(builder, out, True)
    # The arithmetic return's old-target mask is in the common K basis.
    t, _ = node(i)
    add_scaled(builder, P[1], P[0], t)
    builder.swap(flat(P), temporary)
    old_P = builder.alloc_bits(24)
    builder.hmr(temporary, old_P)
    builder.free(temporary)
    pair_record = Arithmetic.make_record(builder, old_P, delta=DELTA, guarded=guarded)
    return Record(id(builder), r, i, pair_record)


def emit_closing(builder, N, D, P, record):
    N, D, P = list(N), list(D), list(P)
    r, i = record.r, record.node_index
    assert id(builder) == record.builder_id
    assert len(N) == r and len(D) == r+1 and len(P) == 2
    apply_inplace_linear(builder, flat(N+P), crt_rows(r, i))
    apply_inplace_linear(builder, flat(D), residue_view_rows(r, i))
    Arithmetic.emit_closing(builder, flat(D[:2]), flat(P), record.pair_record)
    apply_inplace_linear(builder, flat(D), residue_view_rows(r, i, True))
    t, _ = node(i)
    add_scaled(builder, P[1], P[0], t)
    for beta, target in enumerate(N):
        evaluation_view(builder, D, beta)
        evaluation_view(builder, P, beta)
        accumulate_product(builder, D[0], P[0], target)
        evaluation_view(builder, P, beta)
        evaluation_view(builder, D, beta)
    apply_inplace_linear(builder, flat(N), recover_n_rows(r, i))
