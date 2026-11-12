"""Noise-robust fit in angle space (QCC-16, E021): find tables whose error survives rounding to ``brot`` bits.

    uv run python scripts/dfthcsos_noisefit.py <fit dir> <out dir> --tsym out/fit/tsym.npy --brot 8 \
        --rounds 40 --iters 50 --draws 2

The balanced-tree angles ``theta`` (word units) and the weights are optimised on the mean of
``error_2^2`` over
``--draws`` fixed rounding-noise draws (uniform in +-0.5 word, scaled by a ramp from ``--s0`` to 1 over the
rounds, redrawn each round). That is the expected loss of rounding, so the minimiser is a table that is
flat in
the directions the grid disturbs, instead of a table that is later pushed onto the grid. Ends with naive
rounding plus a weights-only refit, and writes ``v.npy``/``w.npy``/``words.npy`` like ``dfthcsos_qat.py``, and
``theta.npy``/``w_cont.npy`` for a follow-up progressive rounding (``dfthcsos_qat2.py --from-theta``).
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
    ap.add_argument("--rounds", type=int, default=40)
    ap.add_argument("--iters", type=int, default=50)
    ap.add_argument("--draws", type=int, default=2)
    ap.add_argument("--s0", type=float, default=0.1)
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
    w = np.load(a.fit / "w.npy")
    r, b, c = w.shape
    edges, brot = balanced_tree(), a.brot
    obj = Objective(tsym, 76, (r, b, c))
    scale = (1 << (brot - 1)) / np.pi
    if (a.fit / "theta.npy").exists():
        theta = np.load(a.fit / "theta.npy")
    else:
        theta = angles_of(np.load(a.fit / "v.npy"), edges, brot)
    round0 = 0
    if (a.out / "state.npz").exists():
        st = np.load(a.out / "state.npz")
        theta, w, round0 = st["theta"], st["w"], int(st["round"])
        print(f"resuming at round {round0}", flush=True)
    sc = float(np.abs(w).mean())
    tshape, wshape, tsize = theta.shape, w.shape, theta.size
    t0 = time.time()

    def err(th: np.ndarray, ww: np.ndarray) -> float:
        return obj.error2(decode_real(th, edges, brot)[0], ww)

    print(f"start: error_2 {err(theta, w):.5f}  rounded {err(np.rint(theta), w):.5f}", flush=True)
    for rd in range(round0, a.rounds):
        s = a.s0 + (1.0 - a.s0) * min(1.0, rd / max(a.rounds * 0.75, 1))
        rng = np.random.default_rng(1000 + rd)
        noise = [s * rng.uniform(-0.5, 0.5, size=theta.shape) for _ in range(a.draws)]

        def fg(x: np.ndarray, noise=noise) -> tuple[float, np.ndarray]:
            th = x[:tsize].reshape(tshape) * scale
            ww = x[tsize:].reshape(wshape) * sc
            ftot, gth, gw = 0.0, np.zeros_like(th), np.zeros_like(ww)
            for nz in noise:
                v, saved = decode_real(th + nz, edges, brot)
                f, gv, gww = obj.value_grad(v, ww)
                ftot += f
                gth += decode_backward(th + nz, edges, brot, saved, gv)
                gw += gww
            k = len(noise)
            return ftot / k * 1e3, np.concatenate([gth.ravel() * scale / k, gw.ravel() * sc / k]) * 1e3

        x0 = np.concatenate([theta.ravel() / scale, w.ravel() / sc])
        res = minimize(fg, x0, jac=True, method="L-BFGS-B", options={"maxiter": a.iters, "maxcor": 30})
        theta = res.x[: theta.size].reshape(theta.shape) * scale
        w = res.x[theta.size :].reshape(w.shape) * sc
        row = {
            "round": rd,
            "s": round(s, 3),
            "noisy": float(np.sqrt(max(res.fun / 1e3, 0))),
            "cont": err(theta, w),
            "rounded": err(np.rint(theta), w),
            "t": round(time.time() - t0),
        }
        print(json.dumps(row), flush=True)
        np.savez(a.out / "state.npz", theta=theta, w=w, round=rd + 1)
        if a.max_secs and time.time() - t0 > a.max_secs:
            print("time limit; state saved", flush=True)
            return
    np.save(a.out / "theta.npy", theta)
    np.save(a.out / "w_cont.npy", w)
    th = np.rint(theta)
    v, _ = decode_real(th, edges, brot)

    def fgw(x: np.ndarray) -> tuple[float, np.ndarray]:
        f, _, gw = obj.value_grad(v, x.reshape(w.shape) * sc, need_v=False)
        return f * 1e3, gw.ravel() * sc * 1e3

    res = minimize(fgw, w.ravel() / sc, jac=True, method="L-BFGS-B", options={"maxiter": 300, "maxcor": 30})
    w = res.x.reshape(w.shape) * sc
    print(f"final all-rounded error_2 {obj.error2(v, w):.5f}", flush=True)
    np.save(a.out / "v.npy", v)
    np.save(a.out / "w.npy", w)
    np.save(a.out / "words.npy", th.astype(np.int64) % (1 << brot))


if __name__ == "__main__":
    main()
