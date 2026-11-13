"""Quantization-aware fit by progressive rounding of the Givens angles (QCC-16, M1 cost lever).

    uv run python scripts/dfthcsos_qat.py <fit dir> <out dir> --tsym out/fit/tsym.npy --brot 10 \
        --stages 0.4,0.65,0.8,0.9,0.96,1.0 --iters 80

The vectors are parametrised by their Givens-tree angles (balanced tree). Each stage optimises the free angles
and the weights on ``error_2`` (L-BFGS, gradient through the decoder), then rounds the free angles closest to
the grid until the stage's fraction is fixed. The last stage refits the weights on the all-rounded vectors.
Writes ``v.npy`` (the decoded, exactly representable vectors) and ``w.npy`` so that
``scripts/dfthcsos_post.py`` re-encodes them losslessly at the same ``--brot``.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("fit", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--tsym", type=Path, default=Path("out/fit/tsym.npy"))
    ap.add_argument("--brot", type=int, default=10)
    ap.add_argument("--stages", default="0.4,0.65,0.8,0.9,0.96,1.0")
    ap.add_argument("--iters", type=int, default=80)
    ap.add_argument("--threads", type=int, default=12)
    ap.add_argument(
        "--half", action="store_true", help="angles in the half circle (bit brot-1 == bit brot-2)"
    )
    a = ap.parse_args()
    for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[k] = str(a.threads)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    import numpy as np
    from scipy.optimize import minimize

    from dfthcsos_gen.fit import Objective
    from dfthcsos_gen.post import angles_of, balanced_tree, decode_backward, decode_real

    tsym = np.load(a.tsym)
    v0, w = np.load(a.fit / "v.npy"), np.load(a.fit / "w.npy")
    r, b, c = w.shape
    edges, brot = balanced_tree(), a.brot
    obj = Objective(tsym, 76, (r, b, c))
    scale = (1 << (brot - 1)) / np.pi  # word units per radian
    theta = angles_of(v0, edges, brot, a.half)
    fixed = np.zeros(theta.shape, dtype=bool)
    sc = float(np.abs(w).mean())
    wshape = w.shape
    t0 = time.time()

    def err(th: np.ndarray, ww: np.ndarray) -> float:
        return obj.error2(decode_real(th, edges, brot)[0], ww)

    print(f"start: error_2 {err(theta, w):.5f}  rounded {err(np.rint(theta), w):.5f}", flush=True)
    for frac in (float(x) for x in a.stages.split(",")):
        free = ~fixed
        nf = int(free.sum())

        def fg(x: np.ndarray, free=free, nf=nf) -> tuple[float, np.ndarray]:
            th = theta.copy()
            th[free] = x[:nf] * scale
            ww = x[nf:].reshape(wshape) * sc
            v, saved = decode_real(th, edges, brot)
            f, gv, gw = obj.value_grad(v, ww)
            gth = decode_backward(th, edges, brot, saved, gv)  # per word unit; x is in radians
            return f * 1e3, np.concatenate([gth[free] * scale, gw.ravel() * sc]) * 1e3

        x0 = np.concatenate([theta[free] / scale, w.ravel() / sc])
        res = minimize(fg, x0, jac=True, method="L-BFGS-B", options={"maxiter": a.iters, "maxcor": 30})
        theta[free] = res.x[:nf] * scale
        w = res.x[nf:].reshape(w.shape) * sc
        cont = err(theta, w)
        # fix the free angles nearest the grid until `frac` of all angles are fixed
        target = int(round(frac * theta.size)) - int(fixed.sum())
        if target > 0:
            dist = np.abs(theta - np.rint(theta))
            dist[fixed] = np.inf
            idx = np.argsort(dist, axis=None)[:target]
            flat = np.zeros(theta.size, dtype=bool)
            flat[idx] = True
            sel = flat.reshape(theta.shape)
            theta[sel] = np.rint(theta[sel])
            if a.half:  # keep bit brot-1 == bit brot-2: the grid is [-2^(b-2), 2^(b-2) - 1]
                theta[sel] = np.clip(theta[sel], -(1 << (brot - 2)), (1 << (brot - 2)) - 1)
            fixed |= sel
        print(
            f"frac {frac}: continuous {cont:.5f} after fixing {err(theta, w):.5f} "
            f"fixed {int(fixed.sum())}/{theta.size} t={time.time() - t0:.0f}s",
            flush=True,
        )
    assert fixed.all()
    # weights-only refit on the rounded vectors
    v, _ = decode_real(theta, edges, brot)

    def fgw(x: np.ndarray) -> tuple[float, np.ndarray]:
        f, _, gw = obj.value_grad(v, x.reshape(w.shape) * sc, need_v=False)
        return f * 1e3, gw.ravel() * sc * 1e3

    res = minimize(fgw, w.ravel() / sc, jac=True, method="L-BFGS-B", options={"maxiter": 300, "maxcor": 30})
    w = res.x.reshape(w.shape) * sc
    print(f"final all-rounded error_2 {obj.error2(v, w):.5f}", flush=True)
    a.out.mkdir(parents=True, exist_ok=True)
    np.save(a.out / "v.npy", v)
    np.save(a.out / "w.npy", w)
    np.save(a.out / "words.npy", np.rint(theta).astype(np.int64) % (1 << brot))


if __name__ == "__main__":
    main()
