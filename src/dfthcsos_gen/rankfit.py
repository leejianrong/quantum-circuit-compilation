"""Round angles to words whose bit planes have low GF(2) rank (the cheap tables of ``bilinear``).

``x`` holds the continuous angles in word units (``theta / pi * 2**(brot - 1)``), shape ``(A, T)``. The
words loaded are XOR deltas along the batches (see ``loader.angle_deltas``), so the planes whose rank costs
Toffolis are the delta planes. Each plane is an ``H x L`` bit matrix; we want its centered rank below a
budget while the words stay close to ``x``.

Heuristic (alternating minimisation over GF(2), soft decisions): for a plane ``Q ~ A B`` with ``A`` of
``H x r`` and ``B`` of ``r x L``, fix ``B`` and decode every row of ``A`` by enumerating its ``2**r``
candidates against the per-entry flip costs, then the same with the roles swapped. The flip cost of an
entry is the increase in squared angle error when that bit of the word flips. Planes are visited from the
high bit down so that carries are already decided.
"""

from __future__ import annotations

import numpy as np

from .bilinear import center, geometry


def flip_cost(x: np.ndarray, words: np.ndarray, bit: int, brot: int) -> np.ndarray:
    """Increase of ``(word - x)^2`` (angles are periodic mod ``2**brot``) when ``bit`` of the word flips."""
    period = 1 << brot
    cur = words.astype(np.float64)
    step = np.where((words >> bit) & 1, -(1 << bit), 1 << bit)
    new = cur + step

    def err(v: np.ndarray) -> np.ndarray:
        d = (v - x + period / 2) % period - period / 2
        return np.asarray(d * d)

    return err(new) - err(cur)


def _decode_rows(q: np.ndarray, b: np.ndarray, cost: np.ndarray) -> np.ndarray:
    """For each row of ``q`` the coefficients ``a`` (``r`` bits) minimising the flip cost of ``a B != q``."""
    r = b.shape[0]
    combos = ((np.arange(1 << r)[:, None] >> np.arange(r)[None, :]) & 1).astype(bool)  # (2^r, r)
    recon = (combos.astype(np.uint8) @ b.astype(np.uint8)) % 2  # (2^r, L)
    recon = recon.astype(bool)
    out = np.zeros((q.shape[0], r), dtype=bool)
    for i in range(q.shape[0]):
        bad = recon != q[i][None, :]
        out[i] = combos[np.argmin((bad * cost[i][None, :]).sum(axis=1))]
    return out


def low_rank_plane(plane: np.ndarray, cost: np.ndarray, rank: int, sweeps: int = 6, seed: int = 0) -> np.ndarray:
    """Plane of centered rank at most ``rank`` close to ``plane`` in flip-cost-weighted Hamming distance.

    ``cost`` is nonnegative with the same shape; zero cost marks a don't-care entry. The ``F(h)``/``G(l)``
    parts of ``plane`` are kept (they are free in the loader), only the centered part is approximated.
    """
    p = np.asarray(plane, dtype=bool)
    q = center(p)
    h, ll = p.shape
    if rank >= min(h, ll) - 1:
        return p
    rng = np.random.default_rng(seed)
    # start from the best rank-r factor found by truncating a random-order elimination of q
    b = np.zeros((rank, ll), dtype=bool)
    b[:] = q[rng.choice(h, size=rank, replace=False)]
    best, best_val = q, np.inf
    for _ in range(sweeps):
        a = _decode_rows(q, b, cost)
        # decode columns: transpose roles
        b = _decode_rows(q.T, a.T, cost.T).T
        approx = (a.astype(np.uint8) @ b.astype(np.uint8)) % 2 == 1
        val = float((cost * (approx != q)).sum())
        if val < best_val - 1e-12:
            best, best_val = approx, val
        else:
            break
    # reinstate F and G: the centered matrix is zero in row/col 0, so rebuild the plane around it
    out = best.copy()
    out[0, :] = False
    out[:, 0] = False
    return np.asarray(out ^ p[:, :1] ^ p[:1, :] ^ p[:1, :1])


def round_to_budget(x: np.ndarray, brot: int, lb: int, ranks: np.ndarray) -> np.ndarray:
    """Words for ``x`` (``(A, T)``) whose planes respect per-plane rank budgets (not yet delta-aware).

    ``ranks[bit]`` is the centered-rank budget of bit ``bit`` for every word column. Nearest rounding
    first, then planes are projected from the top bit down.
    """
    a, t = x.shape
    h, ll = geometry(a, lb)
    period = 1 << brot
    words = np.rint(x).astype(np.int64) % period
    for bit in reversed(range(brot)):
        if ranks[bit] >= min(h, ll) - 1:
            continue
        cost_all = flip_cost(x, words, bit, brot)
        for col in range(t):
            pl = np.zeros(h * ll, dtype=bool)
            pl[:a] = (words[:, col] >> bit) & 1
            cost = np.zeros(h * ll)
            cost[:a] = np.maximum(cost_all[:, col], 1e-9)
            new = low_rank_plane(pl.reshape(h, ll), cost.reshape(h, ll), int(ranks[bit]))
            nb = new.reshape(-1)[:a]
            words[:, col] = (words[:, col] & ~(1 << bit)) | (nb.astype(np.int64) << bit)
    return words
