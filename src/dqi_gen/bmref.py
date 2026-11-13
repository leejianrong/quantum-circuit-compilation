"""Classical reference of the dialog-free divstep (Berlekamp-Massey) solver (QCC-19, E030).

Same rows as `decoder.py` (sigma row `g`, template row `f`, scalar `b`, counter `delta`), but the per-step
dialog (quotient `c`, swap bit) is not stored. Idea from the published description of Berlekamp-Massey with an
invariant (Gu, Kemeny, Yelin, Lukin, arXiv:2610.22367 SI I.1), re-derived here for our rows:

* invariant `g[0] * b = 1`; the shifted template has `f[0] = 0`, so after a step with a swap (a "replace",
  d != 0 and delta > 0) `g[0] = 1 / d_old`;
* a replace step is recognised from the after-state by `f_unshifted[0] != 0`, and its quotient is
  `c = 1 / (f[0] * b)`: no storage;
* a non-swap step with `d != 0` ("retain") has no trace in the state: its quotient goes on a stack of capacity
  one together with the step index. A second retain step is a failure of the circuit.

`solve` returns the final rows and whether the reverse reconstruction would succeed (`ok`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass
class Result:
    g: list[int]
    ok: bool
    retains: int
    max_f_overflow: int  # steps at which the template row's top coefficient was nonzero past index t


def solve(gf: Any, s: Sequence[int], t: int, *, capacity: int = 1) -> Result:
    n = 2 * t
    g = [1] + [0] * t
    f = [0] * (t + 1)
    b, delta = 1, 1
    retains = 0
    stack = 0
    overflow = 0
    ok = True
    for k in range(n):
        d = 0
        for i in range(min(t, k) + 1):
            if g[i]:
                d ^= gf.mul(g[i], s[k - i])
        sw = delta >= 0 and d != 0
        if sw:
            g, f = f, g
            d, b = b, d
            delta = -delta
        c = gf.mul(d, gf.invert(b)) if d else 0
        if sw and c != gf.invert(gf.mul(f[0], b)):
            ok = False
        if not sw and f[0] != 0:
            ok = False
        if c:
            for i in range(t + 1):
                g[i] ^= gf.mul(c, f[i])
            if not sw:
                retains += 1
                stack += 1
                if stack > capacity:
                    ok = False
        delta += 1
        if f[t] == 0:
            f = [0] + f[:t]  # shift up by z
        else:
            overflow += 1  # frozen: the circuit records one `sh` bit per step
    return Result(g, ok, retains, overflow)
