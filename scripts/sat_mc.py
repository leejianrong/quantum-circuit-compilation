"""Exact multiplicative complexity of an n-input function by SAT (QCC-61, loader test).

Is there an XOR-AND graph with k ANDs? Each AND takes two affine forms of the inputs and earlier
ANDs; the output is affine in all of them. Needs ``python-sat``, which is NOT a repo dependency:
use an isolated venv:
``uv venv ~/qcc-builds/venv-sat``, then
``uv pip install --python ~/qcc-builds/venv-sat/bin/python python-sat``.

    sat_mc.py TRUTH_TABLE_BITS KMAX      e.g. a 128-character string of 0/1
"""

from __future__ import annotations

import sys
import time

from pysat.formula import IDPool
from pysat.solvers import Cadical153


def feasible(tt: list[int], n: int, k: int) -> tuple[bool, float]:
    rows = 1 << n
    pool = IDPool()
    cl: list[list[int]] = []

    def xor_chain(terms: list[int]) -> int:
        acc = terms[0]
        for t in terms[1:]:
            v = pool.id()
            cl.extend([[-v, acc, t], [-v, -acc, -t], [v, -acc, t], [v, acc, -t]])
            acc = v
        return acc

    def and_var(a: int, b: int) -> int:
        v = pool.id()
        cl.extend([[-v, a], [-v, b], [v, -a, -b]])
        return v

    true = pool.id()
    cl.append([true])
    val = [[true] * rows] + [[true if (r >> i) & 1 else -true for r in range(rows)] for i in range(n)]

    def lincomb(count: int) -> tuple[list[int], list[int]]:
        cs = [pool.id() for _ in range(count)]
        return cs, [xor_chain([and_var(cs[j], val[j][r]) for j in range(count)]) for r in range(rows)]

    for g in range(k):
        cl_, left = lincomb(1 + n + g)
        cr_, right = lincomb(1 + n + g)
        cl.append(cl_[1:])
        cl.append(cr_[1:])
        val.append([and_var(left[r], right[r]) for r in range(rows)])
    _, out = lincomb(1 + n + k)
    for r in range(rows):
        cl.append([out[r]] if tt[r] else [-out[r]])
    t0 = time.time()
    return Cadical153(bootstrap_with=cl).solve(), time.time() - t0


def main() -> None:
    bits = [int(c) for c in sys.argv[1]]
    n = len(bits).bit_length() - 1
    for k in range(int(sys.argv[2]) + 1):
        ok, t = feasible(bits, n, k)
        print(f"k={k} {'SAT' if ok else 'UNSAT'} {t:.1f}s", flush=True)
        if ok:
            break


if __name__ == "__main__":
    main()
