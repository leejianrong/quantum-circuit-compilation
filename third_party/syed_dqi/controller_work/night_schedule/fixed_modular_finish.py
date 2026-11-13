# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""One fixed35-word modular finish, seventeen quadratic factors plus x+1.

Physical contract:36 true polynomial D coefficients (all coefficients above
its degree are actual zeros),35 arbitrary input U words, D split overGF4096
and D(1)!=0. No contact count or compiler profile is supplied to this emitter.
High coefficient metadata is NOT accepted by this version.

The fixed public M has degree35. Prefix returns V=D*J(T(reverseM)U) modM.
For U=[z,arbitrary history], at a root alpha ofD, V(alpha)=M(alpha)*R(alpha),
where R=reverse_d(T_d(reverseD)z). All source coefficients remain unchanged.
Closing restores every U value and pays all measurement phases.
"""
from dataclasses import dataclass
from functools import cache
from pathlib import Path
import sys
import kickmix as km
sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'night_root'))
import extension24_tensor as Tensor
import modular_quadratic_direct as Quad
from monic_forney import add_scaled, flat
from field_tensor import invert_field_matrix
from tower_inverse import apply_inplace_linear, rows_from_columns, xor_product, phase_product, kernel
from compact_inverse import compact_inverse_twelve
from projective_carry import erase_inverse_word

F = km.GF2Field(12)
SIZE = 35


def poly_product(a, b):
    out = [0]*(len(a)+len(b)-1)
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            out[i+j] ^= F.mul(x, y)
    return out


def matrix_product(a, b):
    n = len(a)
    out = [[0]*n for _ in range(n)]
    for i in range(n):
        for k, value in enumerate(a[i]):
            if not value:
                continue
            for j in range(n):
                out[i][j] ^= F.mul(value, b[k][j])
    return out


def binary_rows(matrix):
    n = len(matrix)
    columns = tuple(sum(F.mul(matrix[i][j], 1 << bit) << (12*i) for i in range(n))
                    for j in range(n) for bit in range(12))
    return rows_from_columns(columns)


@cache
def geometry():
    chosen, seen = [], set()
    for kappa in range(4096):
        delta = Tensor.DELTA ^ F.mul(kappa, kappa) ^ kappa
        if delta not in seen:
            chosen.append((kappa, delta))
            seen.add(delta)
        if len(chosen) == 17:
            break
    M = [1, 1]
    powers = []
    crt = []
    for kappa, delta in chosen:
        M = poly_product(M, [delta, 1, 1])
        root = kappa | (1 << 12)
        row = [1]
        for _ in range(35):
            row.append(Tensor.mul(row[-1], root))
        powers.append(tuple(row))
        crt += [[v & 4095 for v in row[:35]], [v >> 12 for v in row[:35]]]
    crt.append([1]*35)
    assert len(M) == 36 and M[-1] == 1 and len(crt) == 35
    t = [[M[35-i+j] if j <= i else 0 for j in range(35)] for i in range(35)]
    pre = matrix_product(crt, list(reversed(t)))
    crt_inverse = invert_field_matrix(crt, F)
    pre_inverse = invert_field_matrix(pre, F)
    return dict(M=tuple(M), quadratic_factors=tuple(chosen), source_powers=tuple(powers),
                pre_rows=binary_rows(pre), pre_inverse_rows=binary_rows(pre_inverse),
                crt_rows=binary_rows(crt), crt_inverse_rows=binary_rows(crt_inverse),
                tensor=Tensor.multiplication_tensor())


def quadratic_source_view(builder, D, index, inverse=False):
    """Fixed invertible shear: D0,D1 become remainder coordinates at tau+kappa."""
    spec = geometry()
    kappa, _ = spec['quadratic_factors'][index]
    powers = spec['source_powers'][index]
    if not inverse:
        add_scaled(builder, D[1], D[0], kappa)
    for k in reversed(range(2, 36)) if inverse else range(2, 36):
        add_scaled(builder, D[k], D[0], powers[k] & 4095)
        add_scaled(builder, D[k], D[1], powers[k] >> 12)
    if inverse:
        add_scaled(builder, D[1], D[0], kappa)


def linear_source_view(builder, D):
    for word in D[1:]:
        builder.cx(word, D[0])


def scalar_prefix(builder, source, value):
    temporary = builder.alloc_qubits(12)
    xor_product(builder, source, value, temporary)
    builder.swap(value, temporary)
    mask = builder.alloc_bits(12)
    builder.hmr(temporary, mask)
    builder.free(temporary)
    return mask


def scalar_closing(builder, source, value, old_value_mask):
    reciprocal = compact_inverse_twelve(builder, source)
    temporary = builder.alloc_qubits(12)
    xor_product(builder, reciprocal, value, temporary)
    builder.swap(value, temporary)
    old_product_mask = builder.alloc_bits(12)
    builder.hmr(temporary, old_product_mask)
    builder.free(temporary)
    erase_inverse_word(builder, source, reciprocal)
    builder.cz(old_value_mask, value)
    builder.free(old_value_mask)
    phase_product(builder, source, value, old_product_mask, kernel(12))
    builder.free(old_product_mask)


@dataclass
class Record:
    builder_id: int
    quadratics: list
    linear: object


def emit_prefix(builder, D, U):
    assert len(D) == 36 and len(U) == 35
    assert len(set(q for word in list(D)+list(U) for q in word)) == 852
    spec = geometry()
    apply_inplace_linear(builder, flat(U), spec['pre_rows'])
    records = []
    for i in range(17):
        quadratic_source_view(builder, D, i)
        records.append(Quad.emit_prefix(builder, flat(D[:2]), flat(U[2*i:2*i+2]),
                                        Tensor.DELTA, tensor=spec['tensor']))
        quadratic_source_view(builder, D, i, True)
    linear_source_view(builder, D)
    linear = scalar_prefix(builder, D[0], U[34])
    linear_source_view(builder, D)
    apply_inplace_linear(builder, flat(U), spec['crt_inverse_rows'])
    return Record(id(builder), records, linear)


def emit_closing(builder, D, U, record):
    assert record.builder_id == id(builder)
    spec = geometry()
    apply_inplace_linear(builder, flat(U), spec['crt_rows'])
    linear_source_view(builder, D)
    scalar_closing(builder, D[0], U[34], record.linear)
    linear_source_view(builder, D)
    for i in reversed(range(17)):
        quadratic_source_view(builder, D, i)
        Quad.emit_closing(builder, flat(D[:2]), flat(U[2*i:2*i+2]), record.quadratics[i])
        quadratic_source_view(builder, D, i, True)
    apply_inplace_linear(builder, flat(U), spec['pre_inverse_rows'])
