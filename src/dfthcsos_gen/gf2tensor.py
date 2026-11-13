"""Low-rank decomposition of a GF(2) table tensor by a flip-graph random walk (QCC-16, stage 2).

The shared-product loader (``shared.py``) pays one Toffoli per rank-one term of the centered tensor
``Tc[o, h, l] = sum_t v_t[o] alpha_t[h] beta_t[l]``, so the cost of an arbitrary table is its GF(2) tensor
rank, which we reduce by search. Method: the flip graph of Kauers and Moosbauer (arXiv:2212.01175, "Flip
graphs for matrix multiplication") with the plus transitions of Arai et al. (arXiv:2312.08793),
applied to our tensor, written fresh. Terms are triples of python ints (bit masks over the three modes).

* flip: two terms sharing a factor ``a`` in one mode, ``a x b x c + a x b' x c'`` becomes
  ``a x (b + b') x c + a x b' x (c + c')``; the sum is unchanged.
* reduction: a term with a zero factor is dropped; two terms sharing two factors merge into one.
* plus: when the walk stalls, ``a x b x c + a' x b' x c'`` is rewritten with three terms
  ``(a + a') x b x c + a' x b x c + a' x b' x c'`` to open new flips (rank + 1).
"""

from __future__ import annotations

import random

import numpy as np

Term = tuple[int, int, int]


def _row_ints(mat: np.ndarray) -> list[int]:
    return [int("".join("1" if x else "0" for x in row[::-1]), 2) if row.size else 0 for row in mat]


