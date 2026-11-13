"""The full decoder of the 889-qubit architecture, our wiring (QCC-19, E041).

Stages: (0) in-place linear map of the 70 syndrome registers to the 35 residue words (`geometry`), (1)
extract
(`extract`, vendored kernels), (2) synthesis of `(N, D)` (`synth`), (3) scan with a per-position
division (`scan`),
then the mirror: unsynthesis, unextract and the inverse linear map. Registers are exactly `S0 ..` (the
syndromes,
word `i` = registers `2 i` and `2 i + 1`) and `E0 ..` (classical masks).
"""

from __future__ import annotations

import functools
from typing import Any

import kickmix as km  # type: ignore[import-not-found,unused-ignore]

from dqi_gen import extract, scan, synth
from dqi_gen import thiele as T
from dqi_gen.tower import _invert, apply_matrix_inplace


@functools.cache
def geometry_columns() -> tuple[list[int], list[int]]:
    """Columns of the 840 x 840 F2 matrix `S -> Y` (syndrome bits to residue-word bits) and of its
    inverse."""
    gf = T.field()
    cols = []
    for p in range(840):
        r, bit = divmod(p, 12)
        s = [0] * 70
        s[r] = 1 << bit
        res = T.residues(gf, T.residue_polynomial(gf, s))
        v = 0
        for i, (r0, r1) in enumerate(res):
            word = (r0 ^ int(gf.mul(2 * i, r1))) | (r1 << 12)
            v |= word << (24 * i)
        cols.append(v)
    return cols, _invert(cols)


def build_decoder(builder: Any, syndromes: list[Any], masks: list[Any]) -> None:
    """Append the decoder to `builder` (syndromes: 70 registers of 12 qubits; masks: `m` registers of 12
    bits)."""
    flat = [q for reg in syndromes for q in reg]
    fwd, inv = geometry_columns()
    apply_matrix_inplace(builder, flat, fwd)
    words = [list(flat[24 * i : 24 * i + 24]) for i in range(35)]
    carry = list(builder.alloc_qubits(24))
    builder.x(carry[0])
    rec = extract.forward(builder, words, carry)
    flag = rec.tail.current
    n_list, d_list, records, one = synth.forward(builder, words, flag)
    scan.scan(builder, n_list, d_list, masks, list(range(len(masks))))
    synth.backward(builder, flag, words, records, one)
    extract.backward(builder, words, carry, rec)
    builder.x(carry[0])
    builder.free(km.array(carry))
    apply_matrix_inplace(builder, flat, inv)


def build_circuit(m: int, n: int, degree: int) -> Any:
    if (n, degree) != (70, 12):
        raise ValueError("the decoder is built for n = 70 syndromes over GF(2^12)")
    builder = km.CircuitBuilder()
    syndromes = [builder.create_quantum_register(degree, name=f"S{i}") for i in range(n)]
    masks = [builder.create_classical_register(degree, name=f"E{j}") for j in range(m)]
    build_decoder(builder, syndromes, masks)
    return builder.finish_circuit()
