"""Lambda proxy of a fit: 1/4 sum_(rho,c) |w_c|_1^2 before and after the min-L1 rotation of ``c`` (QCC-16).

    uv run python scripts/dfthcsos_l1_eval.py <fit dir> [--tsym out/fit/tsym.npy]

The proxy leaves out the capital-W term and ``Lambda_1`` (about 17 and 3 percent), so it tracks ``Lambda``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dfthcsos_gen.fit import Objective  # noqa: E402
from dfthcsos_gen.post import rotate_min_l1  # noqa: E402


def proxy(w: np.ndarray) -> float:
    return float(0.25 * np.sum(np.abs(w).sum(axis=1) ** 2))


def main() -> None:
    fit = Path(sys.argv[1])
    tsym = Path(sys.argv[sys.argv.index("--tsym") + 1]) if "--tsym" in sys.argv else Path("out/fit/tsym.npy")
    v, w = np.load(fit / "v.npy"), np.load(fit / "w.npy")
    err = Objective(np.load(tsym), 76, w.shape).error2(v, w)
    wr = np.stack([rotate_min_l1(w[r])[0] for r in range(w.shape[0])])
    print(f"error_2 {err:.5f}  proxy {proxy(w):.1f}  rotated {proxy(wr):.1f}")


if __name__ == "__main__":
    main()
