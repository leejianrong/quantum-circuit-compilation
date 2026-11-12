"""Our own DF-THC fit of the dfthcsos factorization (QCC-16, co-design).

The verifier's two-body error is ``error_2^2 = || sum_{rho c} X_rc (x) X_rc - T ||_F^2`` with
``X_rc = sum_b w[rho, b, c] u_rb u_rb^T`` and ``T`` the FCIDUMP integrals plus the fixed symmetry
shift. Everything is a Gram-matrix expression in the unit vectors ``u``:

    error_2^2 = |T|^2 - 2 sum_{rho c} w_rc^T (Z_rho T Z_rho^T) w_rc + |V^T H V|_F^2

with ``Z`` the rank-one matrices ``u u^T`` (rows, packed to the symmetric subspace), ``H = (U U^T)^2``
(elementwise square) and ``V`` the block-diagonal weights. The gradients below are derived by hand and
checked against finite differences in ``tests/unit/test_dfthcsos_fit.py``.

Written from the definition of the metric in ``data/verifiers/dfthcsos/scoreinfra/dfthc_math.py``
(Apache-2.0) and the paper; the initial point is ours (random vectors, least-squares weights), not a
public dataset.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def pack_matrix(tmat: np.ndarray, n: int) -> np.ndarray:
    """``T`` (``n^2 x n^2``, symmetric under ``p<->q`` and ``r<->s``) on the symmetric-matrix subspace.

    The basis is ``E_pp`` and ``(E_pq + E_qp) / sqrt 2``, so inner products match the full space.
    """
    p, q = np.triu_indices(n)
    s = np.where(p == q, 1.0, np.sqrt(2.0))
    return np.asarray(s[:, None] * tmat.reshape(n, n, n, n)[p, q][:, p, q] * s[None, :])


class Objective:
    """``error_2^2`` of vectors ``v`` (rows, any norm) and weights ``w`` and its gradients."""

    def __init__(self, tsym: np.ndarray, n: int, shape: tuple[int, int, int]) -> None:
        self.n = n
        self.R, self.B, self.C = shape
        self.tsym = np.ascontiguousarray(tsym)
        self.t2 = float(np.sum(self.tsym * self.tsym))
        self.p, self.q = np.triu_indices(n)
        self.scale = np.where(self.p == self.q, 1.0, np.sqrt(2.0))

    @property
    def rb(self) -> int:
        return self.R * self.B

    def zvec(self, u: np.ndarray) -> np.ndarray:
        return np.asarray(u[:, self.p] * u[:, self.q] * self.scale)

    def unpack(self, y: np.ndarray) -> np.ndarray:
        """Packed coefficients ``(m, M)`` to full symmetric matrices ``(m, n, n)``."""
        out = np.zeros((y.shape[0], self.n, self.n))
        val = y / self.scale
        out[:, self.p, self.q] = val
        out[:, self.q, self.p] = val
        return out

    def value_grad(self, v: np.ndarray, w: np.ndarray, need_v: bool = True) -> tuple[float, Any, np.ndarray]:
        norm = np.linalg.norm(v, axis=1, keepdims=True)
        u = v / norm
        z = self.zvec(u)
        g = u @ u.T
        h = g**2
        vm = np.zeros((self.rb, self.R * self.C))
        for r in range(self.R):
            vm[r * self.B : (r + 1) * self.B, r * self.C : (r + 1) * self.C] = w[r]
        pm = vm.T @ h @ vm
        gw_full = 4 * (h @ vm) @ pm
        lin, gw = 0.0, np.zeros_like(w)
        sm = np.empty((self.rb, z.shape[1]))
        for r in range(self.R):
            sl = slice(r * self.B, (r + 1) * self.B)
            tz = z[sl] @ self.tsym
            tt = tz @ z[sl].T
            vr = vm[sl, r * self.C : (r + 1) * self.C]
            lin += float(np.einsum("ik,ij,jk->", vr, tt, vr))
            gw[r] = -4 * (tt @ vr) + gw_full[sl, r * self.C : (r + 1) * self.C]
            if need_v:
                sm[sl] = (vr @ vr.T) @ tz
        f = self.t2 - 2 * lin + float(np.sum(pm * pm))
        if not need_v:
            return f, None, gw
        kmat = 2 * vm @ pm @ vm.T
        gu = 4 * (g * kmat) @ u - 8 * np.einsum("bpq,bq->bp", self.unpack(sm), u)
        gv = (gu - u * np.sum(gu * u, axis=1, keepdims=True)) / norm
        return f, gv, gw

    def error2(self, v: np.ndarray, w: np.ndarray) -> float:
        return float(np.sqrt(max(self.value_grad(v, w, need_v=False)[0], 0.0)))
