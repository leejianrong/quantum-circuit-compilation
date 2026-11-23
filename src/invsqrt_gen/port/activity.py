"""Which Toffoli-class gates ever fire? (search harness stage 1b, QCC-61)

Runs the kmx text on every input of the domain (in chunks) with random HMR outcomes and counts, per
CCX/CCZ/CSWAP, the (input, outcome) samples on which the gate's enclosing conditions hold. A gate with
zero count over the whole domain sits on a branch that never runs; the exact proof is still the gate.

    activity.py FILE.kmx [--chunk N] [--limit N]
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np

from invsqrt_gen.port.width import INPUT_QUBITS, MAX_X


def activity(text: str, xs: np.ndarray, seed: int = 0) -> dict[int, int]:
    lines = [ln.split() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    nq = 1 + max(int(t[1:]) for ln in lines for t in ln if re.fullmatch(r"q\d+", t))
    nb = 1 + max((int(t[1:]) for ln in lines for t in ln if re.fullmatch(r"b\d+", t)), default=0)
    n = len(xs)
    rng = np.random.default_rng(seed + 1)
    q = np.zeros((nq, n), dtype=bool)
    for i in range(INPUT_QUBITS):
        q[i] = (xs >> i) & 1 == 1
    b = np.zeros((nb, n), dtype=bool)
    stack: list[np.ndarray] = []
    ones = np.ones(n, dtype=bool)
    out: dict[int, int] = {}
    for idx, ln in enumerate(lines):
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
        mask = ones
        for s in stack:
            mask = mask & s
        if cond is not None:
            mask = mask & b[int(cond[1:])]
        qs = [int(a[1:]) for a in args if re.fullmatch(r"q\d+", a)]
        if op == "X":
            q[qs[0]] ^= mask
        elif op == "CX":
            q[qs[1]] ^= q[qs[0]] & mask
        elif op == "CCX":
            out[idx] = int(mask.sum())
            q[qs[2]] ^= q[qs[0]] & q[qs[1]] & mask
        elif op == "CCZ":
            out[idx] = int(mask.sum())
        elif op == "SWAP":
            d = (q[qs[0]] ^ q[qs[1]]) & mask
            q[qs[0]] ^= d
            q[qs[1]] ^= d
        elif op == "CSWAP":
            out[idx] = int(mask.sum())
            d = (q[qs[1]] ^ q[qs[2]]) & q[qs[0]] & mask
            q[qs[1]] ^= d
            q[qs[2]] ^= d
        elif op == "HMR":
            bit = rng.random(n) < 0.5
            q[qs[0]] = np.where(mask, False, q[qs[0]])
            b[int(args[1][1:])] = np.where(mask, bit, b[int(args[1][1:])])
        elif op in ("BIT_STORE0", "BIT_STORE1"):
            b[int(args[0][1:])] = np.where(mask, op == "BIT_STORE1", b[int(args[0][1:])])
        elif op == "BIT_INVERT":
            b[int(args[0][1:])] ^= mask
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("kmx")
    ap.add_argument("--chunk", type=int, default=262144)
    ap.add_argument("--limit", type=int, default=MAX_X)
    a = ap.parse_args()
    text = Path(a.kmx).read_text()
    total: dict[int, int] = {}
    for lo in range(1, a.limit + 1, a.chunk):
        xs = np.arange(lo, min(lo + a.chunk, a.limit + 1), dtype=np.int64)
        for k, v in activity(text, xs, seed=lo).items():
            total[k] = total.get(k, 0) + v
        print(f"x up to {xs[-1]}: never-firing so far {sum(1 for v in total.values() if v == 0)}", flush=True)
    dead = sorted(k for k, v in total.items() if v == 0)
    print(f"gates {len(total)}, never fire on the domain: {len(dead)}: {dead}")


if __name__ == "__main__":
    main()
