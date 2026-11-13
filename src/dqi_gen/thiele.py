"""Classical model of the quadratic-node rational-reconstruction decoder (QCC-19, stage 2, E041).

Our re-derivation, in our own words, of the architecture of the public 889-qubit DQI circuit (syed3000's
Apache-2.0 builder sources were read as a reference; no code is copied here). The facts, each checked in
`tests/unit/test_dqi_thiele.py`:

* Let `a_j = alpha^j` be the error positions, `S_t = sum_j e_j a_j^t` the syndromes (t = 1 .. 70), and
  `M(z) = prod_{i<35} (z^2 + z + kappa_i)` with 35 constants `kappa_i` of absolute trace 1, so each factor is
  irreducible over GF(2^12) and `M` has degree 70. The polynomial
      P(z) = sum_j e_j a_j (M(z) + M(a_j)) / (z + a_j)
  has degree below 70 and coefficients that are fixed GF(2^12)-linear combinations of the syndromes.
* At a root `alpha_i` of the i-th quadratic `P(alpha_i) = R(alpha_i)`, `R = N / D`, `D(z) = prod (z + a_j)`
  and `N(z) = sum_j e_j W_j D(z) / (z + a_j)`, `W_j = a_j M(a_j)`: the 35 residues `Y_i = P mod q_i` (24 bits
  each, 840 bits in all) are the values of one rational function with `deg N < w <= deg D` at the 35 nodes.
  840 bits in all) are the values of one rational function with `deg N < w <= deg D` at the 35 nodes.
* `(N, D)` follows from the residues by Thiele-type recursion (`extract`): at step `i` the head
  `P_i = D(alpha_i) / N(alpha_i)` (a linear polynomial, 24 bits) is recorded and
  `(N, D) <- ((D + P_i N) / q_i, N)`. Done on residues, this is an in-place O(n^2) pass of GF(2^24) products;
  every pivot is a GF(2^24) element, so it is zero with probability about 2^-24 per step.
* The error value at a root `a` of `D` is `e = N(a) / (W D'(a))`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import kickmix as km  # type: ignore[import-not-found,unused-ignore]

DELTA = 2048
NODES = 35


def field() -> Any:
    return km.GF2Field(12)


def kappas(gf: Any) -> list[int]:
    out = []
    for i in range(NODES):
        t = 2 * i
        out.append(DELTA ^ int(gf.mul(t, t)) ^ t)
    return out


def trace(gf: Any, a: int) -> int:
    v = 0
    for _ in range(12):
        v ^= a
        a = int(gf.mul(a, a))
    return v


def trim(p: Sequence[int]) -> list[int]:
    p = list(p)
    while p and p[-1] == 0:
        p.pop()
    return p


def padd(a: Sequence[int], b: Sequence[int]) -> list[int]:
    out = [0] * max(len(a), len(b))
    for i, x in enumerate(a):
        out[i] ^= x
    for i, x in enumerate(b):
        out[i] ^= x
    return trim(out)


def pmul(gf: Any, a: Sequence[int], b: Sequence[int]) -> list[int]:
    if not a or not b:
        return []
    out = [0] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        if x:
            for j, y in enumerate(b):
                out[i + j] ^= int(gf.mul(x, y))
    return trim(out)


def pdivmod(gf: Any, a: Sequence[int], b: Sequence[int]) -> tuple[list[int], list[int]]:
    a, b = trim(a), trim(b)
    q = [0] * max(0, len(a) - len(b) + 1)
    inv = int(gf.invert(b[-1]))
    while len(a) >= len(b):
        s = len(a) - len(b)
        f = int(gf.mul(a[-1], inv))
        q[s] = f
        for i, x in enumerate(b):
            a[i + s] ^= int(gf.mul(f, x))
        a = trim(a)
    return trim(q), a


def peval(gf: Any, p: Sequence[int], x: int) -> int:
    r = 0
    for c in reversed(p):
        r = int(gf.mul(r, x)) ^ c
    return r


def modulus(gf: Any) -> list[int]:
    m = [1]
    for c in kappas(gf):
        m = pmul(gf, m, [c, 1, 1])
    assert len(m) == 71 and m[-1] == 1
    return m


def syndromes_of(gf: Any, word: dict[int, int], n: int = 70) -> list[int]:
    """`S_t = sum_j e_j a_j^t` for `t = 1 .. n` (the benchmark's `S_i` with `i = t - 1`)."""
    alpha = gf.primitive_element
    out = [0] * n
    for j, e in word.items():
        a = int(gf.pow(alpha, j))
        p = a
        for t in range(n):
            out[t] ^= int(gf.mul(e, p))
            p = int(gf.mul(p, a))
    return out


def residue_polynomial(gf: Any, s: Sequence[int]) -> list[int]:
    """`P(z)` of degree below 70 from the syndromes `S_1 .. S_70`: `P_k = sum_{i > k} M_i S'_{i-k}` with
    `S'_t` the power sum of exponent `t` (a fixed linear map)."""
    m = modulus(gf)
    return [_xor(int(gf.mul(m[i], s[i - k - 1])) for i in range(k + 1, 71)) for k in range(70)]


def _xor(it: Any) -> int:
    v = 0
    for x in it:
        v ^= x
    return v


def residues(gf: Any, p: Sequence[int]) -> list[tuple[int, int]]:
    """`P mod (z^2 + z + kappa_i)` as `(r0, r1)` for each node: the 24-bit word `Y_i`."""
    out = []
    for c in kappas(gf):
        a = b = 0
        for x in reversed(list(p)):
            a, b = x ^ int(gf.mul(c, b)), a ^ b
        out.append((a, b))
    return out


def reconstruct(gf: Any, p: Sequence[int]) -> tuple[list[int], list[int]]:
    """`(N, D)` with `N / D = P mod M`, `deg N < deg D <= 35`, by Euclid on `(M, P)` (reference)."""
    r0, r1 = modulus(gf), trim(p)
    t0, t1 = [], [1]  # cofactors of P: r_i = s_i M + t_i P
    while len(r1) - 1 >= 35 + 0 and r1:
        q, r = pdivmod(gf, r0, r1)
        r0, r1 = r1, r
        t0, t1 = t1, padd(t0, pmul(gf, q, t1))
    # r1 = t1 * P (mod M): N = r1, D = t1
    return r1, t1


def amplitude(gf: Any, n: Sequence[int], d: Sequence[int], a: int) -> int:
    """Error value at a root `a` of `d`: `e = N(a) / (W D'(a))`, `W = a M(a)`."""
    m = modulus(gf)
    dp = [d[i] if i % 2 == 1 else 0 for i in range(1, len(d))]
    w = int(gf.mul(a, peval(gf, m, a)))
    num = peval(gf, n, a)
    den = int(gf.mul(w, peval(gf, dp, a)))
    return int(gf.mul(num, gf.invert(den)))


# ---- residue-level extraction and synthesis (the in-place algorithm, classically) --------------------

Pair = tuple[int, int]


def qmul(gf: Any, x: Pair, y: Pair, c: int) -> Pair:
    """Product in `GF(2^12)[z] / (z^2 + z + c)`; an element is `(r0, r1) = r0 + r1 z`."""
    a, b = x
    d, e = y
    s = int(gf.mul(b, e))
    return int(gf.mul(a, d)) ^ int(gf.mul(c, s)), int(gf.mul(a, e)) ^ int(gf.mul(b, d)) ^ s


def qinv(gf: Any, y: Pair, c: int) -> Pair | None:
    """Inverse via the norm `a^2 + a b + c b^2`; `None` when the norm is zero."""
    a, b = y
    norm = int(gf.mul(a, a)) ^ int(gf.mul(a, b)) ^ int(gf.mul(c, gf.mul(b, b)))
    if not norm:
        return None
    r = int(gf.invert(norm))
    return int(gf.mul(a ^ b, r)), int(gf.mul(b, r))


def extract(gf: Any, res: Sequence[Pair]) -> tuple[list[Pair], int]:
    """Thiele-type pass on the residues: the heads `P_0 .. P_{w-1}` (each `r0 + r1 z`) and the weight `w`.

    Per node `l` the pair `(n_l, d_l)` holds the values of `(N, D)` up to a common scale, from `(Y_l, 1)`.
    Step `i`: `P_i = d_i / n_i`; for later nodes `(n_l, d_l) <- ((d_l + P_i n_l) / q_i(alpha_l), n_l)`; node
    `l` the ring has `z^2 = z + kappa_l`, so `q_i(alpha_l) = kappa_l + kappa_i` is a nonzero constant. Returns
    `w = -1` when a pivot that should be invertible has zero norm (a failure of the pass).
    """
    ks = kappas(gf)
    n = [(int(r[0]), int(r[1])) for r in res]
    d: list[Pair] = [(1, 0)] * NODES
    heads: list[Pair] = []
    for i in range(NODES):
        if n[i] == (0, 0):
            return heads, i
        inv = qinv(gf, n[i], ks[i])
        if inv is None:
            return heads, -1
        h = qmul(gf, d[i], inv, ks[i])
        heads.append(h)
        for lnode in range(i + 1, NODES):
            c = ks[lnode]
            pn = qmul(gf, h, n[lnode], c)
            scale = int(gf.invert(ks[lnode] ^ ks[i]))
            top = (d[lnode][0] ^ pn[0], d[lnode][1] ^ pn[1])
            d[lnode] = n[lnode]
            n[lnode] = (int(gf.mul(top[0], scale)), int(gf.mul(top[1], scale)))
    return heads, NODES


def synthesize(gf: Any, heads: Sequence[Pair]) -> tuple[list[int], list[int]]:
    """`(N, D)` up to a scalar from the heads: `(N, D) <- (D, q_i N + P_i D)`, last head first."""
    ks = kappas(gf)
    n: list[int] = []
    d: list[int] = [1]
    for i in reversed(range(len(heads))):
        n, d = d, padd(pmul(gf, [ks[i], 1, 1], n), pmul(gf, trim(list(heads[i])), d))
    return n, d
