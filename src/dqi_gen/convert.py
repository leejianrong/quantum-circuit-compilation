"""Classical model of the convert stage: the amplitude polynomial `C` (QCC-19, E041).

The plain scan divides at every position: `e = N(a) / (a M(a) D'(a))` costs a field inversion at each of
the 4095 positions. The convert stage computes once, from `(N, D)`, the polynomial `C` with
`C D' = N (mod D)`; then `e_j = C(a_j) / (a_j M(a_j))` at every root `a_j` of `D`. The scan is then the
zero test of `D(a_j)` plus a phase that is linear in the coefficients of `C` (a CZ network after folding the
classical constant `1 / (a_j M(a_j))` into the mask), about 11 Toffolis per position instead of about 96.

Facts used (char 2, `D = A(x)^2 + x B(x)^2`, `D' = B^2`, `A`, `B` the square roots of the even and odd
coefficient words): `D'` is a square, so the inversion `D'^{-1} mod D` is a half-degree problem on `(A, B)`
(a Bezout system of half size), which is what the coherent version has to solve in place.
`half_profile` and `admitted` measure the Euclid degree profile of `(A, B)`, whose drops decide the fixed
schedule of that solve (each drop of 2 costs probability about 1/4096).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from dqi_gen import thiele as T


def derivative(d: Sequence[int]) -> list[int]:
    """`D'` in char 2: the odd coefficients moved down one place."""
    return T.trim([d[i + 1] if i % 2 == 0 else 0 for i in range(len(d) - 1)])


def inverse_mod(gf: Any, a: Sequence[int], m: Sequence[int]) -> list[int]:
    """`a^{-1} mod m` by the extended Euclid (reference, history kept)."""
    r0, r1 = T.trim(m), T.trim(a)
    t0: list[int] = [0]
    t1: list[int] = [1]
    while any(r1):
        q, r = T.pdivmod(gf, r0, r1)
        r0, r1 = r1, r
        t0, t1 = t1, T.padd(t0, T.pmul(gf, q, t1))
    if len(r0) != 1:
        raise ZeroDivisionError("D' and D are not coprime")
    s = int(gf.invert(r0[0]))
    return T.pdivmod(gf, [int(gf.mul(s, c)) for c in t0], m)[1]


def amplitude_polynomial(gf: Any, n: Sequence[int], d: Sequence[int]) -> list[int]:
    """`C` with `C D' = N (mod D)`, degree below `deg D`."""
    inv = inverse_mod(gf, derivative(d), d)
    return T.pdivmod(gf, T.pmul(gf, list(n), inv), d)[1]


def error_value(gf: Any, c: Sequence[int], a: int) -> int:
    """`e` at the root `a` of `D` from `C`: `C(a) / (a M(a))`."""
    w = int(gf.mul(a, T.peval(gf, T.modulus(gf), a)))
    return int(gf.mul(T.peval(gf, c, a), gf.invert(w)))


def _sqrt(gf: Any, x: int) -> int:
    for _ in range(11):
        x = int(gf.mul(x, x))
    return x


def half_profile(gf: Any, d: Sequence[int]) -> list[int]:
    """Degrees of the Euclid sequence of `(A, B)`, the square roots of the even and odd coefficient words."""
    a = T.trim([_sqrt(gf, x) for x in d[::2]])
    b = T.trim([_sqrt(gf, x) for x in d[1::2]])
    degrees = [len(a) - 1]
    while any(b):
        degrees.append(len(b) - 1)
        a, b = b, T.pdivmod(gf, a, b)[1]
    return degrees


def admitted(gf: Any, d: Sequence[int]) -> bool:
    """The half Euclid ends at degree 0 and every drop is at most 2 (two drops of 2 at once are excluded)."""
    degrees = half_profile(gf, d)
    if degrees[-1] != 0:
        return False
    drops = [x - y for x, y in zip(degrees, degrees[1:], strict=False)]
    return max(drops, default=1) <= 2
