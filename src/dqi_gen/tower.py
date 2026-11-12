"""GF(2^2h) as a degree-2 tower over GF(2^h), for cheap division at the Forney step (our own derivation).

An element `a = A + B y` with `A, B` in the subfield and `y^2 = y + b` (we pick `y` with relative trace 1, so
`y + y^64 = 1`). Then `conj(a) = (A + B) + B y` is a linear map, the norm `N = A^2 + A B + b B^2` lies in
GF(2^6), and `1/a = conj(a) / N`. One inversion in GF(2^12) therefore costs one GF(2^6) product (the norm),
one GF(2^6) inversion and the GF(2^6) products of the final multiplication, instead of an Itoh-Tsujii chain
of GF(2^12) products. Changing basis between the host's polynomial basis and `(A, B)` coordinates is a fixed
invertible F2-matrix, applied in place by CNOTs (no Toffolis).

Matrices are lists of column integers: column `i` is the image of basis vector `i`, bit `j` of the integer
is row `j`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


def _apply(cols: Sequence[int], x: int) -> int:
    out = 0
    for i, c in enumerate(cols):
        if x >> i & 1:
            out ^= c
    return out


def _invert(cols: Sequence[int]) -> list[int]:
    """Inverse of an invertible F2 matrix given by columns (Gauss-Jordan on augmented rows)."""
    n = len(cols)
    rows = [sum(((cols[c] >> r) & 1) << c for c in range(n)) | (1 << (n + r)) for r in range(n)]
    for col in range(n):
        piv = next(r for r in range(col, n) if rows[r] >> col & 1)
        rows[col], rows[piv] = rows[piv], rows[col]
        for r in range(n):
            if r != col and rows[r] >> col & 1:
                rows[r] ^= rows[col]
    inv_rows = [rows[r] >> n for r in range(n)]  # row r of the inverse, bit c = entry (r, c)
    return [sum(((inv_rows[r] >> c) & 1) << r for r in range(n)) for c in range(n)]


def apply_matrix_inplace(builder: Any, qubits: Sequence[Any], cols: Sequence[int]) -> None:
    """`x -> M x` on the little-endian bits `qubits`, M invertible, with CNOTs and SWAPs only."""
    n = len(qubits)
    rows = [sum(((cols[c] >> r) & 1) << c for c in range(n)) for r in range(n)]
    ops: list[tuple[str, int, int]] = []
    for col in range(n):
        piv = next(r for r in range(col, n) if rows[r] >> col & 1)
        if piv != col:
            rows[col], rows[piv] = rows[piv], rows[col]
            ops.append(("swap", col, piv))
        for r in range(n):
            if r != col and rows[r] >> col & 1:
                rows[r] ^= rows[col]
                ops.append(("add", col, r))  # row r ^= row col
    # E_k ... E_1 M = I with self-inverse E, so M = E_1 ... E_k: apply E_k first.
    for kind, a, b in reversed(ops):
        if kind == "swap":
            builder.swap(qubits[a], qubits[b])
        else:
            builder.cx(qubits[a], qubits[b])


def xor_linear(builder: Any, src: Sequence[Any], dst: Sequence[Any], cols: Sequence[int]) -> None:
    """`dst ^= M src` (out of place) with CNOTs."""
    for i, c in enumerate(cols):
        for j in range(len(dst)):
            if c >> j & 1:
                builder.cx(src[i], dst[j])


@dataclass(frozen=True)
class Tower:
    """Constants of the tower GF(2^12) = GF(2^6)[y] / (y^2 + y + b) for kickmix's field objects."""

    to_tower: list[int]  # matrix: host polynomial bits -> (A, B) bits
    from_tower: list[int]  # matrix: (A, B) bits -> host polynomial bits
    embed: list[int]  # GF(2^6) bits (kickmix rep) -> host polynomial bits of the subfield element
    square: list[int]  # GF(2^6) matrix a -> a^2
    times_b: list[int]  # GF(2^6) matrix a -> b a
    b: int

    @classmethod
    def build(cls, gf12: Any, gf6: Any) -> Tower:
        h = gf6.degree
        if gf12.degree != 2 * h:
            raise ValueError("the tower is GF(2^(2h)) over GF(2^h)")
        one, q = 1, 1 << h
        sub = [a for a in range(1, 1 << (2 * h)) if gf12.pow(a, q) == a]
        g = next(a for a in sub if _poly_eval(gf12, gf6.modulus, a) == 0)  # root of the GF(2^6) modulus
        embed = [gf12.pow(g, i) for i in range(h)]
        psi = {_apply(embed, v): v for v in range(1 << h)}
        y = next(a for a in range(2, 1 << (2 * h)) if gf12.add(a, gf12.pow(a, q)) == one)
        b = gf12.mul(y, gf12.pow(y, q))
        if gf12.mul(y, y) != gf12.add(y, b):
            raise AssertionError("y^2 != y + b")
        from_tower = embed + [gf12.mul(e, y) for e in embed]
        square = [gf6.square(1 << i) for i in range(h)]
        b6 = psi[b]
        times_b = [gf6.mul(b6, 1 << i) for i in range(h)]
        return cls(_invert(from_tower), from_tower, embed, square, times_b, b6)


def _poly_eval(gf: Any, poly: int, a: int) -> int:
    out, power = 0, 1
    for i in range(poly.bit_length()):
        if poly >> i & 1:
            out ^= power
        power = gf.mul(power, a)
    return out
