"""Width profile of an invsqrt kmx text: how many qubits are live at each step (S2, 43-qubit line, QCC-61).

The text is a classical reversible circuit with phase gates, measure-and-reset (``HMR``) and classically
conditioned gates. We run it on sampled inputs ``x`` in ``[1, 3,133,452]`` (log-uniform, so every normaliser
shift occurs) with the outcome of each ``HMR`` drawn at random. A qubit is *live* at a step if it is nonzero
for any sample, or is one of the 22 input qubits. The union over samples can only miss states, so the profile
is a lower bound on the true width; a step counted live is certainly occupied.

    width.py FILE.kmx [--samples N] [--seed S]
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass

import numpy as np

MAX_X = 3_133_452
INPUT_QUBITS = 22


@dataclass
class Profile:
    width: np.ndarray  # live qubits after each op
    ops: list[str]
    n_qubits: int
    live_sets: dict[int, np.ndarray]  # op index -> bool array of live qubits, only at peak steps


def sample_inputs(n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    xs = np.exp(rng.uniform(0.0, np.log(MAX_X), n)).astype(np.int64)
    xs[: min(3, n)] = [1, MAX_X, 1 << 20][: min(3, n)]
    return np.clip(xs, 1, MAX_X)


def profile(text: str, samples: int = 256, seed: int = 0) -> Profile:
    lines = [ln.split() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    nq = 1 + max(int(t[1:]) for ln in lines for t in ln if re.fullmatch(r"q\d+", t))
    nb = 1 + max((int(t[1:]) for ln in lines for t in ln if re.fullmatch(r"b\d+", t)), default=0)
    rng = np.random.default_rng(seed + 1)
    xs = sample_inputs(samples, seed)
    q = np.zeros((nq, samples), dtype=bool)
    for i in range(INPUT_QUBITS):
        q[i] = (xs >> i) & 1 == 1
    b = np.zeros((nb, samples), dtype=bool)
    stack: list[np.ndarray] = []
    ones = np.ones(samples, dtype=bool)
    width: list[int] = []
    ops: list[str] = []
    peak_sets: list[tuple[int, np.ndarray]] = []
    ever = np.zeros(nq, dtype=bool)
    ever[:INPUT_QUBITS] = True
    for ln in lines:
        op, args = ln[0], ln[1:]
        if op == "PUSH_CONDITION":
            stack.append(b[int(args[1][1:])].copy())
            continue
        if op == "POP_CONDITION":
            stack.pop()
            continue
        cond = args[-1] if len(args) >= 2 and args[-2] == "if" else None
        if cond is not None:
            args = args[:-2]
        mask = ones.copy()
        for s in stack:
            mask &= s
        if cond is not None:
            mask &= b[int(cond[1:])]
        qs = [int(a[1:]) for a in args if re.fullmatch(r"q\d+", a)]
        if op == "X":
            q[qs[0]] ^= mask
        elif op == "CX":
            q[qs[1]] ^= q[qs[0]] & mask
        elif op == "CCX":
            q[qs[2]] ^= q[qs[0]] & q[qs[1]] & mask
        elif op == "SWAP":
            d = (q[qs[0]] ^ q[qs[1]]) & mask
            q[qs[0]] ^= d
            q[qs[1]] ^= d
        elif op == "CSWAP":
            d = (q[qs[1]] ^ q[qs[2]]) & q[qs[0]] & mask
            q[qs[1]] ^= d
            q[qs[2]] ^= d
        elif op == "HMR":
            bit = rng.random(samples) < 0.5
            q[qs[0]] = np.where(mask, False, q[qs[0]])
            b[int(args[1][1:])] = np.where(mask, bit, b[int(args[1][1:])])
        elif op in ("BIT_STORE0", "BIT_STORE1"):
            b[int(args[0][1:])] = np.where(mask, op == "BIT_STORE1", b[int(args[0][1:])])
        elif op == "BIT_INVERT":
            b[int(args[0][1:])] ^= mask
        live = q.any(axis=1)
        live[:INPUT_QUBITS] = True
        ever |= live
        width.append(int(live.sum()))
        ops.append(ln[0])
        peak_sets.append((len(width) - 1, live.copy()))
    w = np.array(width)
    top = int(w.max())
    keep = {i: s for i, s in peak_sets if w[i] >= top - 1}
    return Profile(w, ops, nq, keep)


def segments(width: np.ndarray, level: int) -> list[tuple[int, int]]:
    """Maximal runs of steps with width >= ``level``."""
    out: list[tuple[int, int]] = []
    start = None
    for i, v in enumerate(width):
        if v >= level and start is None:
            start = i
        elif v < level and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(width) - 1))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("kmx")
    ap.add_argument("--samples", type=int, default=256)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    from pathlib import Path

    p = profile(Path(a.kmx).read_text(), a.samples, a.seed)
    top = int(p.width.max())
    print(f"qubits {p.n_qubits}, steps {len(p.width)}, peak width {top}")
    for lvl in (top, top - 1, top - 2):
        segs = segments(p.width, lvl)
        total = sum(e - s + 1 for s, e in segs)
        print(f"width >= {lvl}: {len(segs)} segments, {total} steps ({100 * total / len(p.width):.1f}%)")
    hist = np.bincount(p.width)
    print("steps per width:", {int(i): int(c) for i, c in enumerate(hist) if c and i >= top - 8})


if __name__ == "__main__":
    main()
