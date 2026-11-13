"""Linear matroid parity over GF(2) by the randomized alternating-matrix method (QCC-16, stage 2).

Problem: given pairs ``(a_t, b_t)`` of vectors in ``GF(2)^d``, find the largest set of pairs whose
vectors are linearly independent together (a product that serves two rank-one terms at once is such a
pair). Lovasz: with random field weights ``x_t`` the matrix ``Q = sum_t x_t (a_t b_t^T + b_t a_t^T)``
over a large field has rank ``2 nu`` with high probability, ``nu`` the optimum. When ``Q`` is nonsingular
a pair is in some perfect matching iff ``a^T Q^{-1} b != 0``, and the pairs can be extracted one at a
time by contracting them (change of coordinates that sends ``a, b`` to unit vectors, delete those
coordinates, Schur update of the inverse).

Method seen in the Apache-2.0 builder of syed3000 (``compiler/extract_matching.py`` and
``parity_recover.py``, Copyright 2026 Syed Asad Ali; see THIRD_PARTY_NOTICES.md); the code below is our
own rewrite of that algorithm with our own data layout. GF(2^8) uses the polynomial 0x11b.
"""

from __future__ import annotations

import random

import numpy as np


def _mul_table() -> np.ndarray:
    a = np.broadcast_to(np.arange(256, dtype=np.uint16)[:, None], (256, 256)).copy()
    b = np.broadcast_to(np.arange(256, dtype=np.uint16)[None, :], (256, 256)).copy()
    out = np.zeros((256, 256), dtype=np.uint16)
    for _ in range(8):
        out ^= np.where(b & 1, a, np.uint16(0))
        a <<= 1
        a ^= np.where(a & 256, np.uint16(0x11B), np.uint16(0))
        b >>= 1
    return out.astype(np.uint8)


MUL = _mul_table()
INV = np.zeros(256, dtype=np.uint8)
for _i in range(1, 256):
    INV[_i] = int(np.nonzero(MUL[_i] == 1)[0][0])


def bits(x: int) -> list[int]:
    out = []
    while x:
        low = x & -x
        out.append(low.bit_length() - 1)
        x ^= low
    return out


def gf2_basis(vectors: list[int]) -> dict[int, int]:
    """Echelon basis (leading bit -> vector) of integer bit vectors."""
    d: dict[int, int] = {}
    for x in vectors:
        while x:
            j = x.bit_length() - 1
            if j in d:
                x ^= d[j]
            else:
                d[j] = x
                break
    return d


def gf2_nullspace(rows: list[int], n: int) -> list[int]:
    """Basis of ``{v in GF(2)^n : <row, v> = 0 for every row}``."""
    d = gf2_basis(rows)
    out = []
    for free in range(n):
        if free in d:
            continue
        x = 1 << free
        for p in sorted(d):
            if (d[p] & x).bit_count() & 1:
                x ^= 1 << p
        out.append(x)
    return out


def rank_gf256(mat: np.ndarray) -> int:
    a = mat.copy()
    nr, nc = a.shape
    r = 0
    for col in range(nc):
        hit = np.nonzero(a[r:, col])[0]
        if not len(hit):
            continue
        i = r + int(hit[0])
        a[[r, i]] = a[[i, r]]
        a[r, col:] = MUL[INV[a[r, col]], a[r, col:]]
        if r + 1 < nr:
            a[r + 1 :, col:] ^= MUL[a[r + 1 :, col, None], a[r, None, col:]]
        r += 1
        if r == nr:
            break
    return r


def inverse_gf256(mat: np.ndarray) -> np.ndarray | None:
    n = len(mat)
    a = np.concatenate([mat.copy(), np.eye(n, dtype=np.uint8)], axis=1)
    for c in range(n):
        hit = np.flatnonzero(a[c:, c])
        if not len(hit):
            return None
        p = c + int(hit[0])
        a[[c, p]] = a[[p, c]]
        a[c] = MUL[INV[a[c, c]], a[c]]
        coeff = a[:, c].copy()
        coeff[c] = 0
        a ^= MUL[coeff[:, None], a[c, None, :]]
    return np.asarray(a[:, n:])


