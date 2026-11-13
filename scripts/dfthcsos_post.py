"""From a fitted (v, w) to a submission directory: rotate, fit the capital W, quantize, score, write (QCC-16).

    QCC_DATA=<data dir> uv run python scripts/dfthcsos_post.py <fit dir with v.npy w.npy> <out dir> \
        [--brot 10] [--tree balanced|path] [--no-rotate]

Steps (all ours, see docs/experiments/dfthcsos-structured.md):
1. per rho, rotate the ``c`` index to shrink the column one-norms of ``w`` (``error_2`` is invariant);
2. choose the capital ``W`` (R x C) to minimise ``lambda_eff`` with ``E_gap`` just above its floor;
3. encode every vector on the Givens tree at ``brot`` bits (one-body rows from the decoded ``h1_prime``),
   decode, and report the verifier's metrics on the words;
4. write ``angle_k_*.kmb`` (our unary loader) and ``submission.npz`` for ``bench verify``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

DATA = Path(os.environ.get("QCC_DATA", "data"))
sys.path += [str(DATA / "verifiers")]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

E_FLOOR = 3.914898


class Ctx:
    def __init__(self, sample: Path) -> None:
        from dfthcsos.verify import load_inputs

        self.inp = load_inputs(sample)
        self.ref = self.inp.ref
        n = self.inp.num_orbitals
        self.n = n
        tei = np.asarray(self.ref["tei"], dtype=np.float64)
        h1_thc = np.asarray(self.ref["oei"], dtype=np.float64) - 0.5 * np.einsum("prrq->pq", tei)
        self.base = (
            h1_thc
            - 0.5 * self.ref["electrons"] * np.asarray(self.inp.S, dtype=np.float64)
            + self.inp.beta_1 * np.eye(n)
        )
        self.const = (
            self.inp.energy_upper - self.ref["ecore"] + self.ref["electrons"] * self.inp.beta_1
        )  # E_gap = const + 2 sum(neg eig) + W^2/2


def xmats(u: np.ndarray, w: np.ndarray) -> np.ndarray:
    from dfthcsos.scoreinfra import dfthc_math as dm

    x = dm.reconstruct_x(u, w)
    return np.tril(x) + np.swapaxes(np.tril(x, k=-1), -1, -2)


def fit_cap_w(
    ctx: Ctx, x: np.ndarray, w: np.ndarray, margin: float = 2e-4
) -> tuple[np.ndarray, dict[str, float]]:
    """Minimise ``lambda_eff`` over ``W (R, C)`` with ``E_gap >= floor + margin``."""
    r, b, c = w.shape
    xf = x.reshape(r * c, -1)
    ws = w.sum(axis=1)
    w1 = np.abs(w).sum(axis=1)

    def parts(wc: np.ndarray) -> tuple[float, float, np.ndarray, np.ndarray]:
        h1p = ctx.base - np.einsum("k,kpq->pq", wc, x.reshape(r * c, ctx.n, ctx.n))
        ev, vec = np.linalg.eigh(h1p)
        lam1 = np.abs(ev).sum()
        neg = -ev[ev < 0].sum()
        wb = wc + ws.ravel()
        lam2 = 0.25 * np.sum((w1.ravel() + np.abs(wb)) ** 2)
        lam = lam1 + lam2
        gap = ctx.const + 2 * neg + 0.5 * np.sum(wc**2)
        sg = (vec * np.sign(ev)) @ vec.T  # d lam1 / d h1p
        sn = (vec * (ev < 0)) @ vec.T  # d neg / d h1p = -sum over neg vectors
        dl1 = -(xf @ sg.ravel())
        dneg = xf @ sn.ravel()  # neg = -sum_{ev<0} ev -> d/dW = +<P_neg, X>
        dl2 = 0.5 * (w1.ravel() + np.abs(wb)) * np.sign(wb)
        dgap = 2 * dneg + wc
        return lam, gap, dl1 + dl2, dgap

    def f(wc: np.ndarray) -> tuple[float, np.ndarray]:
        lam, gap, dlam, dgap = parts(wc)
        rad = gap * (2 * lam - gap)
        le = np.sqrt(max(rad, 1e-12))
        return le, (dgap * (2 * lam - gap) + gap * (2 * dlam - dgap)) / (2 * le)

    def gcon(wc: np.ndarray) -> tuple[float, np.ndarray]:
        _, gap, _, dgap = parts(wc)
        return gap - E_FLOOR - margin, dgap

    best = None
    for t in (1.0,):
        w0 = -t * ws.ravel()
        res = minimize(
            lambda z: f(z)[0],
            w0,
            jac=lambda z: f(z)[1],
            method="SLSQP",
            constraints=[{"type": "ineq", "fun": lambda z: gcon(z)[0], "jac": lambda z: gcon(z)[1]}],
            options={"maxiter": 300, "ftol": 1e-10},
        )
        lam, gap, _, _ = parts(res.x)
        ok = gap > E_FLOOR + 1e-5
        le = f(res.x)[0]
        print(
            f"  W fit start t={t}: lambda_eff={le:.3f} Lambda={lam:.1f} E_gap={gap:.6f} ok={ok}", flush=True
        )
        if ok and (best is None or le < best[0]):
            best = (le, res.x, lam, gap)
    if best is None:
        raise RuntimeError("no feasible capital W")
    return best[1].reshape(r, c), {"lambda_eff": best[0], "Lambda": best[2], "E_gap": best[3]}


def refit_w(tsym: np.ndarray, uq: np.ndarray, w: np.ndarray, iters: int) -> np.ndarray:
    """Quantization-aware step: with the decoded vectors fixed, re-optimise the weights on ``error_2``."""
    from dfthcsos_gen.fit import Objective

    r, b, c = w.shape
    obj = Objective(tsym, uq.shape[-1], (r, b, c))
    v = uq.reshape(r * b, -1)
    sc = float(np.abs(w).mean())

    def fg(x: np.ndarray) -> tuple[float, np.ndarray]:
        f, _, gw = obj.value_grad(v, x.reshape(w.shape) * sc, need_v=False)
        return f * 1e3, gw.ravel() * sc * 1e3

    res = minimize(fg, w.ravel() / sc, jac=True, method="L-BFGS-B", options={"maxiter": iters, "maxcor": 30})
    return np.asarray(res.x.reshape(w.shape) * sc)


def build(ctx: Ctx, tsym, u, w0, edges, brot, iters, rotate, half=False, l1_target=0.0):  # type: ignore[no-untyped-def]
    from dfthcsos.scoreinfra import dfthc_math as dm

    from dfthcsos_gen import post

    r, b, _ = w0.shape
    two = post.encode(u.reshape(r * b, -1), edges, brot, half)
    uq = post.decode(two, edges, brot).reshape(r, b, -1)
    w = refit_w(tsym, uq, w0, iters) if iters else w0.copy()
    if l1_target:  # spend the error slack below the gate on a smaller Lambda
        from dfthcsos_gen.fit_fast import FastObjective
        from dfthcsos_gen.fit_varpro import refit_w_l1

        w, e2, mu = refit_w_l1(
            FastObjective(tsym, uq.shape[-1], w.shape), uq.reshape(r * b, -1), w, l1_target
        )
        print(f"  L1 refit: mu {mu:.2e}, error_2 {e2:.5f}", flush=True)
    if rotate:
        for k in range(r):
            w[k], _ = post.rotate_min_l1(w[k], iters=300)
    w = w.astype(np.float32).astype(np.float64)
    cap_w, _ = fit_cap_w(ctx, xmats(uq, w), w)
    h2i = (cap_w + w.sum(axis=1)).astype(np.float32)  # stored as H2_I = W + sum_b w
    cap_w = h2i.astype(np.float64) - w.sum(axis=1)
    h1_thc = np.asarray(ctx.ref["oei"]) - 0.5 * np.einsum("prrq->pq", np.asarray(ctx.ref["tei"]))
    h1p = dm.build_h1_prime(h1_thc, ctx.inp.S, ctx.inp.beta_1, ctx.ref["electrons"], cap_w, xmats(uq, w))
    one = post.encode(np.linalg.eigh(h1p)[1].T, edges, brot, half)
    words = np.vstack([one, two])
    res = dm.evaluate_dfthc_angle_words(
        words,
        w,
        cap_w,
        ctx.inp.S,
        ctx.inp.beta_1,
        ctx.ref,
        brot=brot,
        tree_edges=edges,
        energy_upper=ctx.inp.energy_upper,
    )
    return words, res, w, h2i


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("fit", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--tsym", type=Path, default=Path("out/fit/tsym.npy"))
    ap.add_argument("--brot", default="10", help="comma list; the first is written")
    ap.add_argument("--tree", default="balanced", help="comma list of balanced|path; the first is written")
    ap.add_argument("--refit-iters", type=int, default=300, help="quantization-aware weight refit (0 = off)")
    ap.add_argument("--no-rotate", action="store_true")
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument(
        "--l1-target", type=float, default=0.0, help="refit weights for a small L1 proxy at this error_2"
    )
    ap.add_argument(
        "--half", action="store_true", help="angles in the half circle (bit brot-1 == bit brot-2)"
    )
    ap.add_argument("--loader", default="unary", choices=("unary", "anf"), help="loader family to write")
    a = ap.parse_args()
    from dfthcsos_gen import post

    ctx = Ctx(DATA / "sample_submission" / "dfthcsos" / "submission.npz")
    tsym = np.load(a.tsym)
    v, w0 = np.load(a.fit / "v.npy"), np.load(a.fit / "w.npy")
    r, b, c = w0.shape
    u = (v / np.linalg.norm(v, axis=1, keepdims=True)).reshape(r, b, -1)
    first = None
    for tn in a.tree.split(","):
        edges = post.balanced_tree() if tn == "balanced" else post.path_tree()
        for bs in a.brot.split(","):
            words, res, w, h2i = build(
                ctx, tsym, u, w0, edges, int(bs), a.refit_iters, not a.no_rotate, a.half, a.l1_target
            )
            print(
                f"tree={tn} brot={bs}:",
                json.dumps(
                    {k: (round(float(vv), 6) if not isinstance(vv, bool) else vv) for k, vv in res.items()}
                ),
                flush=True,
            )
            first = first or (words, res, edges, int(bs), w, h2i)
    words, res, edges, a.brot, w, h2i = first
    if a.no_write:
        return
    from dfthcsos_gen import build_family, family_stats, write_family
    from dfthcsos_gen.loader import max_words_per_circuit

    J = max_words_per_circuit(words.shape[0], a.brot)
    if a.loader == "anf":
        from dfthcsos_gen.anf import build_anf_family, max_words
        from dfthcsos_model import Angles, score

        best = None
        for lb in (4, 5, 6):
            j = max_words(words.shape[0], a.brot, lb)
            if j < 1:
                continue
            fam = build_anf_family(words, a.brot, j, lb, sign_ext=a.half)
            s_ = family_stats(fam)
            sc = score(
                (r, b, c),
                Angles(toffoli=2 * s_["toffoli"], qubits=s_["qubits"], J=j, brot=a.brot),
                res["Lambda"],
                res["E_gap"],
            ).score
            print(f"anf lb={lb} J={j}: {s_} predicted cost {sc:,.0f}", flush=True)
            if best is None or sc < best[0]:
                best = (sc, fam, j)
        assert best is not None
        _, circ, J = best
    else:
        circ = build_family(words, a.brot)
    write_family(circ, a.out)
    st = family_stats(circ)
    z = np.load(DATA / "sample_submission" / "dfthcsos" / "submission.npz")
    np.savez(
        a.out / "submission.npz",
        U=np.zeros((r, b, 76), np.float32),
        W=w.astype(np.float32),
        H2_I=h2i,
        H1_I=z["H1_I"],
        Hsym_lower=z["Hsym_lower"],
        tree_edges=edges,
        angle_words=words,
    )
    from dfthcsos_model import Angles, score

    bd = score(
        (r, b, c),
        Angles(toffoli=2 * st["toffoli"], qubits=st["qubits"], J=J, brot=a.brot),
        res["Lambda"],
        res["E_gap"],
    )
    print(f"stats {st} J={J}; predicted cost {bd.score:,.0f} ratio {3355599588.3155 / bd.score:.2f}")


if __name__ == "__main__":
    main()
