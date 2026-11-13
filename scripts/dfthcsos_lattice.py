"""Lattice refinement of rounded words (QCC-16, E022): +-1 word moves where the quadratic model gains.

Negative result, kept for the record: see docs/experiments/dfthcsos-eight-bit.md.

    uv run python scripts/dfthcsos_lattice.py <dir with v.npy w.npy words.npy> <out dir> --brot 8

Starts from integer words on the balanced tree (for example the output of ``dfthcsos_qat.py``). Each
iteration refits the weights on the decoded vectors, takes the gradient ``g`` of ``error_2^2`` in the word
units and a Hutchinson estimate of the diagonal Hessian ``h``, predicts the gain ``g d + h d^2 / 2`` of
``d = +-1`` for every word and applies the best ``frac`` of the moves that gain. A step that does not lower
``error_2`` is undone and ``frac`` halves; a good step grows it by 1.3. Writes ``words.npy``, ``v.npy``,
``w.npy`` after every improvement.
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
    ap.add_argument("--brot", type=int, default=8)
    ap.add_argument("--iters", type=int, default=100)
    ap.add_argument("--frac", type=float, default=0.01)
    ap.add_argument("--probes", type=int, default=6)
    ap.add_argument("--wits", type=int, default=15, help="weights-only L-BFGS iterations per step")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--max-secs", type=float, default=0.0)
    a = ap.parse_args()
    for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[k] = str(a.threads)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    import numpy as np
    from scipy.optimize import minimize

    from dfthcsos_gen.fit import Objective
    from dfthcsos_gen.post import balanced_tree, decode_backward, decode_real

    a.out.mkdir(parents=True, exist_ok=True)
    tsym = np.load(a.tsym)
    w = np.load(a.fit / "w.npy")
    edges, brot = balanced_tree(), a.brot
    half = 1 << (brot - 1)
    words = np.load(a.fit / "words.npy")
    theta = np.where(words >= half, words - (1 << brot), words).astype(np.float64)  # any representative works
    obj = Objective(tsym, 76, w.shape)
    sc = float(np.abs(w).mean())
    t0 = time.time()

    def full(th: np.ndarray, ww: np.ndarray) -> tuple[float, np.ndarray]:
        v, saved = decode_real(th, edges, brot)
        f, gv, _ = obj.value_grad(v, ww)
        return f, decode_backward(th, edges, brot, saved, gv)

    def refit(th: np.ndarray, ww: np.ndarray) -> np.ndarray:
        v, _ = decode_real(th, edges, brot)

        def fgw(x: np.ndarray) -> tuple[float, np.ndarray]:
            f, _, gw = obj.value_grad(v, x.reshape(ww.shape) * sc, need_v=False)
            return f * 1e3, gw.ravel() * sc * 1e3

        res = minimize(
            fgw, ww.ravel() / sc, jac=True, method="L-BFGS-B", options={"maxiter": a.wits, "maxcor": 30}
        )
        return np.asarray(res.x.reshape(ww.shape) * sc)

    def err(th: np.ndarray, ww: np.ndarray) -> float:
        return obj.error2(decode_real(th, edges, brot)[0], ww)

    w = refit(theta, w)
    best = err(theta, w)
    print(f"start error_2 {best:.5f}", flush=True)
    frac, rng = a.frac, np.random.default_rng(0)
    for it in range(a.iters):
        _, g = full(theta, w)
        hd = np.zeros_like(theta)
        for _ in range(a.probes):
            z = rng.choice([-1.0, 1.0], size=theta.shape)
            hd += z * (full(theta + 0.05 * z, w)[1] - full(theta - 0.05 * z, w)[1]) / 0.1
        hd = np.maximum(hd / a.probes, 1e-9)
        hd = np.broadcast_to(hd.mean(axis=0, keepdims=True), hd.shape)  # the per-vector estimate is too noisy
        up, dn = g + 0.5 * hd, -g + 0.5 * hd  # predicted change for +1 and -1
        gain = np.minimum(up, dn)
        step = np.where(up < dn, 1.0, -1.0)
        cand = np.argwhere(gain < 0)
        n = max(1, int(frac * theta.size))
        order = np.argsort(gain[tuple(cand.T)])[:n]
        sel = tuple(cand[order].T)
        trial = theta.copy()
        trial[sel] += step[sel]
        w2 = refit(trial, w)
        e = err(trial, w2)
        ok = e < best
        print(
            f"it {it} moves {len(order)} frac {frac:.4f} error_2 {e:.5f} "
            f"{'ok' if ok else 'undo'} t={time.time() - t0:.0f}",
            flush=True,
        )
        if ok:
            theta, w, best = trial, w2, e
            frac = min(frac * 1.3, 0.2)
            v, _ = decode_real(theta, edges, brot)
            np.save(a.out / "words.npy", np.rint(theta).astype(np.int64) % (1 << brot))
            np.save(a.out / "v.npy", v)
            np.save(a.out / "w.npy", w)
        else:
            frac *= 0.5
        if a.max_secs and time.time() - t0 > a.max_secs:
            break
    print(f"final error_2 {best:.5f}", flush=True)


if __name__ == "__main__":
    main()
