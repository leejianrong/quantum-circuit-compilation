"""A low-rank GF(2^m) multiplier: `target ^= a * b` with 42 Toffolis for m = 12 (our own construction).

The kickmix builtin costs 63 Toffolis for GF(2^12). Here the field is a degree-`e` extension of GF(8)
(`e = m / 3`), an element is `sum_i a_i theta^i` with `a_i` in GF(8) and `theta` a primitive element, and the
product is a polynomial product over GF(8) evaluated at `2e - 1` points of the projective line over GF(8)
(rank `2e - 1` GF(8) products, each of rank 6 over F2 by the 0, 1, infinity and GF(4) residues): rank 42 for
m = 12, 18 for m = 6. Everything but the AND gates is F2-linear, so the algorithm is the list of linear forms
`U` (one per AND, used on both operands) and a matrix `W` (`m x rank`) found numerically by solving for `W`
from random samples and then checked on fresh pairs (`tests/unit/test_dqi_gfmul.py`).

Circuit: for each AND `i`, the two forms are accumulated on one qubit each by CNOTs, `init_and` costs one
Toffoli, its result is XORed into the target bits listed in column `i` of `W`, and `del_and` clears it for
free. Extra qubits: 3.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from functools import cache
from typing import Any

import kickmix as km  # type: ignore[import-not-found,unused-ignore]

_SUB = 3  # subfield degree
# AND gates of one GF(8) product (coordinates in the basis 1, gamma, gamma^2): masks over x0, x1, x2.
# x0 y0, x2 y2, (x0+x1+x2)(y0+y1+y2), then the GF(4) residue u = x0+x2, v = x1+x2 by Karatsuba:
# u u', v v', (u+v)(u'+v').
_GF8_FORMS = (0b001, 0b100, 0b111, 0b101, 0b110, 0b011)


def _parity(x: int) -> int:
    return x.bit_count() & 1


def _gf8(gf: Any) -> tuple[list[int], int]:
    """(elements of the order-8 subfield inside `gf`, a generator gamma of its multiplicative group)."""
    elems = [a for a in range(1 << gf.degree) if gf.pow(a, 8) == a]
    gamma = next(a for a in elems if a > 1 and all(gf.pow(a, k) != 1 for k in range(1, 7)))
    return elems, gamma


def _solve(rows: list[int], rhs: list[int], width: int, n_out: int) -> list[int] | None:
    """Solve `rows[s] . x_o = bit o of rhs[s]` over F2; returns, per output bit o, the bitmask x_o."""
    pivots: dict[int, tuple[int, int]] = {}  # pivot column -> (row, rhs), rows reduced against earlier pivots
    for r, y in zip(rows, rhs, strict=True):
        while r:
            pc = r.bit_length() - 1
            if pc not in pivots:
                break
            pr, py = pivots[pc]
            r ^= pr
            y ^= py
        if r:
            pivots[r.bit_length() - 1] = (r, y)
        elif y:
            return None
    if len(pivots) < width:
        return None
    sol = [0] * n_out
    known: dict[int, int] = {}  # column -> rhs bits of that unknown (back substitution, low pivots first)
    for pc in sorted(pivots):
        r, y = pivots[pc]
        rest = r ^ (1 << pc)
        for c in range(pc):
            if rest >> c & 1:
                y ^= known[c]
        known[pc] = y
    for pc, y in known.items():
        for o in range(n_out):
            if y >> o & 1:
                sol[o] |= 1 << pc
    return sol


@cache
def bilinear_algorithm(degree: int) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """`(U, W)` for the field of kickmix's `GF2Field(degree)`: AND `i` is `<U[i], a> * <U[i], b>` over F2 (bit
    masks over the operand bits) and output bit `j` of `a * b` is the XOR of the ANDs in mask `W[j]`."""
    if degree % _SUB:
        raise ValueError("degree must be a multiple of 3")
    gf = km.GF2Field(degree)
    e = degree // _SUB
    sub, gamma = _gf8(gf)
    theta = gf.primitive_element
    basis = [gf.mul(gf.pow(gamma, r), gf.pow(theta, i)) for i in range(e) for r in range(_SUB)]
    lookup: dict[int, int] = {}  # host element -> coordinate bits in `basis`
    for combo in range(1 << degree):
        x = 0
        for s in range(degree):
            if combo >> s & 1:
                x ^= basis[s]
        lookup[x] = combo
    if len(lookup) != 1 << degree:
        raise AssertionError("basis is not an F2-basis")
    sub_coord = {x: lookup[x] for x in sub}  # GF(8) element -> its 3 bits
    sub_elem = {v: x for x, v in sub_coord.items()}
    points: list[int | None] = [None, 0, 1] + [gf.pow(gamma, k) for k in range(1, 5)]
    points = points[: 2 * e - 1]

    def evaluate(a: int, p: int | None) -> int:
        """The GF(8) element sum a_i p^i (the top coefficient for infinity) as 3 coordinate bits."""
        c = lookup[a]
        ai = [sub_elem[(c >> (_SUB * i)) & 7] for i in range(e)]
        if p is None:
            return sub_coord[ai[-1]]
        acc = 0
        for i, v in enumerate(ai):
            acc ^= gf.mul(v, gf.pow(p, i))
        return sub_coord[acc]

    forms: list[int] = []
    for p in points:
        cols = [evaluate(1 << s, p) for s in range(degree)]
        coord_forms = [sum(((cols[s] >> bit) & 1) << s for s in range(degree)) for bit in range(_SUB)]
        for m in _GF8_FORMS:
            mask = 0
            for bit in range(_SUB):
                if m >> bit & 1:
                    mask ^= coord_forms[bit]
            forms.append(mask)
    n_and = len(forms)
    rng = random.Random(1234)
    rows, rhs = [], []
    for _ in range(4 * n_and + 64):
        a, b = rng.randrange(1 << degree), rng.randrange(1 << degree)
        ands = sum((_parity(a & f) & _parity(b & f)) << i for i, f in enumerate(forms))
        rows.append(ands)
        rhs.append(gf.mul(a, b))
    sol = _solve(rows, rhs, n_and, degree)
    if sol is None:
        raise AssertionError(f"no rank-{n_and} algorithm found for degree {degree}")
    return tuple(forms), tuple(sol)


def classical_mul(degree: int, a: int, b: int) -> int:
    forms, w = bilinear_algorithm(degree)
    ands = [_parity(a & f) & _parity(b & f) for f in forms]
    out = 0
    for j in range(degree):
        bit = 0
        for i, x in enumerate(ands):
            if w[j] >> i & 1:
                bit ^= x
        out |= bit << j
    return out


class FastMul:
    """`ixor_mul(lhs, rhs, target)` = `target ^= lhs * rhs` in GF(2^degree) with `rank` Toffolis."""

    def __init__(self, builder: Any, field: Any):
        self.b = builder
        self.gf = field
        self.deg = field.degree
        self.forms, self.w = bilinear_algorithm(self.deg)
        self.rank = len(self.forms)

    def _load(self, reg: Sequence[Any], mask: int, dst: Any) -> None:
        for s in range(self.deg):
            if mask >> s & 1:
                self.b.cx(reg[s], dst)

    def ixor_mul(self, lhs: Any, rhs: Any, target: Any) -> None:
        b = self.b
        ta, tb, c = b.alloc_qubits(3)
        for i, f in enumerate(self.forms):
            self._load(lhs, f, ta)
            self._load(rhs, f, tb)
            b.init_and(ta, tb, c)
            for j in range(self.deg):
                if self.w[j] >> i & 1:
                    b.cx(c, target[j])
            b.del_and(ta, tb, c)
            self._load(lhs, f, ta)
            self._load(rhs, f, tb)
        b.free(ta)
        b.free(tb)
        b.free(c)
