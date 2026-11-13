"""Variable projection for the DF-THC fit: optimise the vectors ``v`` with the weights ``w`` solved out
(QCC-16).

``f(v, w) = |T|^2 - 2 sum_r w_r^T (Z_r T Z_r^T) w_r + |V^T H V|^2`` depends on ``w`` only through the
small Gram matrices ``tt_r = Z_r T Z_r^T`` (``B x B``) and ``H = (U U^T)^2``. For fixed ``v`` those are
computed once (the expensive ``T`` products), after which the minimisation over ``w`` costs milliseconds
per step. The reduced function ``F(v) = min_w f(v, w)`` has gradient ``df/dv`` at the optimal ``w``
(envelope theorem), so an outer L-BFGS on ``v`` sees a smoother, better-conditioned problem than the
joint one. ``reduced`` returns ``(F, grad_v, w_star)``; ``w`` is warm started between calls.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.optimize import minimize  # type: ignore[import-untyped,unused-ignore]

from .fit_fast import FastObjective


def solve_w(
    obj: FastObjective, h: np.ndarray, tt: list[np.ndarray], w0: np.ndarray, iters: int
) -> tuple[np.ndarray, float]:
    """Minimise over ``w`` with ``tt`` and ``h`` fixed; returns ``(w, f)``."""
    r_, b_, c_ = obj.R, obj.B, obj.C
    sl = [slice(r * b_, (r + 1) * b_) for r in range(r_)]
    cl = [slice(r * c_, (r + 1) * c_) for r in range(r_)]
    sc = float(np.abs(w0).mean())

    def fg(x: np.ndarray) -> tuple[float, np.ndarray]:
        w = x.reshape(w0.shape) * sc
        hv = np.concatenate([h[:, sl[r]] @ w[r] for r in range(r_)], axis=1)
        p = np.concatenate([w[r].T @ hv[sl[r]] for r in range(r_)], axis=0)
        hvp = hv @ p
        lin = 0.0
        gw = np.zeros_like(w)
        for r in range(r_):
            lin += float(np.einsum("ik,ij,jk->", w[r], tt[r], w[r]))
            gw[r] = -4 * (tt[r] @ w[r]) + 4 * hvp[sl[r]][:, cl[r]]
        return (obj.t2 - 2 * lin + float(np.sum(p * p))) * 1e3, gw.ravel() * sc * 1e3

    res = minimize(fg, w0.ravel() / sc, jac=True, method="L-BFGS-B", options={"maxiter": iters, "maxcor": 30})
    return np.asarray(res.x.reshape(w0.shape) * sc), float(res.fun) * 1e-3


def reduced(
    obj: FastObjective, v: np.ndarray, w0: np.ndarray, inner: int = 40
) -> tuple[float, np.ndarray, np.ndarray]:
    """``(F(v), dF/dv, w_star)`` with ``w`` re-optimised from ``w0`` for ``inner`` steps."""
    r_, b_ = obj.R, obj.B
    u = v / np.linalg.norm(v, axis=1, keepdims=True)
    z = obj.zvec(u)
    h = (u @ u.T) ** 2
    zu = (z.astype(obj.dt) @ obj.u).astype(np.float64) if obj.rank is not None else None
    tt = []
    for r in range(r_):
        s = slice(r * b_, (r + 1) * b_)
        if obj.rank is not None:
            assert zu is not None
            tt.append((zu[s] * obj.lam) @ zu[s].T)
        else:
            tt.append(z[s] @ obj.tsym @ z[s].T)
    w, _ = solve_w(obj, h, tt, w0, inner)
    f, gv, _ = obj.value_grad(v, w, zu=zu)
    return f, np.asarray(gv), w


def minimize_v(
    obj: FastObjective, v0: np.ndarray, w0: np.ndarray, iters: int, inner: int = 40, callback: Any = None
) -> tuple[np.ndarray, np.ndarray, float]:
    """Outer L-BFGS on ``v`` over the reduced function; returns ``(v, w, error_2)``."""
    state = {"w": w0.copy()}

    def fg(x: np.ndarray) -> tuple[float, np.ndarray]:
        f, gv, w = reduced(obj, x.reshape(v0.shape), state["w"], inner)
        state["w"] = w
        return f * 1e3, gv.ravel() * 1e3

    res = minimize(
        fg,
        v0.ravel(),
        jac=True,
        method="L-BFGS-B",
        callback=callback,
        options={"maxiter": iters, "maxcor": 30},
    )
    v = res.x.reshape(v0.shape)
    return v, state["w"], float(np.sqrt(max(res.fun * 1e-3, 0.0)))
