"""Classical reference of the dialog-free Jacobi (Lanczos) key-equation solver (QCC-19).

Design and numbers: docs/experiments/dqi-inplace.md. The syndromes are moments
`S_i = L(z^i) = sum_j w_j x_j^i` with nodes `x_j = alpha^j` and weights `w_j = e_j x_j` (the benchmark's `S_i = sum_j e_j alpha^((i+1) j)`).
The monic polynomials orthogonal for `L` obey, in characteristic 2,

    p_{k+1} = (z + a_k) p_k + b_k p_{k-1},   h_k = L(p_k z^k) = sum_i p_{k,i} S_{k+i},
    a_k = s_k / h_k + p_{k,k-1},   s_k = sum_i p_{k,i} S_{k+1+i},   b_k = h_k / h_{k-1}.

For weight `w` the recurrence stops at `k = w` (`h_w = 0`) and `p_w` is the locator, with roots at the nodes.
The error values follow from Gauss quadrature, `w_j = h_{w-1} / (p_{w-1}(x_j) p_w'(x_j))`: no Omega.
Facts the circuit relies on, checked by the tests:

* `(a_k, b_k)` are recoverable from the pair `(p_{k+1}, p_k)` (they sit in two coefficients): no dialog.
* After `p_k` is known, `S_{k-1} = sum_{i>=1} p_{k,i} S_{k-1+i} / p_{k,0}`: erase it in place, reuse its
  qubits; heads at step `k' >= k` only read `S_{k'..2k'+1}`.
* The failures of the scheme are premature `h_k = 0` and `p_k(0) = 0`, each about `2^-12` per step.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import kickmix as km  # type: ignore[import-not-found,unused-ignore]


@dataclass
class Solution:
    stopped_at: int  # k with h_k = 0 (the weight), or t when the recurrence ran to the end
    p: list[int]  # p_k coefficients, index = power of z (monic at index stopped_at)
    p_prev: list[int]
    h_prev: int  # h_{k-1}
    erase_ok: bool  # p_{j,0} != 0 for every step that erases S_{j-1}


def _dot(gf: Any, p: Sequence[int], s: Sequence[int], off: int) -> int:
    acc = 0
    for i, c in enumerate(p):
        if c:
            acc ^= gf.mul(c, s[off + i])
    return acc


def solve(gf: Any, s: Sequence[int], t: int) -> Solution:
    """Runs the recurrence on `s` (length at least `2t`) for at most `t` steps."""
    p, pp, hp = [1], [], 0
    erase_ok = True
    for k in range(t):
        h = _dot(gf, p, s, k)
        if h == 0:
            return Solution(k, p, pp, hp, erase_ok)
        if k >= 1 and p[0] == 0:
            erase_ok = False
        a = gf.mul(_dot(gf, p, s, k + 1), gf.invert(h)) ^ (p[k - 1] if k >= 1 else 0)
        b = gf.mul(h, gf.invert(hp)) if k >= 1 else 0
        new = [0] * (k + 2)
        for i, c in enumerate(p):
            new[i + 1] ^= c
            new[i] ^= gf.mul(a, c)
        for i, c in enumerate(pp):
            new[i] ^= gf.mul(b, c)
        pp, p, hp = p, new, h
    return Solution(t, p, pp, hp, erase_ok)


def peel(gf: Any, p_next: Sequence[int], p: Sequence[int]) -> tuple[int, int, list[int]]:
    """Recovers `(a_k, b_k, p_{k-1})` from `(p_{k+1}, p_k)`: the pair carries the recurrence parameters."""
    k = len(p) - 1
    a = p_next[k] ^ (p[k - 1] if k >= 1 else 0)
    b = p_next[k - 1] ^ (p[k - 2] if k >= 2 else 0) ^ gf.mul(a, p[k - 1]) if k >= 1 else 0
    if k == 0 or b == 0:
        return a, b, []
    inv_b = gf.invert(b)
    q = [0] * k
    for i in range(k):
        v = p_next[i] ^ gf.mul(a, p[i]) ^ (p[i - 1] if i >= 1 else 0)
        q[i] = gf.mul(v, inv_b)
    return a, b, q


def erase_value(gf: Any, p: Sequence[int], s: Sequence[int], k: int) -> int:
    """`S_{k-1}` from `p_k` and `S_{k..2k-1}` (valid when `p_k(0) != 0`)."""
    acc = 0
    for i in range(1, len(p)):
        if p[i]:
            acc ^= gf.mul(p[i], s[k - 1 + i])
    return gf.mul(acc, gf.invert(p[0]))


def poly_eval(gf: Any, p: Sequence[int], x: int) -> int:
    r = 0
    for c in reversed(p):
        r = gf.mul(r, x) ^ c
    return r


def gauss_weight(gf: Any, sol: Solution, x: int) -> int:
    """Weight `w_j` at a root `x` of `p_w`: `h_{w-1} / (p_{w-1}(x) p_w'(x))`."""
    dp = [c if i % 2 == 1 else 0 for i, c in enumerate(sol.p)][1:]
    den = gf.mul(poly_eval(gf, sol.p_prev, x), poly_eval(gf, dp, x))
    return gf.mul(sol.h_prev, gf.invert(den))


def syndromes(gf: Any, values: dict[int, int], n: int) -> list[int]:
    """`S_i = sum_j e_j alpha^((i+1) j)` for an error word `position -> value`."""
    alpha = gf.primitive_element
    out = [0] * n
    for j, e in values.items():
        for i in range(n):
            out[i] ^= gf.mul(e, gf.pow(alpha, (i + 1) * j))
    return out


def field(degree: int) -> Any:
    return km.GF2Field(degree)
