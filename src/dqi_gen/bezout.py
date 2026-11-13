"""Classical prototype of the reciprocal-polynomial scan (QCC-19, E037; ADR-0009 stage 2).

Idea from the published description of a Berlekamp-Massey DQI decoder (Gu, Kemeny, Yelin, Lukin,
arXiv:2610.22367 SI I.1): in characteristic 2, `sigma(z) = E(z)^2 + z O(z)^2` and `sigma' = O^2`, so
`1 / sigma'` at the roots comes
from a Bezout identity of the half-degree pair `(E, O)`. This module is our own derivation of a constant-time
version, checked numerically:

* run Bernstein-Yang divsteps (`delta`, swap when `delta > 0` and `g(0) != 0`) on the *reversed* polynomials
  `E*(z) = z^17 E(1/z)` and `O*`, for `2 * 18` steps, tracking the first row `(u, v)` of the matrix;
* then `u E* + v O* = c z^36` exactly (the monomial index is always 36), `u` has its nonzero coefficients in
  `[2, 18]` and `v` in `[2, 19]`: 35 words;
* at a root `beta` of `sigma` (position `x = 1 / beta`):
  `1 / sigma'(beta) = (x^-1 u(x)^2 + v(x)^2) x^-38 / c^2`.
  With `u~ = x^-19 u`, `v~ = x^-19 v` and one square root constant this is `(v~ + x^(-1/2) u~)^2 / c^2`: two
  polynomial evaluations by CNOT networks (Chien constants), one linear squaring, no division per position.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

HALF = 18  # coefficients of E and O for a locator of degree at most 35


def padd(a: Sequence[int], b: Sequence[int]) -> list[int]:
    n = max(len(a), len(b))
    return [(a[i] if i < len(a) else 0) ^ (b[i] if i < len(b) else 0) for i in range(n)]


def pscale(gf: Any, c: int, a: Sequence[int]) -> list[int]:
    return [int(gf.mul(c, x)) for x in a]


def pmul(gf: Any, a: Sequence[int], b: Sequence[int]) -> list[int]:
    out = [0] * (len(a) + len(b))
    for i, x in enumerate(a):
        if x:
            for j, y in enumerate(b):
                out[i + j] ^= int(gf.mul(x, y))
    return out


def peval(gf: Any, a: Sequence[int], x: int) -> int:
    r = 0
    for c in reversed(a):
        r = int(gf.mul(r, x)) ^ c
    return r


def halves(gf: Any, sigma: Sequence[int]) -> tuple[list[int], list[int]]:
    """`E, O` with `sigma = E^2 + z O^2`: coefficientwise square roots of the even and odd coefficients."""
    s = list(sigma) + [0] * (2 * HALF - len(sigma))
    root = 1 << (gf.degree - 1)
    e = [int(gf.pow(s[2 * i], root)) for i in range(HALF)]
    o = [int(gf.pow(s[2 * i + 1], root)) for i in range(HALF)]
    return e, o


def bezout_rows(gf: Any, e: Sequence[int], o: Sequence[int]) -> tuple[list[int], list[int], int]:
    """`(u, v, steps)` with `u E* + v O* = c z^steps` for the reversed pair, by constant-time divsteps."""
    f, g = list(e)[::-1], list(o)[::-1]
    steps = 2 * HALF
    delta = 1
    uf, vf, ug, vg = [1], [0], [0], [1]
    for _ in range(steps):
        g0 = g[0] if g else 0
        if delta > 0 and g0:
            f, g = g, f
            uf, ug = ug, uf
            vf, vg = vg, vf
            delta = -delta
            g0 = g[0]
        if g0:
            c = int(gf.mul(g0, gf.invert(f[0]))) if f[0] else 0
            g = padd(g, pscale(gf, c, f))
            ug = padd(ug, pscale(gf, c, uf))
            vg = padd(vg, pscale(gf, c, vf))
        delta += 1
        g = g[1:]
        uf = [0] + uf
        vf = [0] + vf
    return uf, vf, steps


def reciprocal_at(gf: Any, sigma: Sequence[int], x: int) -> int:
    """`1 / sigma'(beta)` at the root `beta = 1 / x` of `sigma`, from the Bezout rows of the halves."""
    e, o = halves(gf, sigma)
    uf, vf, steps = bezout_rows(gf, e, o)
    tot = padd(pmul(gf, uf, e[::-1]), pmul(gf, vf, o[::-1]))
    nz = [i for i, c in enumerate(tot) if c]
    if nz != [steps]:
        raise ValueError("no monomial identity (degenerate input)")
    cc = tot[steps]
    u, v = peval(gf, uf, x), peval(gf, vf, x)
    inner = int(gf.mul(gf.invert(x), gf.mul(u, u))) ^ int(gf.mul(v, v))
    scale = gf.mul(gf.pow(x, 2 * HALF - 2), gf.invert(gf.mul(gf.pow(x, 2 * steps), gf.mul(cc, cc))))
    return int(gf.mul(inner, scale))
