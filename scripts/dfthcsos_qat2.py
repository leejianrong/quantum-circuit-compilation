"""Sensitivity-ordered quantization-aware fit (QCC-16, E022): a gentler end for the rounding schedule.

    uv run python scripts/dfthcsos_qat2.py <fit dir> <out dir> --tsym out/fit/tsym.npy --brot 8 \
        --stages 24 --shrink 0.78 --iters 60

Same parametrisation as ``dfthcsos_qat.py`` (balanced-tree angles + weights, ``error_2`` by L-BFGS through the
decoder) but each stage freezes the angles whose rounding is predicted to cost least, not the ones nearest the
grid. The prediction is the quadratic model ``g d + d^2 H_tt / 2`` for the better of floor/ceil, with the
gradient ``g`` and a Hutchinson estimate of the diagonal Hessian ``H_tt`` taken at the current point. The free
fraction shrinks geometrically (``--shrink`` per stage) so the last angles are frozen one small batch at a
time. State is written after every stage (``state.npz``) and resumed, so a Kaggle chain can continue a run.
Writes ``v.npy`` (decoded vectors), ``w.npy`` and ``words.npy`` at the end, like ``dfthcsos_qat.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("fit", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--tsym", type=Path, default=Path("out/fit/tsym.npy"))
    ap.add_argument("--brot", type=int, default=8)
    ap.add_argument("--stages", type=int, default=24)
    ap.add_argument("--first", type=float, default=0.4, help="fraction frozen at the first stage")
    ap.add_argument("--shrink", type=float, default=0.78, help="free count multiplier per later stage")
    ap.add_argument("--iters", type=int, default=60)
    ap.add_argument("--probes", type=int, default=4)
    ap.add_argument("--order", choices=["model", "nearest"], default="model")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--max-secs", type=float, default=0.0)
    a = ap.parse_args()
    for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[k] = str(a.threads)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    import numpy as np
    from scipy.optimize import minimize

    from dfthcsos_gen.fit import Objective
    from dfthcsos_gen.post import angles_of, balanced_tree, decode_backward, decode_real

    a.out.mkdir(parents=True, exist_ok=True)
    tsym = np.load(a.tsym)
    v0, w = np.load(a.fit / "v.npy"), np.load(a.fit / "w.npy")
    r, b, c = w.shape
    edges, brot = balanced_tree(), a.brot
    obj = Objective(tsym, 76, (r, b, c))
    scale = (1 << (brot - 1)) / np.pi
    theta = angles_of(v0, edges, brot)
    fixed = np.zeros(theta.shape, dtype=bool)
    stage0 = 0
    if (a.out / "state.npz").exists():
        st = np.load(a.out / "state.npz")
        theta, w, fixed, stage0 = st["theta"], st["w"], st["fixed"], int(st["stage"])
        print(f"resuming after stage {stage0}", flush=True)
    sc = float(np.abs(w).mean())
    wshape = w.shape
    t0 = time.time()

    def full(th: np.ndarray, ww: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
        v, saved = decode_real(th, edges, brot)
        f, gv, gw = obj.value_grad(v, ww)
        return f, decode_backward(th, edges, brot, saved, gv), gw

    def err(th: np.ndarray, ww: np.ndarray) -> float:
        return obj.error2(decode_real(th, edges, brot)[0], ww)

    def freeze_scores(th: np.ndarray, ww: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Predicted cost of rounding each angle and the rounded value it picks."""
        lo, hi = np.floor(th), np.ceil(th)
        if a.order == "nearest":
            near = np.rint(th)
            return np.abs(th - near), near
        _, g, _ = full(th, ww)
        hd = np.zeros_like(th)
        rng = np.random.default_rng(stage0)
        eps = 0.05
        for _ in range(a.probes):
            z = rng.choice([-1.0, 1.0], size=th.shape)
            gp = full(th + eps * z, ww)[1]
            gm = full(th - eps * z, ww)[1]
            hd += z * (gp - gm) / (2 * eps)
        hd = np.maximum(hd / a.probes, 1e-12)
        cost = []
        for tgt in (lo, hi):
            d = tgt - th
            cost.append(g * d + 0.5 * hd * d * d)
        use_hi = cost[1] < cost[0]
        return np.where(use_hi, cost[1], cost[0]), np.where(use_hi, hi, lo)

    print(f"start: error_2 {err(theta, w):.5f}  rounded {err(np.rint(theta), w):.5f}", flush=True)
    log = []
    for stage in range(stage0, a.stages + 1):
        last = stage == a.stages
        free = ~fixed
        nf = int(free.sum())
        if nf:

            def fg(x: np.ndarray, free=free, nf=nf) -> tuple[float, np.ndarray]:
                th = theta.copy()
                th[free] = x[:nf] * scale
                ww = x[nf:].reshape(wshape) * sc
                f, gth, gw = full(th, ww)
                return f * 1e3, np.concatenate([gth[free] * scale, gw.ravel() * sc]) * 1e3

            x0 = np.concatenate([theta[free] / scale, w.ravel() / sc])
            res = minimize(fg, x0, jac=True, method="L-BFGS-B", options={"maxiter": a.iters, "maxcor": 30})
            theta[free] = res.x[:nf] * scale
            w = res.x[nf:].reshape(wshape) * sc
        cont = err(theta, w)
        if last or nf == 0:
            break
        if stage == 0:
            target_free = int(round((1 - a.first) * theta.size))
        else:
            target_free = int(nf * a.shrink)
        if stage == a.stages - 1:
            target_free = 0
        target = nf - max(target_free, 0)
        if target > 0:
            score, val = freeze_scores(theta, w)
            score = np.where(fixed, np.inf, score)
            idx = np.argsort(score, axis=None)[:target]
            sel = np.zeros(theta.size, dtype=bool)
            sel[idx] = True
            sel = sel.reshape(theta.shape)
            theta[sel] = val[sel]
            fixed |= sel
        row = {
            "stage": stage,
            "continuous": cont,
            "after": err(theta, w),
            "fixed": int(fixed.sum()),
            "t": round(time.time() - t0),
        }
        log.append(row)
        print(json.dumps(row), flush=True)
        np.savez(a.out / "state.npz", theta=theta, w=w, fixed=fixed, stage=stage + 1)
        if a.max_secs and time.time() - t0 > a.max_secs:
            print("time limit; state saved", flush=True)
            return
    assert fixed.all()
    v, _ = decode_real(theta, edges, brot)

    def fgw(x: np.ndarray) -> tuple[float, np.ndarray]:
        f, _, gw = obj.value_grad(v, x.reshape(w.shape) * sc, need_v=False)
        return f * 1e3, gw.ravel() * sc * 1e3

    res = minimize(fgw, w.ravel() / sc, jac=True, method="L-BFGS-B", options={"maxiter": 300, "maxcor": 30})
    w = res.x.reshape(w.shape) * sc
    print(f"final all-rounded error_2 {obj.error2(v, w):.5f}", flush=True)
    np.save(a.out / "v.npy", v)
    np.save(a.out / "w.npy", w)
    np.save(a.out / "words.npy", np.rint(theta).astype(np.int64) % (1 << brot))


if __name__ == "__main__":
    main()
