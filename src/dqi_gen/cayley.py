"""Classical prototype: block pivots by moving the key equation to the quadratic extension (QCC-19).

Syndromes are moments `S_m = sum_j w_j x_j^m` with nodes `x_j` in F_q. Take `theta` in F_{q^2} outside F_q,
`thetabar = theta^q`, and the node change `u = (x + theta) / (x + thetabar)` (on the unit circle of F_{q^2}).
The sequence

    T_i = sum_m [z^m] ((z + theta)^i (z + thetabar)^(N - i)) S_m = sum_j W_j u_j^i,
    W_j = w_j (x_j + thetabar)^N

is a linear image of `S` (N = n - 1) with `T_{N-i} = conj(T_i)`, so only half of it is independent: as many
bits as `S`. Its weights `W_j` are generic elements of F_{q^2}, so the Hankel minors the Lanczos recursion
pivots on vanish with probability about `1 / q^2` per step instead of `1 / q`. Measured in
`tests/unit/test_dqi_cayley.py` and `docs/experiments/dqi-stage2.md`.

Nothing here comes from a public circuit: it is the Cayley transform of the projective line over F_q onto the
unit circle of F_{q^2}, with the Jacobi solver of `jacobi.py` run over F_{q^2}.
"""

from __future__ import annotations

import random
from collections.abc import Sequence

import kickmix as km  # type: ignore[import-not-found,unused-ignore]

from dqi_gen import jacobi


class Cayley:
    def __init__(self, h: int, n: int, theta: int | None = None):
        self.h, self.n, self.N = h, n, n - 1
        self.q = 1 << h
        self.G = km.GF2Field(2 * h)
        G, q = self.G, self.q
        self.sub = [a for a in range(1, 1 << (2 * h)) if G.pow(a, q) == a]
        self.theta = (
            theta if theta is not None else next(a for a in range(2, 1 << (2 * h)) if G.pow(a, q) != a)
        )
        self.thetabar = G.pow(self.theta, q)
        # matrix[i][m] = [z^m] (z + theta)^i (z + thetabar)^(N-i)
        self.matrix = [self._coeffs(i) for i in range(n)]

    def _coeffs(self, i: int) -> list[int]:
        G = self.G
        poly = [1]
        for factor in [self.theta] * i + [self.thetabar] * (self.N - i):
            nxt = [0] * (len(poly) + 1)
            for k, c in enumerate(poly):
                nxt[k + 1] ^= c
                nxt[k] ^= G.mul(c, factor)
            poly = nxt
        return poly + [0] * (self.n - len(poly))

    def moments(self, s: Sequence[int]) -> list[int]:
        G = self.G
        out = []
        for row in self.matrix:
            acc = 0
            for c, sm in zip(row, s, strict=False):
                if c and sm:
                    acc ^= G.mul(c, sm)
            out.append(acc)
        return out

    def conj_symmetric(self, t: Sequence[int]) -> bool:
        return all(t[self.N - i] == self.G.pow(t[i], self.q) for i in range(self.n))

    def decode(self, s: Sequence[int], t: int) -> tuple[dict[int, int] | None, str]:
        """Error word `x -> w` from syndromes `s`, or `(None, reason)` when the recursion degenerates."""
        G = self.G
        tm = self.moments(s)
        sol = jacobi.solve(G, tm, t)
        if not sol.erase_ok:
            return None, "p_k(0)=0"
        w = sol.stopped_at
        if w >= t:
            w = t
        # roots of p_w over F_{q^2}: u on the unit circle; x = (theta + u thetabar) / (1 + u)
        p = sol.p
        roots = [u for u in range(1, 1 << (2 * self.h)) if jacobi.poly_eval(G, p, u) == 0]
        if len(roots) != w or any(u == 1 for u in roots):
            return None, "roots"
        out: dict[int, int] = {}
        for u in roots:
            x = G.mul(self.theta ^ G.mul(u, self.thetabar), G.invert(1 ^ u))
            big = jacobi.gauss_weight(G, sol, u)
            wt = G.mul(big, G.invert(G.pow(x ^ self.thetabar, self.N)))
            out[x] = wt
        return out, "ok"

    def random_word(self, w: int, rng: random.Random) -> dict[int, int]:
        xs = rng.sample(self.sub, w)
        return {x: rng.choice(self.sub) for x in xs}

    def syndromes(self, word: dict[int, int]) -> list[int]:
        G = self.G
        s = [0] * self.n
        for x, wt in word.items():
            p = 1
            for m in range(self.n):
                s[m] ^= G.mul(wt, p)
                p = G.mul(p, x)
        return s


def plain_failure(h: int, n: int, w: int, shots: int, rng: random.Random) -> float:
    """Failure rate of the plain F_q Lanczos recursion (premature `h_k = 0` or `p_k(0) = 0`) at weight `w`."""
    G = km.GF2Field(h)
    sub = list(range(1, 1 << h))
    bad = 0
    for _ in range(shots):
        xs = rng.sample(sub, w)
        s = [0] * n
        for x in xs:
            wt = rng.choice(sub)
            p = 1
            for m in range(n):
                s[m] ^= G.mul(wt, p)
                p = G.mul(p, x)
        sol = jacobi.solve(G, s, n // 2)
        if sol.stopped_at != w or not sol.erase_ok:
            bad += 1
    return bad / shots


def cayley_failure(h: int, n: int, w: int, shots: int, rng: random.Random) -> tuple[float, float]:
    """(failure rate, wrong-answer rate) of the Cayley recursion at weight `w`."""
    cy = Cayley(h, n)
    fail = wrong = 0
    for _ in range(shots):
        word = cy.random_word(w, rng)
        got, why = cy.decode(cy.syndromes(word), n // 2)
        if got is None:
            fail += 1
        elif got != word:
            wrong += 1
    return fail / shots, wrong / shots


def main() -> None:
    rng = random.Random(7)
    for h, n, w, shots in ((4, 8, 4, 3000), (5, 10, 5, 3000), (6, 10, 5, 2000)):
        pf = plain_failure(h, n, w, shots, rng)
        cf, cw = cayley_failure(h, n, w, shots, rng)
        print(f"q={1 << h} n={n} w={w}: plain Lanczos fails {pf:.4f}; Cayley fails {cf:.4f}, wrong {cw:.4f}")


if __name__ == "__main__":
    main()
