# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Public syndrome/CRT geometry for the fixed quadratic-node representation."""
from functools import cache
import kickmix as km
from field_tensor import invert_field_matrix
from tower_inverse import apply_inplace_linear
from monic_forney import flat
from fused_crt_synthesis import node, residue_powers, field_rows
from projective_finish import product

F = km.GF2Field(12)


@cache
def geometry():
    U = [1]
    for i in range(35):
        U = product(U, [node(i)[1], 1, 1])
    assert len(U) == 71 and U[-1] == 1
    matrix = []
    for i in range(35):
        powers = residue_powers(i, 70)
        for c in range(2):
            row = []
            for r in range(1, 71):
                value = 0
                for j in range(71-r):
                    value ^= F.mul(U[j+r], powers[j][c])
                row.append(value)
            matrix.append(row)
    inverse = invert_field_matrix(matrix, F)
    return dict(U=tuple(U), field_matrix=tuple(tuple(row) for row in matrix),
                forward_rows=field_rows(matrix), inverse_rows=field_rows(inverse))


def emit(builder, syndromes, inverse=False):
    assert len(syndromes) == 70 and all(len(w) == 12 for w in syndromes)
    spec = geometry()
    apply_inplace_linear(builder, flat(syndromes),
                         spec['inverse_rows'] if inverse else spec['forward_rows'])


def evaluate(poly, x):
    result = 0
    for value in reversed(poly):
        result = F.mul(result, x) ^ value
    return result


@cache
def syndrome_gauge_plan():
    import mask_gauge135
    # Any 70 distinct nonzero physical points work. The selection is fixed
    # public data and does not depend on a circuit input or sampled failure.
    return mask_gauge135.make_plan(12, tuple(range(1, 71)))
