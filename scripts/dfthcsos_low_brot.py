"""Experiment code for QCC-38 / QCC-15: round the dfthcsos angle words to fewer bits.

Not part of the harness; it needs the competition data and a public dfthcsos submission directory
(neither is committed). See docs/experiments/dfthcsos-low-brot.md for what it found.

    QCC_DATA=<data dir> uv run python scripts/dfthcsos_low_brot.py check  <sub dir> 7
    QCC_DATA=<data dir> uv run python scripts/dfthcsos_low_brot.py round  <sub dir> 7 <out dir> [iters]
    QCC_DATA=<data dir> uv run python scripts/dfthcsos_low_brot.py finish <sub dir> 7 <out dir>

`round` runs progressive rounding of the two-body words (continuous fit of angles and weights, then
fixing the words closest to the grid in stages and re-fitting the rest) against a surrogate of
`error_2` that agrees with the verifier to 8 digits. `finish` refits the 76 one-body rows to the
eigenvectors of the decoded h1_prime (nearest rounding, then coordinate descent on `error_1`) and
writes `<out dir>/submission.npz`. Build circuits with the host's
`example_submission/angle_k_reference_circuit.py` and check them with `bench verify`.
"""

from __future__ import annotations

import dataclasses
import os
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

DATA = Path(os.environ.get("QCC_DATA", "data"))
sys.path += [str(DATA / "kickmix"), str(DATA / "verifiers")]
from dfthcsos.scoreinfra.dfthc_math import build_h1_prime, reconstruct_u_vectors, reconstruct_x  # noqa: E402
from dfthcsos.verify import evaluate_words, load_inputs  # noqa: E402

N = 76


