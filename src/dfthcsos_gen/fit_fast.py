"""Faster ``error_2^2`` and gradients for the DF-THC fit (QCC-16): same function as ``fit.Objective``.

Three savings over ``fit.Objective``:

* the products with the dense target ``T`` (``B x M @ M x M`` per group, 2.4 GFlop each) are replaced by the
  eigendecomposition ``T = U diag(lam) U^T`` truncated to the ``rank`` largest ``|lam|``: ``z T z^T`` and
  ``(A z) T`` then cost ``B x M x rank`` (``rank = None`` keeps the exact dense path). The tail dropped
  (``|T - T_rank|_F`` is 0.0013 at rank 500) moves the objective by a few percent of ``error_2^2`` near the
  gate, so use it for the long bulk of a fit and finish with ``rank=None``;
* the Gram algebra ``V^T H V`` and its gradient use the block structure of ``V`` (a ``B x C`` block per group)
  instead of dense ``RB x RC`` matrices (8x fewer flops);
* the large products can run in ``float32`` (``dtype``) while all sums stay in ``float64``.

Pinned against ``fit.Objective`` in ``tests/unit/test_dfthcsos_fit_fast.py``.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .fit import Objective


class FastObjective(Objective):
    def __init__(
        self,
        tsym: np.ndarray,
        n: int,
        shape: tuple[int, int, int],
        rank: int | None = None,
        dtype: Any = np.float64,
    ) -> None:
        super().__init__(tsym, n, shape)
        self.rank = rank
        self.dt = dtype
        if rank is not None:
            lam, u = np.linalg.eigh(self.tsym)
            keep = np.argsort(-np.abs(lam))[:rank]
            self.lam = lam[keep]
            self.u = np.ascontiguousarray(u[:, keep]).astype(dtype)
            self.ut = np.ascontiguousarray(self.u.T)
            self.t2 = float(np.sum(self.tsym * self.tsym))

    def value_grad(
        self, v: np.ndarray, w: np.ndarray, need_v: bool = True, zu: np.ndarray | None = None
    ) -> tuple[float, Any, np.ndarray]:
        r_, b_, c_ = self.R, self.B, self.C
        norm = np.linalg.norm(v, axis=1, keepdims=True)
        u = v / norm
        z = self.zvec(u)
        g = u @ u.T
        h = g * g
        sl = [slice(r * b_, (r + 1) * b_) for r in range(r_)]
        cl = [slice(r * c_, (r + 1) * c_) for r in range(r_)]
        hv = np.concatenate([h[:, sl[r]] @ w[r] for r in range(r_)], axis=1)  # (RB, RC) = H V
        p = np.concatenate([w[r].T @ hv[sl[r]] for r in range(r_)], axis=0)  # (RC, RC) = V^T H V
        quad = float(np.sum(p * p))
        hvp = hv @ p  # (RB, RC)
        lin = 0.0
        gw = np.zeros_like(w)
        sm = np.empty((self.rb, z.shape[1])) if need_v else None
        if self.rank is not None and zu is None:
            zu = (z.astype(self.dt) @ self.u).astype(np.float64)
        for r in range(r_):
            wr = w[r]
            if self.rank is not None:
                assert zu is not None
                zl = zu[sl[r]] * self.lam  # (B, rank)
                tt = zl @ zu[sl[r]].T
                tz_part = None
            else:
                tz_part = z[sl[r]] @ self.tsym
                tt = tz_part @ z[sl[r]].T
            lin += float(np.einsum("ik,ij,jk->", wr, tt, wr))
            gw[r] = -4 * (tt @ wr) + 4 * (hvp[sl[r]][:, cl[r]])
            if sm is not None:
                a = wr @ wr.T
                if self.rank is not None:
                    sm[sl[r]] = (a @ zl).astype(self.dt) @ self.ut
                else:
                    assert tz_part is not None
                    sm[sl[r]] = a @ tz_part
        f = self.t2 - 2 * lin + quad
        if sm is None:
            return f, None, gw
        vp = np.concatenate([w[r] @ p[cl[r]] for r in range(r_)], axis=0)  # (RB, RC)
        kmat = np.empty((self.rb, self.rb))
        for r in range(r_):
            for s in range(r_):
                kmat[sl[r], sl[s]] = 2 * (vp[sl[r]][:, cl[s]] @ w[s].T)
        gu = 4 * (g * kmat) @ u - 8 * np.einsum("bpq,bq->bp", self.unpack(sm.astype(np.float64)), u)
        gv = (gu - u * np.sum(gu * u, axis=1, keepdims=True)) / norm
        return f, gv, gw
