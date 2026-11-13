"""Compact-group seed for the DF-THC fit (QCC-16, stage 2).

Idea learned from public notebook text (marculera, "DF-THC 10x: compact groups from the Hamiltonian",
logged in docs/PROVENANCE.md): a table fits better when each group of shared vectors lives on few
orbitals. The seed is built from the target alone, in four steps that we wrote from their description:
pivoted Cholesky leaves of the packed target, balanced k-means of the leaves' orbital profiles into
``R`` groups, simultaneous orthogonal matching pursuit of ``B`` shared vectors per group from the
leaves' own eigenvectors, then least-squares weights. No table, weight or code of theirs is used.
"""

from __future__ import annotations

import numpy as np

from dfthcsos_gen.fit import Objective


def pivoted_cholesky(m: np.ndarray, k: int) -> np.ndarray:
    """``k`` leaves ``y_l`` (rows) with ``sum_l y_l y_l^T`` the greedy rank-``k`` approximation of ``m``."""
    d = np.diag(m).copy()
    leaves = np.zeros((k, m.shape[0]))
    for i in range(k):
        j = int(np.argmax(d))
        if d[j] <= 1e-14:
            return leaves[:i]
        col = m[:, j] - leaves[:i].T @ leaves[:i, j]
        leaves[i] = col / np.sqrt(d[j])
        d -= leaves[i] ** 2
        d[d < 0] = 0.0
    return leaves


def balanced_kmeans(x: np.ndarray, groups: int, rng: np.random.Generator, iters: int = 30) -> np.ndarray:
    """Cluster rows of ``x`` into ``groups`` equal-size clusters (greedy assignment by distance gap)."""
    n = x.shape[0]
    size = n // groups
    cen = x[rng.choice(n, groups, replace=False)]
    lab = np.zeros(n, dtype=int)
    for _ in range(iters):
        dist = ((x[:, None, :] - cen[None]) ** 2).sum(-1)
        cap = np.full(groups, size)
        cap[: n - size * groups] += 1
        new = np.full(n, -1)
        order = np.argsort(dist.min(1) - np.sort(dist, 1)[:, 1])  # most decided first
        for i in order:
            for g in np.argsort(dist[i]):
                if cap[g] > 0:
                    new[i] = g
                    cap[g] -= 1
                    break
        if np.array_equal(new, lab):
            break
        lab = new
        cen = np.stack([x[lab == g].mean(0) for g in range(groups)])
    return lab


def group_omp(mats: np.ndarray, b: int, cand: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Pick ``b`` unit vectors from ``cand`` (rows) that jointly fit ``mats`` (``c, n, n``) as
    ``sum_b a_lb u_b u_b^T``; returns the vectors and the least-squares coefficients ``(b, c)``."""
    res = mats.copy()
    chosen: list[int] = []
    for _ in range(b):
        q = np.einsum("kp,lpq,kq->kl", cand, res, cand, optimize=True)
        score = (q * q).sum(1)
        score[chosen] = -1.0
        chosen.append(int(np.argmax(score)))
        u = cand[chosen]
        h = (u @ u.T) ** 2
        rhs = np.einsum("bp,lpq,bq->bl", u, mats, u, optimize=True)
        coef = np.linalg.solve(h + 1e-12 * np.eye(len(chosen)), rhs)
        res = mats - np.einsum("bl,bp,bq->lpq", coef, u, u, optimize=True)
    return cand[chosen], coef


def compact_seed(
    obj: Objective, shape: tuple[int, int, int], seed: int = 0, cand_per_leaf: int = 12
) -> tuple[np.ndarray, np.ndarray]:
    """Vectors ``(R*B, n)`` and weights ``(R, B, C)`` for :class:`Objective` from the target alone."""
    r, b, c = shape
    n = obj.n
    rng = np.random.default_rng(seed)
    # target as a matrix on the packed space: tsym is already M x M
    leaves = pivoted_cholesky(obj.tsym, r * c)
    mats = obj.unpack(leaves)  # (R*C, n, n), sum_l X_l (x) X_l ~ T
    prof = np.sqrt((mats**2).sum(2))
    prof /= np.linalg.norm(prof, axis=1, keepdims=True)
    lab = balanced_kmeans(prof, r, rng)
    v = np.zeros((r * b, n))
    w = np.zeros((r, b, c))
    for g in range(r):
        gm = mats[lab == g]
        evals, evecs = np.linalg.eigh(gm)
        cand = []
        for li in range(gm.shape[0]):
            top = np.argsort(-np.abs(evals[li]))[:cand_per_leaf]
            cand.append(evecs[li][:, top].T)
        u, coef = group_omp(gm, b, np.concatenate(cand))
        v[g * b : (g + 1) * b] = u
        w[g, :, : coef.shape[1]] = coef
    return v, w


def sparse_seed(
    obj: Objective, shape: tuple[int, int, int], seed: int = 0, k: int = 5, group_orbitals: int = 20
) -> tuple[np.ndarray, np.ndarray]:
    """Random LOCAL start: every vector lives on ``k`` of its group's ``group_orbitals`` random orbitals.

    Public frontier tables have vectors of participation ratio about 4 (docs/experiments/dfthcsos-stage2.md), so
    the fit starts from that kind of support instead of dense Gaussian vectors. Weights are scaled so that the
    objective is minimal along the ray, as in ``run_fit.init_point``.
    """
    r, b, c = shape
    rng = np.random.default_rng(seed)
    v = np.zeros((r * b, obj.n))
    for g in range(r):
        sub = rng.choice(obj.n, group_orbitals, replace=False)
        for i in range(b):
            v[g * b + i, rng.choice(sub, k, replace=False)] = rng.normal(size=k)
    v += 1e-3 * rng.normal(size=v.shape)
    w = rng.normal(size=(r, b, c))
    f1 = obj.value_grad(v, w, need_v=False)[0]
    fh = obj.value_grad(v, 0.5 * w, need_v=False)[0]
    a, bq = np.linalg.solve([[-0.5, 0.0625], [-2.0, 1.0]], [fh - obj.t2, f1 - obj.t2])
    return v, w * np.sqrt(max(a / bq, 1e-12))