class Problem:
    def __init__(self, sub_dir: Path, brot: int) -> None:
        self.brot = brot
        self.npz = np.load(sub_dir / "submission.npz")
        self.edges = self.npz["tree_edges"]
        self.words8 = self.npz["angle_words"].astype(np.int64)
        self.inp = load_inputs(sub_dir / "submission.npz")
        self.R, self.B, self.C = self.inp.w.shape
        self.RB = self.R * self.B
        tei = np.array(self.inp.ref["tei"], dtype=np.float64)  # a copy: the verifier's own array stays intact
        s = np.asarray(self.inp.S, dtype=np.float64)
        d = np.arange(N)
        tei[:, :, d, d] += 0.5 * s[:, :, None]
        tei[d, d, :, :] += 0.5 * s[None, :, :]
        self.tmat = tei.reshape(N * N, N * N)  # (S x I + I x S)/2 + (pq|rs), as a matrix
        self.t2 = float(np.sum(self.tmat * self.tmat))

    # decoding and its adjoint ------------------------------------------------------------
    def decode(self, x: np.ndarray) -> np.ndarray:
        th = np.pi * x / 2 ** (self.brot - 1)
        v = np.zeros((len(x), N))
        v[:, 0] = 1.0
        for t, (p, c) in enumerate(self.edges):
            co, si = np.cos(th[:, t]), np.sin(th[:, t])
            vp, vc = v[:, p].copy(), v[:, c].copy()
            v[:, p], v[:, c] = co * vp - si * vc, si * vp + co * vc
        return v

    def backprop(self, x: np.ndarray, gv: np.ndarray) -> np.ndarray:
        th = np.pi * x / 2 ** (self.brot - 1)
        v, g, gth = self.decode(x), gv.copy(), np.zeros_like(x)
        for t in range(74, -1, -1):
            p, c = self.edges[t]
            co, si = np.cos(th[:, t]), np.sin(th[:, t])
            npv, ncv = v[:, p].copy(), v[:, c].copy()
            gth[:, t] = -g[:, p] * ncv + g[:, c] * npv
            gp, gc = g[:, p].copy(), g[:, c].copy()
            g[:, p], g[:, c] = co * gp + si * gc, -si * gp + co * gc
            v[:, p], v[:, c] = co * npv + si * ncv, -si * npv + co * ncv
        return gth * np.pi / 2 ** (self.brot - 1)

    # error_2^2 as a quartic form in the vectors, through Gram matrices ---------------------
    def value_grad(self, x: np.ndarray, w: np.ndarray, need_x: bool = True):
        u = self.decode(x)
        z = (u[:, :, None] * u[:, None, :]).reshape(self.RB, N * N)
        g = u @ u.T
        h = g**2
        vm = np.zeros((self.RB, self.R * self.C))
        for r in range(self.R):
            vm[r * self.B : (r + 1) * self.B, r * self.C : (r + 1) * self.C] = w[r]
        p = vm.T @ h @ vm
        gw_full = 4 * (h @ vm) @ p
        lin, gw = 0.0, np.zeros_like(w)
        sm = np.empty((self.RB, N, N))
        for r in range(self.R):
            sl = slice(r * self.B, (r + 1) * self.B)
            tz = z[sl] @ self.tmat
            tt = tz @ z[sl].T
            vr = vm[sl, r * self.C : (r + 1) * self.C]
            lin += float(np.einsum("ik,ij,jk->", vr, tt, vr))
            gw[r] = -4 * (tt @ vr) + gw_full[sl, r * self.C : (r + 1) * self.C]
            if need_x:
                sm[sl] = ((vr @ vr.T) @ tz).reshape(self.B, N, N)
        f = self.t2 - 2 * lin + float(np.sum(p * p))
        if not need_x:
            return f, None, gw
        kmat = 2 * vm @ p @ vm.T
        gu = 4 * (g * kmat) @ u - 8 * np.einsum("bpq,bq->bp", sm, u)
        return f, self.backprop(x, gu), gw

    def optimize(self, x, w, free, iters, tag):
        wsc = np.abs(w).mean()
        idx = np.flatnonzero(free.ravel())

        def unpack(v):
            xx = x.copy().ravel()
            xx[idx] = v[: len(idx)]
            return xx.reshape(x.shape), v[len(idx) :].reshape(w.shape) * wsc

        def fg(v):
            xx, ww = unpack(v)
            f, gx, gw = self.value_grad(xx, ww)
            return f * 1e3, np.concatenate([gx.ravel()[idx], gw.ravel() * wsc]) * 1e3

        v0 = np.concatenate([x.ravel()[idx], w.ravel() / wsc])
        res = minimize(fg, v0, jac=True, method="L-BFGS-B", options={"maxiter": iters, "maxcor": 15})
        xx, ww = unpack(res.x)
        f = self.value_grad(xx, ww, need_x=False)[0]
        print(f"  {tag}: free={len(idx)} err2={np.sqrt(max(f, 0)):.5f}", flush=True)
        return xx, ww


def check(pb: Problem) -> None:
    x = pb.words8[N:].astype(np.float64) / 2 ** (8 - pb.brot)
    w = np.asarray(pb.inp.w, dtype=np.float64)
    f, gx, gw = pb.value_grad(x, w)
    print("error_2 of the public words:", np.sqrt(f))
    for i, j in [(5, 3), (100, 40)]:
        xp, xm = x.copy(), x.copy()
        xp[i, j] += 1e-4
        xm[i, j] -= 1e-4
        fd = (pb.value_grad(xp, w, False)[0] - pb.value_grad(xm, w, False)[0]) / 2e-4
        print("angle gradient", gx[i, j], "finite difference", fd)


def progressive_round(pb: Problem, out: Path, iters: int) -> None:
    x = pb.words8[N:].astype(np.float64) / 2 ** (8 - pb.brot)
    w = np.asarray(pb.inp.w, dtype=np.float64).copy()
    x, w = pb.optimize(x, w, np.ones(x.shape, bool), iters, "continuous")
    for phi in (0.3, 0.5, 0.7, 0.85, 0.95, 1.0):
        order = np.argsort(np.abs(x - np.rint(x)).ravel())
        fixed = np.zeros(x.size, bool)
        fixed[order[: int(phi * x.size)]] = True
        fixed = fixed.reshape(x.shape)
        x = np.where(fixed, np.rint(x), x)
        x, w = pb.optimize(x, w, ~fixed, iters, f"phi={phi}")
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / "two_body_words.npy", np.rint(x).astype(np.int64) % 2**pb.brot)
    np.save(out / "w.npy", w)


