"""Self-inverse gate pairs with nothing touching their qubits (or condition bits) in between."""

import collections
import json
import sys

path = sys.argv[1]
last = {}  # wire ('q12'/'b7') -> instruction number of last touch
pend = {}  # key -> (n, ) last occurrence of gate key
stack = []
found = collections.Counter()
lines_found = collections.defaultdict(list)
SELF = {"CCX", "CCZ", "CZ", "CX", "CSWAP", "SWAP", "X", "Z"}
n = 0
with open(path) as f:
    for ln in f:
        n += 1
        p = ln.split()
        op = p[0]
        if op in ("REGISTER", "APPEND_TO_REGISTER"):
            continue
        if op == "PUSH_CONDITION":
            stack.append(p[2])
            last[p[2]] = n
            stack_key = tuple(stack)
            continue
        if op == "POP_CONDITION":
            stack.pop()
            continue
        extra = None
        if len(p) >= 3 and p[-2] == "if":
            extra = p[-1]
            p = p[:-2]
        wires = [t for t in p[1:] if t[0] in "qb" and t[1:].isdigit()]
        cb = tuple(stack) + ((extra,) if extra else ())
        deps = wires + list(cb)
        if op in SELF and all(t[0] == "q" for t in wires):
            key = (op, tuple(wires) if op not in ("CZ", "CCZ", "SWAP") else tuple(sorted(wires)), cb)
            prev = pend.get(key)
            if prev is not None and all(last.get(t, -1) <= prev for t in deps):
                found[op] += 1
                lines_found[op].append((prev, n))
                pend.pop(key)
                for t in wires:
                    last[t] = n
                continue
            pend[key] = n
        for t in wires:
            last[t] = n
print(dict(found))
json.dump({k: v[:50] for k, v in lines_found.items()}, open(sys.argv[2], "w"))