def alternating(pairs: list[tuple[int, int]], dim: int, rng: random.Random) -> np.ndarray:
    q = np.zeros((dim, dim), dtype=np.uint8)
    for a, b in pairs:
        av, bv = bits(a), bits(b)
        x = rng.randrange(1, 256)
        q[np.ix_(av, bv)] ^= x
        q[np.ix_(bv, av)] ^= x
    return q


def project(pairs: list[tuple[int, int]]) -> tuple[list[tuple[int, int]], int]:
    """Coordinates of the pair vectors in a basis of their span: ``(projected pairs, span dimension)``."""
    d = gf2_basis([v for p in pairs for v in p])
    piv = sorted(d)

    def proj(x: int) -> int:
        return sum(((x >> p) & 1) << j for j, p in enumerate(piv))

    return [(proj(a), proj(b)) for a, b in pairs], len(piv)


def parity_rank(pairs: list[tuple[int, int]], seed: int = 1) -> tuple[int, int]:
    """``(rank of Q, span dimension)`` for the pairs; a perfect matching exists when they are equal."""
    proj, dim = project(pairs)
    return rank_gf256(alternating(proj, dim, random.Random(seed))), dim


def _remove_bit(x: int, p: int) -> int:
    return (x & ((1 << p) - 1)) | ((x >> (p + 1)) << p)


def perfect_matching(pairs: list[tuple[int, int]], seed: int = 1) -> list[int] | None:
    """Indices of pairs whose vectors form a basis of the span (``dim / 2`` of them), or ``None``."""
    proj, dim = project(pairs)
    if dim % 2:
        return None
    rng = random.Random(seed)
    inv = None
    for _ in range(20):
        inv = inverse_gf256(alternating(proj, dim, rng))
        if inv is not None:
            break
    if inv is None:
        return None
    cur = [[a, b] for a, b in proj]
    chosen: list[int] = []
    n = dim
    while n:
        found = -1
        for i, (a, b) in enumerate(cur):
            if not a or not b or a == b:
                continue
            if int(np.bitwise_xor.reduce(inv[np.ix_(bits(a), bits(b))].ravel())):
                found = i
                break
        if found < 0:
            return None
        chosen.append(found)
        a, b = cur[found]
        p = (a & -a).bit_length() - 1
        for vec_mask, pivot in ((a ^ (1 << p), p),):
            _transvect(inv, cur, vec_mask, pivot)
        q = ((cur[found][1] & ~(1 << p)) & -(cur[found][1] & ~(1 << p))).bit_length() - 1
        _transvect(inv, cur, cur[found][1] ^ (1 << q), q)
        t = int(inv[p, q])
        keep = [i for i in range(n) if i not in (p, q)]
        vp, vq = inv[keep, p].copy(), inv[keep, q].copy()
        corr = MUL[INV[t], MUL[vp[:, None], vq[None, :]] ^ MUL[vq[:, None], vp[None, :]]]
        inv = inv[np.ix_(keep, keep)] ^ corr
        for ab in cur:
            for r in (max(p, q), min(p, q)):
                ab[0], ab[1] = _remove_bit(ab[0], r), _remove_bit(ab[1], r)
        n -= 2
    return chosen


def _transvect(inv: np.ndarray, cur: list[list[int]], mask: int, pivot: int) -> None:
    """Replace unit coordinate ``pivot`` by ``mask + e_pivot`` in all vectors; update ``inv`` to match."""
    ix = bits(mask)
    if not ix:
        return
    inv[pivot, :] ^= np.bitwise_xor.reduce(inv[ix, :], axis=0)
    inv[:, pivot] ^= np.bitwise_xor.reduce(inv[:, ix], axis=1)
    for ab in cur:
        if (ab[0] >> pivot) & 1:
            ab[0] ^= mask
        if (ab[1] >> pivot) & 1:
            ab[1] ^= mask
