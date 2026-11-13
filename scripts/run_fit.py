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
    ap.add_argument(
        "--init-from", type=Path, help="start from another run's v.npy, w.npy; padded up to --shape"
    )
    ap.add_argument(
        "--l1", type=float, default=0.0, help="weight of 1/4 sum_(rho,c) |w_c|_1^2 (Lambda proxy)"
    )
    ap.add_argument(
        "--init", choices=("random", "compact"), default="random", help="start point (compact: seed.py)"
    )
    ap.add_argument("--max-secs", type=float, default=0.0, help="stop (and save) after this wall time")
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


def grow(v0: Any, w0: Any, shape: tuple[int, int, int], seed: int) -> tuple[Any, Any]:
    """Pad a fit to a larger shape: new ``c`` columns and new ``b`` rows start small but nonzero."""
    import numpy as np

    rng = np.random.default_rng(seed)
    r, b, c = shape
    r0, b0, c0 = w0.shape
    assert r == r0 and b >= b0 and c >= c0
    amp = 0.05 * float(np.abs(w0).mean())
    w = rng.normal(size=(r, b, c)) * amp
    w[:, :b0, :c0] = w0
    v = rng.normal(size=(r * b, v0.shape[1])) * float(
        np.linalg.norm(v0, axis=1).mean() / np.sqrt(v0.shape[1])
    )
    v3 = v.reshape(r, b, -1)
    v3[:, :b0] = v0.reshape(r0, b0, -1)
    return v3.reshape(r * b, -1), w


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
    elif args.init_from is not None:
        v, w = grow(
            np.load(args.init_from / "v.npy"), np.load(args.init_from / "w.npy"), (r, b, c), args.seed
        )
    elif args.init == "compact":
        from dfthcsos_gen.seed import compact_seed

        v, w = compact_seed(obj, (r, b, c), args.seed)
        print(f"compact seed error_2={obj.error2(v, w):.5f}", flush=True)
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
        if args.l1:
            phi = np.sqrt(ww * ww + 1e-8 * wsc * wsc)
            a1 = phi.sum(axis=1, keepdims=True)  # (R, 1, C): |w_c|_1 per (rho, c)
            f = f + args.l1 * 0.25 * float(np.sum(a1 * a1))
            gw = gw + args.l1 * 0.5 * a1 * ww / phi
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
        if args.max_secs and time.time() - t0 > args.max_secs:
            raise StopIteration

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
