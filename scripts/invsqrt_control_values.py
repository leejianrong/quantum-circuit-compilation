"""Per CCX/CCZ: over executing samples, how often each control is 1 and the AND. Full domain, invsqrt."""

import glob
import json
import re
import sys

import numpy as np

sys.path.insert(0, "src")
from invsqrt_gen.port.width import INPUT_QUBITS, MAX_X

rows = []
for f in sorted(glob.glob("out/circuit-index/bb676b95/pages/*.json")):
    rows += json.load(open(f))["rows"]
lines = [r[1].split() for r in rows]
nq = 1 + max(int(t[1:]) for ln in lines for t in ln if re.fullmatch(r"q\d+", t))
nb = 1 + max((int(t[1:]) for ln in lines for t in ln if re.fullmatch(r"b\d+", t)), default=0)
seed = int(sys.argv[1]) if len(sys.argv) > 1 else 0
stat = {}  # idx -> [exec, c0, c1, c0&c1, (c2)]
CH = 262144
for lo in range(1, MAX_X + 1, CH):
    xs = np.arange(lo, min(lo + CH, MAX_X + 1), dtype=np.int64)
    n = len(xs)
    rng = np.random.default_rng(seed + lo)
    q = np.zeros((nq, n), bool)
    for i in range(INPUT_QUBITS):
        q[i] = (xs >> i) & 1 == 1
    b = np.zeros((nb, n), bool)
    stack = []
    ones = np.ones(n, bool)
    for idx, ln in enumerate(lines):
        op, args = ln[0], ln[1:]
        if op == "PUSH_CONDITION":
            stack.append(b[int(args[1][1:])].copy())
            continue
        if op == "POP_CONDITION":
            stack.pop()
            continue
        cond = args[-1] if len(args) >= 2 and args[-2] == "if" else None
        if cond:
            args = args[:-2]
        mask = ones
        for s in stack:
            mask = mask & s
        if cond:
            mask = mask & b[int(cond[1:])]
        qs = [int(a[1:]) for a in args if re.fullmatch(r"q\d+", a)]
        if op == "X":
            q[qs[0]] ^= mask
        elif op == "CX":
            q[qs[1]] ^= q[qs[0]] & mask
        elif op in ("CCX", "CCZ"):
            a, c = q[qs[0]] & mask, q[qs[1]] & mask
            st = stat.setdefault(idx, [0, 0, 0, 0, 0])
            st[0] += int(mask.sum())
            st[1] += int(a.sum())
            st[2] += int(c.sum())
            st[3] += int((a & c).sum())
            if op == "CCX":
                q[qs[2]] ^= a & c
            else:
                st[4] += int((a & c & q[qs[2]]).sum())
        elif op == "SWAP":
            d = (q[qs[0]] ^ q[qs[1]]) & mask
            q[qs[0]] ^= d
            q[qs[1]] ^= d
        elif op == "CSWAP":
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
    print(lo, flush=True)
json.dump({str(k): v for k, v in stat.items()}, open(sys.argv[2], "w"))
