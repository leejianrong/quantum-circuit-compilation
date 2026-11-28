"""Abstract interpretation of a kickmix text (QCC-61): qubits and bits in {0, 1, 2 = unknown}.

Reports Toffoli-class gates whose controls are known, and gates under a condition bit that is known 0.
Usage: kmx_constprop.py TEXT OUT.json (TEXT from `Circuit.to_file`). Input qubits are those in the leading
APPEND_TO_REGISTER block; every other qubit starts at 0.
"""

import collections
import json
import sys

path, out = sys.argv[1], sys.argv[2]
U = 2
q = collections.defaultdict(int)  # default 0
b = collections.defaultdict(lambda: U)  # classical bits unknown unless stored
inputs = set()
stack = []  # list of bit ids (cond bit names)


def bv(x):
    return b[x]


def cond_state(extra):
    """1 = surely runs, 0 = surely not, U = maybe"""
    st = 1
    for c in stack + ([extra] if extra else []):
        v = b[c]
        if v == 0:
            return 0
        if v == U:
            st = U
    return st


cand = collections.defaultdict(list)  # kind -> [line numbers]
stats = collections.Counter()


def setq(t, new, st):
    if st == 1:
        q[t] = new
    elif st == U:
        q[t] = q[t] if q[t] == new else U


n = 0
inp_phase = True
with open(path) as f:
    for ln in f:
        n += 1
        p = ln.split()
        op = p[0]
        if op == "APPEND_TO_REGISTER":
            if inp_phase and p[1][0] == "q":
                inputs.add(int(p[1][1:]))
                q[int(p[1][1:])] = U
            continue
        if op == "REGISTER":
            continue
        inp_phase = False
        if op == "PUSH_CONDITION":
            stack.append(p[2])
            continue
        if op == "POP_CONDITION":
            stack.pop()
            continue
        extra = p[-1] if len(p) >= 3 and p[-2] == "if" else None
        if extra:
            p = p[:-2]
        st = cond_state(extra)
        if op in ("BIT_STORE0", "BIT_STORE1"):
            t = p[1]
            new = 1 if op == "BIT_STORE1" else 0
            if st == 1:
                b[t] = new
            elif st == U:
                b[t] = b[t] if b[t] == new else U
            continue
        if op == "BIT_INVERT":
            t = p[1]
            v = b[t]
            new = U if v == U else 1 - v
            if st == 1:
                b[t] = new
            elif st == U:
                b[t] = v if v == new else U
            continue
        if st == 0:
            if op in ("CCX", "CCZ", "CSWAP"):
                cand["dead_cond"].append(n)
            continue
        if op == "X":
            t = int(p[1][1:])
            v = q[t]
            setq(t, U if v == U else 1 - v, st)
        elif op == "CX":
            c, t = int(p[1][1:]), int(p[2][1:])
            cv = q[c]
            if cv == 1:
                v = q[t]
                setq(t, U if v == U else 1 - v, st)
            elif cv == U:
                setq(t, U, st)
        elif op in ("CCX", "CCZ"):
            a, c = int(p[1][1:]), int(p[2][1:])
            av, cv = q[a], q[c]
            if av == 0 or cv == 0:
                cand[op + "_noop"].append(n)
            elif av == 1 and cv == 1:
                cand[op + "_always"].append(n)
            elif av == 1 or cv == 1:
                cand[op + "_cx"].append(n)
            elif a == c:
                cand[op + "_samectrl"].append(n)
            if op == "CCX":
                t = int(p[3][1:])
                v = q[t]
                if av == 0 or cv == 0:
                    pass
                elif av == 1 and cv == 1:
                    setq(t, U if v == U else 1 - v, st)
                else:
                    setq(t, U, st)
        elif op == "SWAP":
            a, c = int(p[1][1:]), int(p[2][1:])
            if st == 1:
                q[a], q[c] = q[c], q[a]
            else:
                if q[a] != q[c]:
                    q[a] = q[c] = U
        elif op == "CSWAP":
            cc, a, c = int(p[1][1:]), int(p[2][1:]), int(p[3][1:])
            if q[cc] == 0:
                cand["CSWAP_noop"].append(n)
            elif q[cc] == 1 and st == 1:
                q[a], q[c] = q[c], q[a]
            elif q[a] != q[c]:
                q[a] = q[c] = U
        elif op == "HMR":
            t = int(p[1][1:])
            bit = p[2]
            setq(t, 0, st)
            b[bit] = U
        elif op == "R":
            setq(int(p[1][1:]), 0, st)
        stats[op] += 1
        if n % 10_000_000 == 0:
            print(n, {k: len(v) for k, v in cand.items()}, flush=True)
print({k: len(v) for k, v in cand.items()})
json.dump({k: v for k, v in cand.items()}, open(out, "w"))
print("inputs", len(inputs), "lines", n)