def encode(pb: Problem, vecs: np.ndarray) -> np.ndarray:
    """Angle words for unit vectors on the Givens tree, nearest rounding to the brot-bit grid."""
    v = np.array(vecs, dtype=np.float64)
    out = np.zeros((len(v), 75), dtype=np.int64)
    for t in range(74, -1, -1):
        p, c = pb.edges[t]
        th = np.arctan2(v[:, c], v[:, p])
        v[:, p], v[:, c] = np.hypot(v[:, p], v[:, c]), 0
        out[:, t] = np.rint(th / np.pi * 2 ** (pb.brot - 1)).astype(np.int64) % 2**pb.brot
    return out


def finish(pb: Problem, out: Path) -> None:
    brot = pb.brot
    two = np.load(out / "two_body_words.npy")
    w = np.load(out / "w.npy")
    inp = dataclasses.replace(pb.inp, w=w)
    u = reconstruct_u_vectors(two / 2 ** (brot - 1), pb.edges).reshape(pb.R, pb.B, N)
    x = reconstruct_x(u, w)
    x = np.tril(x) + np.swapaxes(np.tril(x, k=-1), -1, -2)
    ref = inp.ref
    h1_thc = np.asarray(ref["oei"], dtype=np.float64) - 0.5 * np.einsum("prrq->pq", np.asarray(ref["tei"]))
    hp = build_h1_prime(h1_thc, np.asarray(inp.S, dtype=np.float64), inp.beta_1, ref["electrons"], inp.W, x)
    lam, vec = np.linalg.eigh(hp)
    ones = encode(pb, vec.T)
    rm = np.einsum("j,jp,jq->pq", lam, *(2 * [reconstruct_u_vectors(ones / 2 ** (brot - 1), pb.edges)])) - hp
    print("one-body nearest rounding: error_1 =", np.linalg.norm(rm))
    for sweep in range(8):  # coordinate descent on error_1 over single-word moves
        accepted = 0
        for j in range(N):
            for t in range(75):
                v = reconstruct_u_vectors(ones[j : j + 1] / 2 ** (brot - 1), pb.edges)[0]
                cur, best = np.sum(rm * rm), None
                for d in (-2, -1, 1, 2):
                    o = ones[j : j + 1].copy()
                    o[0, t] = (o[0, t] + d) % 2**brot
                    v2 = reconstruct_u_vectors(o / 2 ** (brot - 1), pb.edges)[0]
                    dr = lam[j] * (np.outer(v2, v2) - np.outer(v, v))
                    new = cur + 2 * np.sum(rm * dr) + np.sum(dr * dr)
                    if new < cur - 1e-14 and (best is None or new < best[0]):
                        best = (new, o[0, t], dr)
                if best is not None:
                    ones[j, t], rm, accepted = best[1], rm + best[2], accepted + 1
        print(f"  sweep {sweep}: error_1 = {np.linalg.norm(rm):.5f}")
        if accepted == 0:
            break
    words = np.vstack([ones, two])
    m = evaluate_words(inp, words, pb.edges, brot)
    print("metrics:", {k: float(v) for k, v in m.items()})
    arrs = {k: pb.npz[k] for k in pb.npz.files}
    arrs.update(angle_words=words, W=w, H2_I=inp.W + w.sum(axis=1))
    np.savez(out / "submission.npz", **arrs)


def main() -> None:
    cmd, sub, brot = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3])
    pb = Problem(sub, brot)
    t0 = time.time()
    if cmd == "check":
        check(pb)
    elif cmd == "round":
        progressive_round(pb, Path(sys.argv[4]), int(sys.argv[5]) if len(sys.argv) > 5 else 40)
    elif cmd == "finish":
        finish(pb, Path(sys.argv[4]))
    print(f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
