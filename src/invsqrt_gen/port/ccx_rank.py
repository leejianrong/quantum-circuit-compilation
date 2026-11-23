"""Stage 1 of the search harness (QCC-61): is any CCX of a kmx text redundant on the sampled states?

For every CCX we take the AND ``p = a & b`` over N sampled inputs (and HMR outcomes) and ask whether
``p`` lies in the GF(2) span of the constant 1 and the other live wires at that step. If it does, the
Toffoli could be replaced by CX/X gates (free) on those samples; the exact proof is the gate afterwards.
Samples can only propose, never prove.

    ccx_rank.py FILE.kmx [--samples N] [--seed S]
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np

from invsqrt_gen.port.width import INPUT_QUBITS, sample_inputs


def _pack(v: np.ndarray) -> int:
    return int.from_bytes(np.packbits(v).tobytes(), "big")


def in_span(target: int, vecs: list[int]) -> bool:
    basis: dict[int, int] = {}
    for v in vecs:
        while v:
            h = v.bit_length()
            if h in basis:
                v ^= basis[h]
            else:
                basis[h] = v
                break
    while target:
        h = target.bit_length()
        if h not in basis:
            return False
        target ^= basis[h]
    return True


def scan(text: str, samples: int = 2048, seed: int = 0) -> list[tuple[int, str, bool]]:
    """Return (line index, gate text, redundant) for every CCX, simulated exactly as ``width.profile``."""
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
    out: list[tuple[int, str, bool]] = []
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
            p = q[qs[0]] & q[qs[1]] & mask
            # restrict to the samples where the gate fires: a condition bit is not a wire we can XOR in
            act = mask
            others = [_pack(q[i][act]) for i in range(nq) if i != qs[2] and q[i][act].any()]
            others.append(_pack(np.ones(int(act.sum()), dtype=bool)))
            tag = "" if mask.all() else f" [conditioned, {int(act.sum())} active samples]"
            out.append((idx, " ".join(ln) + tag, in_span(_pack(p[act]), others)))
            q[qs[2]] ^= p
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
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("kmx")
    ap.add_argument("--samples", type=int, default=2048)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    res = scan(Path(a.kmx).read_text(), a.samples, a.seed)
    hits = [r for r in res if r[2]]
    print(f"CCX scanned {len(res)}, redundant on the samples: {len(hits)}")
    for idx, gate, _ in hits[:20]:
        print(idx, gate)


if __name__ == "__main__":
    main()