def center(table: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``table`` of shape ``(nout, H, L)`` as ``(F, G, Tc)`` with ``T = F[o,h] + G[o,l] + Tc[o,h,l]``."""
    t = np.asarray(table, dtype=np.uint8)
    f = t[:, :, 0].copy()
    g = (t[:, 0, :] ^ t[:, :1, 0]).copy()
    tc = t ^ f[:, :, None] ^ g[:, None, :]
    return f, g, tc


def initial_terms(tc: np.ndarray) -> list[Term]:
    """Slice-by-slice decomposition: for each ``l`` a GF(2) row-space factorization of ``Tc[:, :, l]``."""
    nout, _, ll = tc.shape
    terms: list[Term] = []
    for lq in range(ll):
        basis: list[int] = []  # echelon vectors over h, in creation order
        use: list[int] = []  # use[k] = bit mask over o of the rows that contain basis[k]
        for o, r in enumerate(_row_ints(tc[:, :, lq])):
            for k, vec in enumerate(basis):
                if r ^ vec < r:
                    r ^= vec
                    use[k] ^= 1 << o
            if r:
                basis.append(r)
                use.append(1 << o)
        terms += [(u, vec, 1 << lq) for u, vec in zip(use, basis, strict=True) if u]
    return terms


def plane_terms(tc: np.ndarray) -> list[Term]:
    """One decomposition per output bit (``v`` a unit vector): the per-plane loader as a starting point."""
    nout, _, _ = tc.shape
    terms: list[Term] = []
    for o in range(nout):
        basis: list[int] = []
        use: list[int] = []
        for hq, r in enumerate(_row_ints(tc[o])):  # rows over l
            for k, vec in enumerate(basis):
                if r ^ vec < r:
                    r ^= vec
                    use[k] ^= 1 << hq
            if r:
                basis.append(r)
                use.append(1 << hq)
        terms += [(1 << o, u, vec) for u, vec in zip(use, basis, strict=True) if u]
    return terms


def expand(terms: list[Term], nout: int, h: int, ll: int) -> np.ndarray:
    out = np.zeros((nout, h, ll), dtype=np.uint8)
    for v, a, b in terms:
        vo = np.array([(v >> i) & 1 for i in range(nout)], dtype=np.uint8)
        ah = np.array([(a >> i) & 1 for i in range(h)], dtype=np.uint8)
        bl = np.array([(b >> i) & 1 for i in range(ll)], dtype=np.uint8)
        out ^= vo[:, None, None] & ah[None, :, None] & bl[None, None, :]
    return out


class FlipWalk:
    """Random walk over decompositions of a fixed tensor; ``terms`` is always an exact decomposition."""

    def __init__(self, terms: list[Term], seed: int = 0) -> None:
        self.rng = random.Random(seed)
        self.slots: list[Term | None] = []
        self.free: list[int] = []
        self.by: list[dict[int, set[int]]] = [{}, {}, {}]  # mode -> factor -> ids
        self.alive = 0
        self.vcount: dict[int, int] = {}
        self.cost = 0  # sum over output vectors of ceil(terms / 2): Toffolis with the pairing trick
        self.journal: list[tuple[str, int, Term]] = []
        for t in terms:
            self._add(t)
        self.journal.clear()

    def _add(self, t: Term) -> None:
        # merge with any term sharing two factors, drop zero terms
        while True:
            if 0 in t:
                return
            hit = None
            for m in range(3):
                for j in self.by[m].get(t[m], ()):
                    u = self.slots[j]
                    assert u is not None
                    if sum(u[k] == t[k] for k in range(3)) >= 2:
                        hit = j
                        break
                if hit is not None:
                    break
            if hit is None:
                break
            u = self.slots[hit]
            assert u is not None
            k = next(k for k in range(3) if u[k] != t[k]) if u != t else 0
            self._remove(hit)
            if u == t:
                return  # identical terms cancel
            merged = list(t)
            merged[k] = u[k] ^ t[k]
            t = (merged[0], merged[1], merged[2])
        i = self.free.pop() if self.free else len(self.slots)
        if i == len(self.slots):
            self.slots.append(None)
        self._put(i, t)
        self.journal.append(("a", i, t))

    def _put(self, i: int, t: Term) -> None:
        self.slots[i] = t
        for m in range(3):
            self.by[m].setdefault(t[m], set()).add(i)
        self.alive += 1
        c = self.vcount.get(t[0], 0)
        self.vcount[t[0]] = c + 1
        self.cost += (c + 2) // 2 - (c + 1) // 2

    def _del(self, i: int) -> Term:
        t = self.slots[i]
        assert t is not None
        for m in range(3):
            s = self.by[m][t[m]]
            s.discard(i)
            if not s:
                del self.by[m][t[m]]
        self.slots[i] = None
        self.alive -= 1
        c = self.vcount[t[0]]
        self.vcount[t[0]] = c - 1
        self.cost += (c - 1 + 1) // 2 - (c + 1) // 2
        return t

    def _remove(self, i: int) -> Term:
        t = self._del(i)
        self.free.append(i)
        self.journal.append(("r", i, t))
        return t

    def undo(self) -> None:
        for op, i, t in reversed(self.journal):
            if op == "a":
                self._del(i)
                self.free.append(i)
            else:
                self.free.remove(i)
                self._put(i, t)
        self.journal.clear()

    @property
    def terms(self) -> list[Term]:
        return [t for t in self.slots if t is not None]

    def _random_alive(self) -> int:
        while True:
            i = self.rng.randrange(len(self.slots))
            if self.slots[i] is not None:
                return i

    def flip(self) -> bool:
        i = self._random_alive()
        ti = self.slots[i]
        assert ti is not None
        m = self.rng.randrange(3)
        bucket = self.by[m][ti[m]]
        if len(bucket) < 2:
            return False
        j = self.rng.choice(tuple(bucket - {i}))
        tj = self.slots[j]
        assert tj is not None
        o1, o2 = [k for k in range(3) if k != m]
        if self.rng.random() < 0.5:
            o1, o2 = o2, o1
        # ti = a x b x c, tj = a x b' x c'  ->  a x (b+b') x c, a x b' x (c+c')
        ni, nj = list(ti), list(tj)
        ni[o1] = ti[o1] ^ tj[o1]
        nj[o2] = tj[o2] ^ ti[o2]
        self._remove(i)
        self._remove(j)
        self._add((ni[0], ni[1], ni[2]))
        self._add((nj[0], nj[1], nj[2]))
        return True

    def plus(self) -> None:
        i, j = self._random_alive(), self._random_alive()
        if i == j:
            return
        ti, tj = self.slots[i], self.slots[j]
        assert ti is not None and ti is not None and tj is not None
        m = self.rng.randrange(3)
        self._remove(i)
        self._remove(j)
        a = list(ti)
        a[m] = ti[m] ^ tj[m]
        b = list(ti)
        b[m] = tj[m]
        self._add((a[0], a[1], a[2]))
        self._add((b[0], b[1], b[2]))
        self._add(tj)

    def run(self, steps: int, patience: int = 20000) -> list[Term]:
        best = self.terms
        since = 0
        for _ in range(steps):
            before = self.alive
            self.flip()
            if self.alive < len(best):
                best = self.terms
                since = 0
            elif self.alive >= before:
                since += 1
            if since > patience:
                self.plus()
                since = 0
        return best


def anneal(walk: FlipWalk, steps: int, temp: float = 0.3) -> list[Term]:
    """Random flips accepted when the paired Toffoli cost does not rise (or by Metropolis at ``temp``)."""
    best_cost, best = walk.cost, walk.terms
    for _ in range(steps):
        before = walk.cost
        walk.journal.clear()
        if not walk.flip():
            continue
        d = walk.cost - before
        if d > 0 and walk.rng.random() >= 2.718281828 ** (-d / temp):
            walk.undo()
            continue
        if walk.cost < best_cost:
            best_cost, best = walk.cost, walk.terms
    return best


def pair_cost(terms: list[Term]) -> int:
    """Toffolis if two terms with the same output vector share one (see ``shared.py``)."""
    count: dict[int, int] = {}
    for v, _, _ in terms:
        count[v] = count.get(v, 0) + 1
    return sum((m + 1) // 2 for m in count.values())
