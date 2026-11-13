"""Post-processing of a fitted dfthcsos factorization (QCC-16): Givens-tree words and weight rotations.

All of it is ours, written from the verifier's decoding rule (``SCORING_README.md``): a row is decoded by
applying ``(p, c)`` rotations of angle ``theta_t = pi * word_t / 2**(brot - 1)`` to ``e_0``, so the encoder is
the spherical-coordinate decomposition of the vector along the tree, taken from the last edge to the first.
"""

from __future__ import annotations

import numpy as np
from scipy.linalg import expm  # type: ignore[import-untyped,unused-ignore]


def path_tree(n: int = 76) -> np.ndarray:
    return np.array([[i, i + 1] for i in range(n - 1)], dtype=np.int64)


def balanced_tree(n: int = 76) -> np.ndarray:
    """Heap-shaped binary tree rooted at 0, parents listed before children (depth about log2 n)."""
    return np.array([[(c - 1) // 2, c] for c in range(1, n)], dtype=np.int64)


def decode(words: np.ndarray, edges: np.ndarray, brot: int) -> np.ndarray:
    """Unit vectors from integer words ``(m, n-1)``, as the verifier does."""
    ang = np.pi * np.asarray(words, dtype=np.float64) / (1 << (brot - 1))
    m, n1 = ang.shape
    v = np.zeros((m, n1 + 1))
    v[:, 0] = 1.0
    for t, (p, c) in enumerate(edges):
        pv, cv = v[:, p].copy(), v[:, c].copy()
        co, si = np.cos(ang[:, t]), np.sin(ang[:, t])
        v[:, p] = co * pv - si * cv
        v[:, c] = si * pv + co * cv
    return v


def encode(u: np.ndarray, edges: np.ndarray, brot: int, half: bool = False) -> np.ndarray:
    """Nearest integer words ``(m, n-1)`` in ``[0, 2**brot)`` whose decoding approximates ``u``.

    ``half``: angles in the half circle (see ``angles_of``), so bit ``brot - 1`` of every word equals bit
    ``brot - 2`` and the decoded vector may be ``-u`` (the objective only sees ``u u^T``).
    """
    ang = angles_of(u, edges, brot, half)
    w = np.rint(ang).astype(np.int64)
    if half:
        w = np.clip(w, -(1 << (brot - 2)), (1 << (brot - 2)) - 1)
    return np.asarray(w % (1 << brot))


def _l1_obj(w: np.ndarray, eps: float) -> tuple[float, np.ndarray]:
    """``sum_c (sum_b phi(w_bc))^2`` with the smooth abs ``phi``, and its gradient in ``w`` (B x C)."""
    phi = np.sqrt(w * w + eps * eps)
    a = phi.sum(axis=0)
    return float(np.sum(a * a)), 2 * a[None, :] * (w / phi)


def rotate_min_l1(
    w: np.ndarray, iters: int = 200, eps: float = 1e-4, seed: int = 0
) -> tuple[np.ndarray, np.ndarray]:
    """Orthogonal ``O`` (C x C) with ``w @ O`` of small column one-norms, for one ``rho`` (``w`` is B x C).

    The sum over ``c`` of ``X_c (x) X_c`` is invariant under rotating ``c``, so this changes ``Lambda``
    and nothing else. Riemannian gradient descent with an exponential retraction and a backtracking step.
    """
    c = w.shape[1]
    o = np.eye(c)
    f, g = _l1_obj(w @ o, eps)
    step = 0.05
    for _ in range(iters):
        grad = w.T @ g
        om = grad @ o.T - o @ grad.T
        nrm = np.linalg.norm(om)
        if nrm < 1e-12:
            break
        while step > 1e-14:
            o2 = expm(-step * om / nrm) @ o
            f2, g2 = _l1_obj(w @ o2, eps)
            if f2 < f:
                o, f, g = o2, f2, g2
                step *= 1.5
                break
            step *= 0.5
        else:
            break
    return w @ o, o


def angles_of(u: np.ndarray, edges: np.ndarray, brot: int, half: bool = False) -> np.ndarray:
    """Real-valued angles in word units: ``encode`` before rounding.

    ``half`` keeps every angle in ``[-pi/2, pi/2]``: a rotation by ``theta + pi`` negates both outputs, so
    a negative parent amplitude is carried up the tree with its sign instead of rotating past ``pi / 2``. Idea
    seen in public Kaggle notebook text (pi-gauge, bit7 == bit6 domain; docs/PROVENANCE.md), written fresh.
    """
    v = np.array(u, dtype=np.float64)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    ang = np.zeros((v.shape[0], len(edges)))
    for t in range(len(edges) - 1, -1, -1):
        p, c = edges[t]
        if half:
            sgn = np.where(v[:, p] < 0, -1.0, 1.0)
            a = np.arctan2(sgn * v[:, c], np.abs(v[:, p]))
            # an angle that would round to +pi/2 is not in the half grid [-pi/2, pi/2): use -pi/2 and carry
            # the sign (R(theta - pi) = -R(theta)), so every word keeps bit brot-1 == bit brot-2
            edge = a > (np.pi / 2) * (1 - 0.5 / (1 << (brot - 2)))
            a = np.where(edge, a - np.pi, a)
            sgn = np.where(edge, -sgn, sgn)
            ang[:, t] = a
            v[:, p] = sgn * np.hypot(v[:, p], v[:, c])
        else:
            ang[:, t] = np.arctan2(v[:, c], v[:, p])
            v[:, p] = np.hypot(v[:, p], v[:, c])
        v[:, c] = 0.0
    return np.asarray(ang / np.pi * (1 << (brot - 1)))


def decode_real(theta: np.ndarray, edges: np.ndarray, brot: int) -> tuple[np.ndarray, list[np.ndarray]]:
    """Decode real word-unit angles; also returns the rotated pair after each step for the backward pass."""
    ang = np.pi * theta / (1 << (brot - 1))
    m, n1 = ang.shape
    v = np.zeros((m, n1 + 1))
    v[:, 0] = 1.0
    saved = []
    for t, (p, c) in enumerate(edges):
        pv, cv = v[:, p].copy(), v[:, c].copy()
        co, si = np.cos(ang[:, t]), np.sin(ang[:, t])
        v[:, p] = co * pv - si * cv
        v[:, c] = si * pv + co * cv
        saved.append(np.stack([v[:, p], v[:, c]]))
    return v, saved


def decode_backward(
    theta: np.ndarray, edges: np.ndarray, brot: int, saved: list[np.ndarray], gu: np.ndarray
) -> np.ndarray:
    """Gradient w.r.t. ``theta`` (word units) of a loss with gradient ``gu`` w.r.t. the decoded vectors."""
    ang = np.pi * theta / (1 << (brot - 1))
    g = np.array(gu, dtype=np.float64)
    gth = np.zeros_like(theta)
    for t in range(len(edges) - 1, -1, -1):
        p, c = edges[t]
        pn, cn = saved[t]
        gp, gc = g[:, p].copy(), g[:, c].copy()
        gth[:, t] = -gp * cn + gc * pn
        co, si = np.cos(ang[:, t]), np.sin(ang[:, t])
        g[:, p] = gp * co + gc * si
        g[:, c] = -gp * si + gc * co
    return np.asarray(gth * np.pi / (1 << (brot - 1)))
