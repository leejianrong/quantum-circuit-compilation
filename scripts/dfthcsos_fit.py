"""Cache the dfthcsos fit target. Needs the competition data (not committed).

    QCC_DATA=<data dir> uv run python scripts/dfthcsos_fit.py <out dir>

Writes ``<out dir>/tsym.npy``: the FCIDUMP integrals plus the fixed symmetry shift on the symmetric-pair
space. The fit itself is ``scripts/run_fit.py``. See docs/experiments/dfthcsos-codesign.md.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

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


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    build_tsym(out)


if __name__ == "__main__":
    main()
