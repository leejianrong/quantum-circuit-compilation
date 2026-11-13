"""Joint coefficient search with wide moves on the worst segments (QCC-13).

`model.fit_tables` rounds the minimax coefficients and polishes every segment by `+-radius` ulps of
`c_1 .. c_d`. The gate is the worst segment, and for narrow words a few segments carry the excess error,
so here the segments above `target` are searched over a box far larger than the polish radius (all
`(c_1, c_2)` offsets in `[-r1, r1] x [-r2, r2]`, `c_0` recentred for each), until no segment improves. The
result is the input for the angle LP of `angles.py`. Measured limit: the lattice of `(c_1, c_2)` bounds the
error (each bit off `c_1` or `c_2` costs about half a bit), see docs/experiments/invsqrt-onepass.md.
"""

import numpy as np

from invsqrt_gen.model import Tables, _recentre, _seg_err, exact_full, reachable_matrix
from invsqrt_gen.params import Params


def segment_errors(p: Params, t: Tables) -> np.ndarray:
    """Worst reachable relative error of the phased word per segment."""
    r = np.arange(1 << p.rwidth, dtype=np.int64)
    return _seg_err(p, t.coef, r, exact_full(p), reachable_matrix(p))


def refine(
    p: Params,
    t: Tables,
    target: float,
    box: tuple[int, ...] = (10, 3),
    rounds: int = 6,
    worst: int = 48,
) -> Tables:
    """Wide-box search on the segments whose error exceeds `target`; returns improved tables (a copy)."""
    assert p.degree == len(box) == 2, "the box has one radius per coefficient c_1 .. c_d"
    r = np.arange(1 << p.rwidth, dtype=np.int64)
    exact, valid = exact_full(p), reachable_matrix(p)
    coef = [c.copy() for c in t.coef]
    err = _seg_err(p, coef, r, exact, valid)
    offsets = [(a, b) for a in range(-box[0], box[0] + 1) for b in range(-box[1], box[1] + 1) if a or b]
    for _ in range(rounds):
        idx = np.argsort(-err)[:worst]
        idx = idx[err[idx] > target]
        if not len(idx):
            break
        sub = [c[idx].copy() for c in coef]
        ex, va = exact[idx], valid[idx]
        best = err[idx].copy()
        improved = False
        for d1, d2 in offsets:
            trial = [c.copy() for c in sub]
            trial[1] += d1
            trial[2] += d2
            _recentre(p, trial, r, ex, rounds=1, valid=va)
            e = _seg_err(p, trial, r, ex, va)
            better = e < best
            if better.any():
                improved = True
                for j in range(3):
                    sub[j] = np.where(better, trial[j], sub[j])
                best = np.where(better, e, best)
        for j in range(3):
            coef[j][idx] = sub[j]
        err[idx] = best
        if not improved:
            break
    return Tables(p, coef)
