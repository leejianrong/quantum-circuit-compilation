"""Score a fitted (v, w) with the host's metric code: error_1, error_2, Lambda, E_gap (competition data).

    QCC_DATA=<data dir> uv run python scripts/eval_fit.py <run dir with v.npy, w.npy>
    QCC_DATA=<data dir> uv run python scripts/eval_fit.py --sample   # sanity check on the sample submission

The fit has no one-body rows and no capital ``W_rho_c``. The one-body rows are the exact eigenvectors of
``h1_prime`` (``error_1`` is zero up to rounding) and ``W = -t * sum_b w`` is scanned over ``t``: ``W`` moves
``Lambda`` and ``E_gap`` but not ``error_2``. Gates: Lambda > 49.0, E_gap > 3.914898, errors < 0.02.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

DATA = Path(os.environ.get("QCC_DATA", "data"))
sys.path += [str(DATA / "verifiers")]


def metrics(inp, u_two: np.ndarray, w: np.ndarray, cap_w: np.ndarray) -> dict:  # type: ignore[no-untyped-def]
    from dfthcsos.scoreinfra import dfthc_math as dm

    n = inp.num_orbitals
    u = u_two / np.linalg.norm(u_two, axis=-1, keepdims=True)
    x = dm.reconstruct_x(u, w)
    x = np.tril(x) + np.swapaxes(np.tril(x, k=-1), -1, -2)
    h1_thc = inp.ref["oei"] - 0.5 * np.einsum("prrq->pq", inp.ref["tei"])
    h1p = dm.build_h1_prime(h1_thc, inp.S, inp.beta_1, inp.ref["electrons"], cap_w, x)
    one_body = np.linalg.eigh(h1p)[1].T
    all_u = np.vstack([one_body, u.reshape(-1, n)])
    return dm.evaluate_dfthc_vectors(
        all_u, w, cap_w, inp.S, inp.beta_1, inp.ref, energy_upper=inp.energy_upper
    )


def main() -> None:
    from dfthcsos.verify import load_inputs

    sample = DATA / "sample_submission" / "dfthcsos" / "submission.npz"
    inp = load_inputs(sample)
    if sys.argv[1] == "--sample":
        z = np.load(sample)
        res = metrics(inp, z["U"][:, :, :], inp.w, inp.W)
        print("sample submission with its own W:", {k: round(float(v), 6) for k, v in res.items()})
        return
    run = Path(sys.argv[1])
    v, w = np.load(run / "v.npy"), np.load(run / "w.npy")
    r, b, c = w.shape
    u_two = v.reshape(r, b, -1)
    print(f"shape {w.shape}")
    for t in (0.0, 0.5, 1.0, 1.5, 2.0, 3.0):
        cap_w = -t * w.sum(axis=1)
        res = metrics(inp, u_two, w, cap_w)
        print(f"t={t}: " + " ".join(f"{k}={float(v):.6g}" for k, v in res.items() if k != "gap_in_domain"))


if __name__ == "__main__":
    main()
