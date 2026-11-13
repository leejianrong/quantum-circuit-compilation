"""GPU (or CPU) torch version of scripts/run_fit.py: same objective, autograd gradients, L-BFGS on one device.

    python scripts/run_fit_gpu.py --tsym tsym.npy --shape 8 143 44 --init-from fit/8x143x44 --iters 100000 \
        --out fit/gpu_8x143x44 --max-secs 40000

The objective is ``error_2^2 = |T|^2 - 2 sum_{rho c} w_rc^T (Z_rho T Z_rho^T) w_rc + |V^T H V|_F^2`` of
``src/dfthcsos_gen/fit.py`` written with torch float64 tensors (float32 loses the 3e-6 relative signal), so the
two matrix products with ``T`` (``RB x M @ M x M``) run on the GPU. The test in
``tests/unit/test_dfthcsos_fit_torch.py`` pins it to the numpy objective. Checkpoints (``v.npy``, ``w.npy``,
``log.jsonl``) have the same layout as ``run_fit.py`` so either script can resume the other's run.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any


def make_loss(tsym: Any, n: int, shape: tuple[int, int, int], device: str) -> Any:
    import numpy as np
    import torch

    r_, b_, c_ = shape
    t = torch.as_tensor(np.ascontiguousarray(tsym), dtype=torch.float64, device=device)
    t2 = float((t * t).sum())
    p, q = np.triu_indices(n)
    scale = torch.as_tensor(np.where(p == q, 1.0, np.sqrt(2.0)), dtype=torch.float64, device=device)
    pi, qi = torch.as_tensor(p, device=device), torch.as_tensor(q, device=device)

    def loss(v: Any, w: Any) -> Any:
        u = v / torch.linalg.norm(v, dim=1, keepdim=True)
        z = u[:, pi] * u[:, qi] * scale  # (RB, M)
        h = (u @ u.T) ** 2
        lin = 0.0
        pm = 0.0
        # V^T H V is block-sparse in V: assemble the (R C) x (R C) Gram of the weighted squares
        zr = z.reshape(r_, b_, -1)
        for r in range(r_):
            tz = zr[r] @ t  # (B, M)
            tt = tz @ zr[r].T  # (B, B)
            lin = lin + torch.einsum("bc,bd,dc->", w[r], tt, w[r])
        vm_blocks = [w[r] for r in range(r_)]
        hb = h.reshape(r_, b_, r_, b_)
        rows = []
        for r in range(r_):
            rows.append(torch.cat([vm_blocks[r].T @ hb[r, :, s, :] @ vm_blocks[s] for s in range(r_)], dim=1))
        pm = torch.cat(rows, dim=0)
        return t2 - 2 * lin + (pm * pm).sum()

    return loss


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tsym", type=Path, required=True)
    ap.add_argument("--shape", type=int, nargs=3, default=(8, 143, 44))
    ap.add_argument("--init-from", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--iters", type=int, default=100000)
    ap.add_argument("--max-secs", type=float, default=0.0)
    ap.add_argument("--checkpoint-every", type=int, default=200)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--history", type=int, default=30)
    a = ap.parse_args()
    import numpy as np
    import torch

    dev = a.device if (a.device != "cuda" or torch.cuda.is_available()) else "cpu"
    print("device", dev, torch.cuda.get_device_name(0) if dev == "cuda" else "", flush=True)
    tsym = np.load(a.tsym)
    n = round((np.sqrt(8 * tsym.shape[0] + 1) - 1) / 2)
    shape = tuple(a.shape)
    loss = make_loss(tsym, n, shape, dev)  # type: ignore[arg-type]
    a.out.mkdir(parents=True, exist_ok=True)
    src = a.out if (a.out / "v.npy").exists() else a.init_from
    v0, w0 = np.load(src / "v.npy"), np.load(src / "w.npy")
    assert w0.shape == shape, (w0.shape, shape)
    done = 0
    if (a.out / "log.jsonl").exists():
        lines = (a.out / "log.jsonl").read_text().splitlines()
        done = json.loads(lines[-1])["it"] if lines else 0
    wsc = float(np.abs(w0).mean())
    v = torch.nn.Parameter(torch.as_tensor(v0, dtype=torch.float64, device=dev))
    w = torch.nn.Parameter(torch.as_tensor(w0 / wsc, dtype=torch.float64, device=dev))
    opt = torch.optim.LBFGS(
        [v, w],
        lr=1.0,
        max_iter=20,
        history_size=a.history,
        line_search_fn="strong_wolfe",
        tolerance_grad=0,
        tolerance_change=0,
    )
    t0 = time.time()
    it = done

    def closure() -> Any:
        opt.zero_grad()
        f = loss(v, w * wsc) * 1e3
        f.backward()
        return f

    def save() -> float:
        with torch.no_grad():
            e2 = float(loss(v, w * wsc).clamp(min=0).sqrt())
        np.save(a.out / "v.tmp.npy", v.detach().cpu().numpy())
        np.save(a.out / "w.tmp.npy", (w.detach() * wsc).cpu().numpy())
        os.replace(a.out / "v.tmp.npy", a.out / "v.npy")
        os.replace(a.out / "w.tmp.npy", a.out / "w.npy")
        with (a.out / "log.jsonl").open("a") as fh:
            fh.write(json.dumps({"it": it, "error_2": e2, "secs": round(time.time() - t0, 1)}) + "\n")
        print(f"it {it} error_2={e2:.5f} t={time.time() - t0:.0f}s", flush=True)
        return e2

    while it < a.iters:
        opt.step(closure)
        it += 20
        if it % a.checkpoint_every < 20:
            save()
        if a.max_secs and time.time() - t0 > a.max_secs:
            break
    print(f"done error_2={save():.5f}", flush=True)


if __name__ == "__main__":
    main()
