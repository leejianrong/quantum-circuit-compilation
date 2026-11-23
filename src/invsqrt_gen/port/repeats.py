"""Pebbling bound (QCC-61): which Toffoli products are computed twice, and could a spare wire hold them?

One classical simulation of the kmx text (as in ``width.py``) records, per CCX, the AND of its controls as a
bit vector over N sampled inputs, and the live-wire count after every step. Two CCX with the same product
vector and the same firing condition compute the same value. If a wire is free across the gap between them
(peak live width in the gap below the circuit's peak), holding the first result would save the second
Toffoli. That bounds what a rematerialisation optimiser could gain from repeats. Samples can propose; the
exact proof is still the gate.

    repeats.py FILE.kmx [--samples N] [--seed S]
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

from invsqrt_gen.port.width import INPUT_QUBITS, sample_inputs


def analyse(text: str, samples: int = 2048, seed: int = 0) -> dict[str, object]:
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
    ccx: list[tuple[int, int, bytes, float]] = []  # (step, line, signature, firing fraction)
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
            p = q[qs[0]] & q[qs[1]]
            if p.any() and not np.array_equal(p & mask, np.zeros(samples, dtype=bool)):
                ccx.append(
                    (
                        len(width),
                        idx,
                        np.packbits(p & mask).tobytes() + np.packbits(mask).tobytes(),
                        float(mask.mean()),
                    )
                )
            q[qs[2]] ^= p & mask
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
        width.append(int(live.sum()))
    w = np.array(width)
    peak = int(w.max())
    groups: dict[bytes, list[tuple[int, int, float]]] = defaultdict(list)
    for step, line, sig, frac in ccx:
        groups[sig].append((step, line, frac))
    pairs = []
    for occ in groups.values():
        for (s1, l1, _f1), (s2, l2, f2) in zip(occ, occ[1:], strict=False):
            gap = int(w[s1 : s2 + 1].max())
            pairs.append({"first": l1, "second": l2, "gap_peak": gap, "holdable": gap < peak, "firing": f2})
    return {"ccx": len(ccx), "peak": peak, "pairs": pairs}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("kmx")
    ap.add_argument("--samples", type=int, default=2048)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    r = analyse(Path(a.kmx).read_text(), a.samples, a.seed)
    pairs = r["pairs"]
    assert isinstance(pairs, list)
    hold = [p for p in pairs if p["holdable"]]
    print(f"CCX {r['ccx']}, peak width {r['peak']}")
    print(f"repeated products (consecutive pairs): {len(pairs)}, holdable below the peak: {len(hold)}")
    saved = sum(p["firing"] for p in hold)
    total = sum(p["firing"] for p in pairs)
    print(f"expected Toffolis a hold could save: {saved:.1f} (all repeats: {total:.1f})")
    for p in hold[:15]:
        print(p)


if __name__ == "__main__":
    main()
