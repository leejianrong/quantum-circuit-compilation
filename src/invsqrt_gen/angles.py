"""Tuned rotation angles: our own linear program over the reachable inputs (QCC-13).

The phase of an input is `sum_pos bits(x)[pos] * A[pos]` turns, `A[pos] = 2^(pos - F)`, `F = wy + 10`, where
`bits(x)[pos]` counts the coarse and fine word bits that the shift by `s` lands on rotation position `pos`.
Giving every position its own scale `A[pos] (1 + d[pos])` is free in the cost model (rotation cost depends on
the margin only). The verifier accepts a phase error of `2^-24 f(x)` turns with `f = 2^(s-10) Y(x)`, so we
maximise the smallest slack `f(x) 2^-24 - |error(x)|` over the reachable inputs, which both makes room for
narrower tables and lowers the rotation cost (`predict.py`).
"""

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import linprog  # type: ignore[import-untyped,unused-ignore]

from invsqrt_gen.model import MAX_X, Tables, horner_pm1_levels, normalised_inputs
from invsqrt_gen.params import FRAC, MAX_PAIRS, Params
from invsqrt_gen.split import centered_words


def positions(p: Params) -> int:
    """Number of rotation positions (`F`)."""
    return p.wy + MAX_PAIRS


def design(p: Params, t: Tables) -> tuple[NDArray[np.float32], NDArray[np.float64], NDArray[np.float64]]:
    """`(M, f, e0)` over every reachable `(x_norm, parity, s)`.

    `M[i, pos] f_i / A[pos]` counts the word bits on rotation `pos`, so `f_i * (M @ d)` is the phase change
    for relative scales `d`; `f` is the exact phase in turns and `e0` the error with the untuned angles.
    """
    k0 = p.frac[0] - p.a
    base = k0 - 2 - p.guard
    n_pos = positions(p)
    xn_all, par_all = normalised_inputs()
    cw = np.array(centered_words(p, t)[0], dtype=np.int64)  # coarse word, bit i at position base + i
    n_coarse = int(cw.max()).bit_length()
    rows, fs, e0s = [], [], []
    for s in range(MAX_PAIRS + 1):
        z = par_all + 2 * s
        x = xn_all >> z
        valid = ((xn_all & (np.left_shift(1, z) - 1)) == 0) & (x >= 1) & (x <= MAX_X)
        xn, par = xn_all[valid], par_all[valid]
        if not len(xn):
            continue
        a_idx = (par << p.a) | ((xn >> p.rwidth) & ((1 << p.a) - 1))
        r = xn & ((1 << p.rwidth) - 1)
        v0 = horner_pm1_levels(p, [c[a_idx] for c in t.coef], r, check=False)[0]
        coarse = cw[a_idx]
        fine = (v0 - (coarse << (k0 - 2))) >> p.guard  # W >> guard with W = V_0 - CW
        exact = 1.0 / np.sqrt(xn / 2.0**FRAC * 2.0 ** (1 - par))
        f = 2.0 ** (s - 10) * exact
        m = np.zeros((len(xn), n_pos), dtype=np.float32)
        total = np.zeros(len(xn))
        for word, off, width in ((fine, 0, k0 - p.guard), (coarse, base, n_coarse)):
            for i in range(width):
                bit = (word >> i) & 1
                pos = off + i + s
                if pos < n_pos:
                    m[:, pos] += bit
                    total += bit * 2.0 ** (pos - n_pos)
        rows.append((m * ((2.0 ** (np.arange(n_pos) - n_pos))[None, :] / f[:, None])).astype(np.float32))
        fs.append(f)
        e0s.append(total - f)
    return np.concatenate(rows), np.concatenate(fs), np.concatenate(e0s)


def solve(
    m: NDArray[np.float32],
    f: NDArray[np.float64],
    e0: NDArray[np.float64],
    rounds: int = 12,
    seed_rows: int = 40000,
    bound: float = 0.05,
) -> tuple[NDArray[np.float64], float, float]:
    """Cutting-plane LP: scales `d` maximising `min_i (2^-24 f_i - |e0_i + f_i (m_i . d)|)`.

    Returns `(d, slack_before, slack_after)` in turns. `bound` limits `|d|` per position.
    """
    tol = f * 2.0**-24
    before = float((tol - np.abs(e0)).min())
    n, k = m.shape
    rng = np.random.default_rng(1)
    active = set(rng.choice(n, size=min(seed_rows, n), replace=False).tolist())
    active |= set(np.argsort(tol - np.abs(e0))[:seed_rows].tolist())
    d = np.zeros(k)
    after = before
    for _ in range(rounds):
        idx = np.array(sorted(active))
        mi = m[idx].astype(np.float64) * f[idx, None]
        a_ub = np.vstack([np.hstack([mi, np.ones((len(idx), 1))]), np.hstack([-mi, np.ones((len(idx), 1))])])
        b_ub = np.concatenate([tol[idx] - e0[idx], tol[idx] + e0[idx]])
        res = linprog(
            c=np.append(np.zeros(k), -1.0),
            A_ub=a_ub * 2.0**37,
            b_ub=b_ub * 2.0**37,
            bounds=[(-bound, bound)] * k + [(None, None)],
            method="highs",
        )
        if res.status != 0:
            break
        cand = res.x[:k]
        slack = tol - np.abs(e0 + (m @ cand) * f)
        if float(slack.min()) < after:  # the sampled LP over-promised and no violator helped: keep the best
            break
        d, after = cand, float(slack.min())
        bad = np.where(slack < res.x[k] - 1e-18)[0]
        if not len(bad):
            break
        active |= set(bad[np.argsort(slack[bad])[:20000]].tolist())
    return d, before, after


def tune(p: Params, t: Tables) -> tuple[NDArray[np.float64], float, float]:
    """Per-position scales for the tables `(p, t)`: `solve` over every reachable input (2.4 million rows)."""
    m, f, e0 = design(p, t)
    return solve(m, f, e0)
