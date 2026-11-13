"""A GF(2^24) multiplier of bilinear rank 99 (our own construction, QCC-19, E041).

The ring is `K = GF(2^12)[theta] / (theta^2 + theta + DELTA)` with `DELTA = 2048` (absolute trace 1, so `K` is
a field). A 24-bit word is `(a, b) = a + b theta`: bits 0..11 hold `a`, bits 12..23 hold `b`, both in the
kickmix GF(2^12) polynomial basis. The multiplier follows the same recipe as `gfmul.py`:

* `K` is a degree-6 extension of GF(16) (a subfield of GF(2^12)): pick `theta'` in `K` so that the 24
  products `beta_r theta'^i` (`beta_r` the F2-basis `1, w, s, w s` of GF(16), `w^2 = w + 1`) form an F2-basis;
  an element is `sum_i a_i theta'^i` with `a_i` in GF(16);
* the product is a polynomial product of degree 10 over GF(16), evaluated at 11 points of GF(16);
* each pointwise GF(16) product has rank 9 by two levels of quadratic Karatsuba over GF(4): the AND forms on
  the coordinates `(c0, c1, c2, c3)` are `c0, c1, c0+c1, c2, c3, c2+c3, c0+c2, c1+c3, c0+c1+c2+c3`;
* all evaluation, interpolation and reduction maps are F2-linear (CNOT networks); the output matrix `W` is
  found by solving from random samples and checked on the 576 basis pairs and on random pairs.

Rank 11 x 9 = 99 against 3 x 42 = 126 by Karatsuba over our GF(2^12) multiplier.
"""

from __future__ import annotations

import random
from functools import cache
from typing import Any

import kickmix as km  # type: ignore[import-not-found,unused-ignore]

from dqi_gen.gfmul import _parity, _solve

DELTA = 2048
POINTS = 11
GF16_FORMS = (0b0001, 0b0010, 0b0011, 0b0100, 0b1000, 0b1100, 0b0101, 0b1010, 0b1111)


def _gf() -> Any:
    return km.GF2Field(12)


def mul24(a: int, b: int) -> int:
    """Product in `K` of two 24-bit words."""
    gf = _gf()
    a0, a1, b0, b1 = a & 4095, a >> 12, b & 4095, b >> 12
    aa, bb = int(gf.mul(a0, b0)), int(gf.mul(a1, b1))
    mixed = int(gf.mul(a0 ^ a1, b0 ^ b1))
    return (aa ^ int(gf.mul(DELTA, bb))) | ((mixed ^ aa) << 12)


def _inverse_rows(columns: list[int], n: int) -> list[int]:
    """Row masks of the inverse of the F2 matrix whose columns are `columns` (ints over `n` bits)."""
    rows = [sum(((c >> i) & 1) << j for j, c in enumerate(columns)) | (1 << (n + i)) for i in range(n)]
    for j in range(n):
        piv = next((i for i in range(j, n) if rows[i] >> j & 1), None)
        if piv is None:
            raise ValueError("singular")
        rows[j], rows[piv] = rows[piv], rows[j]
        for i in range(n):
            if i != j and rows[i] >> j & 1:
                rows[i] ^= rows[j]
    return [row >> n for row in rows]


def _apply(rows: list[int], v: int) -> int:
    return sum(_parity(r & v) << j for j, r in enumerate(rows))


@cache
def bilinear24() -> tuple[tuple[int, ...], tuple[int, ...]]:
    """`(U, W)`: AND `i` is `<U[i], a> * <U[i], b>` over F2 (masks over the 24 operand bits); output bit `j`
    of
    `a * b` is the XOR of the ANDs selected by mask `W[j]`."""
    gf = _gf()
    sub16 = [x for x in range(4096) if gf.pow(x, 16) == x]
    w = next(x for x in sub16 if x > 1 and int(gf.mul(x, x)) ^ x ^ 1 == 0)
    s = next(x for x in sub16 if x not in (0, 1, w, w ^ 1))
    b16 = [1, w, s, int(gf.mul(w, s))]
    coord16 = {}
    for c in range(16):
        x = 0
        for r in range(4):
            if c >> r & 1:
                x ^= b16[r]
        coord16[x] = c
    assert len(coord16) == 16 and set(coord16) == set(sub16)
    theta = 1 << 12  # the element theta = (0, 1)
    for t0 in range(4096):
        thp = theta ^ t0  # theta' = theta + t0
        cols, p = [], 1
        powers = []
        for _ in range(6):
            powers.append(p)
            p = mul24(p, thp)
        for i in range(6):
            for r in range(4):
                cols.append(mul24(powers[i], b16[r]))
        try:
            inv_rows = _inverse_rows(cols, 24)  # circuit bits -> coordinates in the basis `cols`
        except ValueError:
            continue
        break
    else:  # pragma: no cover
        raise AssertionError("no degree-6 generator over GF(16)")
    pts = sub16[:POINTS]
    forms: list[int] = []
    for pt in pts:
        # circuit bit -> coordinates in the `cols` basis -> value of a(pt) in GF(16) -> 4 coordinates
        eval_cols = []
        for sbit in range(24):
            c = _apply(inv_rows, 1 << sbit)
            val = 0
            for idx in range(24):
                if c >> idx & 1:
                    i, r = divmod(idx, 4)
                    val ^= int(gf.mul(b16[r], gf.pow(pt, i)))
            eval_cols.append(coord16[val])
        coord_forms = [sum(((eval_cols[sb] >> bit) & 1) << sb for sb in range(24)) for bit in range(4)]
        for m in GF16_FORMS:
            mask = 0
            for bit in range(4):
                if m >> bit & 1:
                    mask ^= coord_forms[bit]
            forms.append(mask)
    n_and = len(forms)
    rng = random.Random(24)
    rows, rhs = [], []
    for _ in range(4 * n_and + 64):
        a, b = rng.randrange(1 << 24), rng.randrange(1 << 24)
        rows.append(sum((_parity(a & f) & _parity(b & f)) << i for i, f in enumerate(forms)))
        rhs.append(mul24(a, b))
    sol = _solve(rows, rhs, n_and, 24)
    if sol is None:
        raise AssertionError(f"no rank-{n_and} algorithm found")
    return tuple(forms), tuple(sol)


def classical_mul24(a: int, b: int) -> int:
    forms, w = bilinear24()
    ands = [_parity(a & f) & _parity(b & f) for f in forms]
    out = 0
    for j in range(24):
        bit = 0
        for i, x in enumerate(ands):
            if w[j] >> i & 1:
                bit ^= x
        out |= bit << j
    return out


class FastMul24:
    """`ixor_mul(lhs, rhs, target)`: `target ^= lhs * rhs` in `K` (24-bit registers) with 99 Toffolis."""

    def __init__(self, builder: Any):
        self.b = builder
        self.forms, self.w = bilinear24()
        self.rank = len(self.forms)

    def _load(self, reg: Any, mask: int, dst: Any) -> None:
        for s in range(24):
            if mask >> s & 1:
                self.b.cx(reg[s], dst)

    def ixor_mul(self, lhs: Any, rhs: Any, target: Any) -> None:
        b = self.b
        ta, tb, c = b.alloc_qubits(3)
        for i, f in enumerate(self.forms):
            self._load(lhs, f, ta)
            self._load(rhs, f, tb)
            b.init_and(ta, tb, c)
            for j in range(24):
                if self.w[j] >> i & 1:
                    b.cx(c, target[j])
            b.del_and(ta, tb, c)
            self._load(lhs, f, ta)
            self._load(rhs, f, tb)
        b.free(ta)
        b.free(tb)
        b.free(c)
