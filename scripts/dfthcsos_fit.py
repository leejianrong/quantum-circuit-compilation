"""Our own DF-THC fit for dfthcsos (QCC-16 co-design). Needs the competition data (not committed).

    QCC_DATA=<data dir> uv run python scripts/dfthcsos_fit.py tsym  <out dir>
    QCC_DATA=<data dir> uv run python scripts/dfthcsos_fit.py fit   <out dir> R B C [iters] [seed]

``tsym`` caches the FCIDUMP integrals plus the fixed symmetry shift on the symmetric-pair space.
``fit`` starts from random unit vectors (nothing from any public factorization), minimises
``error_2^2`` with L-BFGS in raw-vector coordinates and writes ``v.npy`` and ``w.npy`` to
``<out dir>/R_B_C/`` every few hundred iterations. See docs/experiments/dfthcsos-codesign.md.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

DATA = Path(os.environ.get("QCC_DATA", "data"))
sys.path += [str(DATA / "verifiers")]
N = 76


def build_tsym(out: Path) -> None:
    from dfthcsos.verify import load_inputs

    from dfthcsos_gen.fit import pack_matrix

    inp = load_inputs(DATA / "sample_submission" / "dfthcsos" / "submission.npz")
    tei = np.array(inp.ref["tei"], dtype=np.float64)
    s = np.asarray(inp.S, dtype=np.float64)
    d = np.arange(N)
    tei[:, :, d, d] += 0.5 * s[:, :, None]
    tei[d, d, :, :] += 0.5 * s[None, :, :]
    np.save(out / "tsym.npy", pack_matrix(tei.reshape(N * N, N * N), N))


def init_point(obj, seed: int):
    rng = np.random.default_rng(seed)
    v = rng.normal(size=(obj.rb, N))
    w = rng.normal(size=(obj.R, obj.B, obj.C))
    f0, _, _ = obj.value_grad(v, w, need_v=False)
    # f(s w) = t2 - 2 s^2 a + s^4 b: read a and b off three evaluations
    f1 = obj.value_grad(v, 0.5 * w, need_v=False)[0]
    f2 = obj.value_grad(v, 2.0 * w, need_v=False)[0]
    # solve for (a, b) from f(1/2) and f(1)
    a_mat = np.array([[-2 * 0.25, 0.0625], [-2.0, 1.0]])
    a, b = np.linalg.solve(a_mat, [f1 - obj.t2, f0 - obj.t2])
    del f2
    s2 = max(a / b, 1e-12)
    return v, w * np.sqrt(s2)


def fit(out: Path, shape: tuple[int, int, int], iters: int, seed: int) -> None:
    from dfthcsos_gen.fit import Objective

    obj = Objective(np.load(out / "tsym.npy"), N, shape)
    run = out / "x".join(map(str, shape))
    run.mkdir(exist_ok=True)
    if (run / "v.npy").exists():
        v, w = np.load(run / "v.npy"), np.load(run / "w.npy")
    else:
        v, w = init_point(obj, seed)
    wsc = float(np.abs(w).mean())
    nv = v.size
    t0 = time.time()
    state = {"n": 0}

    def unpack(x):
        return x[:nv].reshape(v.shape), x[nv:].reshape(w.shape) * wsc

    def fg(x):
        vv, ww = unpack(x)
        f, gv, gw = obj.value_grad(vv, ww)
        return f * 1e3, np.concatenate([gv.ravel(), gw.ravel() * wsc]) * 1e3

    def cb(x):
        state["n"] += 1
        if state["n"] % 100 == 0:
            vv, ww = unpack(x)
            np.save(run / "v.npy", vv)
            np.save(run / "w.npy", ww)
            print(f"  it {state['n']} err2={obj.error2(vv, ww):.5f} t={time.time() - t0:.0f}s", flush=True)

    x0 = np.concatenate([v.ravel(), w.ravel() / wsc])
    res = minimize(fg, x0, jac=True, method="L-BFGS-B", callback=cb, options={"maxiter": iters, "maxcor": 20})
    vv, ww = unpack(res.x)
    np.save(run / "v.npy", vv)
    np.save(run / "w.npy", ww)
    print(f"done err2={obj.error2(vv, ww):.5f} nit={res.nit} {time.time() - t0:.0f}s", flush=True)


def main() -> None:
    cmd, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    if cmd == "tsym":
        build_tsym(out)
    elif cmd == "fit":
        r, b, c = map(int, sys.argv[3:6])
        fit(
            out,
            (r, b, c),
            int(sys.argv[6]) if len(sys.argv) > 6 else 2000,
            int(sys.argv[7]) if len(sys.argv) > 7 else 0,
        )


if __name__ == "__main__":
    main()
