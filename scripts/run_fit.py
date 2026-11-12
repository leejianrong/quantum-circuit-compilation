"""Pod-friendly DF-THC fit of the dfthcsos factorization (QCC-16). Needs only numpy, scipy and ``src/``.

    uv run python scripts/run_fit.py --tsym out/fit/tsym.npy --shape 8 143 44 --seed 0 \
        --iters 3000 --threads 16 --out out/fit/8x143x44_s0 --checkpoint-every 100

``tsym.npy`` is the packed target (``scripts/dfthcsos_fit.py tsym <dir>``; it derives from the competition
FCIDUMP, so it is never committed). Minimises ``error_2^2`` with L-BFGS from random unit vectors. Writes
``v.npy``, ``w.npy`` and ``log.jsonl`` to ``--out`` every ``--checkpoint-every`` iterations and resumes from
them when they exist. See docs/experiments/dfthcsos-codesign.md.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


def parse(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tsym", type=Path, required=True)
    ap.add_argument("--shape", type=int, nargs=3, metavar=("R", "B", "C"), default=(8, 143, 44))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--iters", type=int, default=2000, help="L-BFGS iterations (total, including resumed)")
    ap.add_argument("--threads", type=int, default=0, help="BLAS threads (0 = leave to the library)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--checkpoint-every", type=int, default=100)
    ap.add_argument("--maxcor", type=int, default=20)
    return ap.parse_args(argv)


def set_threads(n: int) -> None:
    """Must run before numpy is imported."""
    if n > 0:
        for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
            os.environ[k] = str(n)


def init_point(obj: Any, seed: int) -> tuple[Any, Any]:
    """Random unit vectors and weights scaled so that ``f(s w)`` is minimal along the ray."""
    import numpy as np

    rng = np.random.default_rng(seed)
    v = rng.normal(size=(obj.rb, obj.n))
    w = rng.normal(size=(obj.R, obj.B, obj.C))
    f1 = obj.value_grad(v, w, need_v=False)[0]
    fh = obj.value_grad(v, 0.5 * w, need_v=False)[0]
    # f(s w) = t2 - 2 s^2 a + s^4 b, so f - t2 at s = 1/2 and 1 gives a and b
    a, b = np.linalg.solve([[-0.5, 0.0625], [-2.0, 1.0]], [fh - obj.t2, f1 - obj.t2])
    return v, w * np.sqrt(max(a / b, 1e-12))


def run(args: argparse.Namespace) -> float:
    import numpy as np
    from scipy.optimize import minimize

    from dfthcsos_gen.fit import Objective

    tsym = np.load(args.tsym)
    n = round((np.sqrt(8 * tsym.shape[0] + 1) - 1) / 2)
    r, b, c = args.shape
    obj = Objective(tsym, n, (r, b, c))
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    done = 0
    if (out / "v.npy").exists():
        v, w = np.load(out / "v.npy"), np.load(out / "w.npy")
        lines = (out / "log.jsonl").read_text().splitlines() if (out / "log.jsonl").exists() else []
        done = json.loads(lines[-1])["it"] if lines else 0
        print(f"resuming at iteration {done}", flush=True)
    else:
        v, w = init_point(obj, args.seed)
    wsc = float(np.abs(w).mean())
    nv = v.size
    t0 = time.time()
    state = {"n": done}

    def unpack(x: Any) -> tuple[Any, Any]:
        return x[:nv].reshape(v.shape), x[nv:].reshape(w.shape) * wsc

    def fg(x: Any) -> tuple[float, Any]:
        vv, ww = unpack(x)
        f, gv, gw = obj.value_grad(vv, ww)
        return f * 1e3, np.concatenate([gv.ravel(), gw.ravel() * wsc]) * 1e3

    def save(x: Any) -> float:
        vv, ww = unpack(x)
        e2 = obj.error2(vv, ww)
        np.save(out / "v.tmp.npy", vv)
        np.save(out / "w.tmp.npy", ww)
        os.replace(out / "v.tmp.npy", out / "v.npy")
        os.replace(out / "w.tmp.npy", out / "w.npy")
        with (out / "log.jsonl").open("a") as fh:
            fh.write(json.dumps({"it": state["n"], "error_2": e2, "secs": round(time.time() - t0, 1)}) + "\n")
        print(f"it {state['n']} error_2={e2:.5f} t={time.time() - t0:.0f}s", flush=True)
        return e2

    def cb(x: Any) -> None:
        state["n"] += 1
        if state["n"] % args.checkpoint_every == 0:
            save(x)

    x0 = np.concatenate([v.ravel(), w.ravel() / wsc])
    res = minimize(
        fg,
        x0,
        jac=True,
        method="L-BFGS-B",
        callback=cb,
        options={"maxiter": max(args.iters - done, 1), "maxcor": args.maxcor},
    )
    return save(res.x)


def main(argv: list[str] | None = None) -> None:
    args = parse(argv)
    set_threads(args.threads)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    print(f"done error_2={run(args):.5f}", flush=True)


if __name__ == "__main__":
    main()
