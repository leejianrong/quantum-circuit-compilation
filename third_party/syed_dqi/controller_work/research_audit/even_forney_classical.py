#!/usr/bin/env python3
# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Classical algebra certificate for the even-degree raw Forney outer map.

No quantum circuit is generated. Dense inverse Bezout is a reference only;
it does not claim a cheap coherent implementation or a failure certificate.
"""
from __future__ import annotations
import argparse
import json
import random
from pathlib import Path

MODULUS = 0x1053


def manual_mul(a, b):
    answer = 0
    while b:
        if b & 1:
            answer ^= a
        b >>= 1
        a <<= 1
        if a & 4096:
            a ^= MODULUS
    return answer


EXP, LOG = [], [None]*4096
x = 1
for k in range(4095):
    assert LOG[x] is None
    EXP.append(x)
    LOG[x] = k
    x = manual_mul(x, 2)
assert x == 1 and len(set(EXP)) == 4095


def mul(a, b):
    return 0 if not a or not b else EXP[(LOG[a]+LOG[b]) % 4095]


def divide(a, b):
    assert b
    return 0 if not a else EXP[(LOG[a]-LOG[b]) % 4095]


def square(a):
    return mul(a, a)


def sqrt(a):
    return 0 if not a else EXP[(2048*LOG[a]) % 4095]


def trim(poly):
    out = list(poly)
    while len(out) > 1 and not out[-1]:
        out.pop()
    return out


def product(a, b):
    out = [0]*(len(a)+len(b)-1)
    for i, av in enumerate(a):
        for j, bv in enumerate(b):
            out[i+j] ^= mul(av, bv)
    return trim(out)


def remainder(a, b):
    out = trim(a)
    assert any(b)
    while len(out) >= len(b) and any(out):
        shift = len(out)-len(b)
        factor = divide(out[-1], b[-1])
        for i, value in enumerate(b):
            out[i+shift] ^= mul(value, factor)
        out = trim(out)
    return out


def bezout(a, b):
    n = max(len(a), len(b))-1
    aa = list(a)+[0]*(n+1-len(a))
    bb = list(b)+[0]*(n+1-len(b))
    matrix = [[0]*n for _ in range(n)]
    for i in range(1, n+1):
        for j in range(i):
            coefficient = mul(aa[i], bb[j]) ^ mul(aa[j], bb[i])
            for k in range(i-j):
                matrix[i-1-k][j+k] ^= coefficient
    return matrix


def solve_two(matrix, u, v):
    n = len(matrix)
    rows = [list(row)+[u[i], v[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = next(i for i in range(col, n) if rows[i][col])
        rows[col], rows[pivot] = rows[pivot], rows[col]
        scale = rows[col][col]
        rows[col] = [divide(a, scale) for a in rows[col]]
        for i in range(n):
            if i == col:
                continue
            factor = rows[i][col]
            for j in range(col, n+2):
                rows[i][j] ^= mul(factor, rows[col][j])
    return [row[n] for row in rows], [row[n+1] for row in rows]


def even_forney(d, omega):
    degree = len(d)-1
    assert degree % 2 == 0 and len(omega) == degree and d[-1]
    h = degree//2
    a = [sqrt(value) for value in d[::2]]
    b = [sqrt(value) for value in d[1::2]]
    hmatrix = bezout(a, b)
    # H^(2) e_last = leading(D) * odd_coefficients(D).
    for i in range(h):
        assert square(hmatrix[i][-1]) == mul(d[-1], d[2*i+1])
    u, v = list(omega[::2]), list(omega[1::2])
    q = divide(v[-1], d[-1])
    u = [value ^ mul(d[2*i+1], q) for i, value in enumerate(u)]
    u, v = solve_two(hmatrix, [sqrt(value) for value in u],
                     [sqrt(value) for value in v])
    inverse_bez = [z for pair in zip(map(square, v), map(square, u)) for z in pair]
    # Full degree-word lower Toeplitz, diagonal d[degree], then reverse.
    out = []
    for i in range(degree):
        value = 0
        for j in range(i+1):
            value ^= mul(d[degree-i+j], inverse_bez[j])
        out.append(value)
    return list(reversed(out))


def half_profile(d):
    a = trim([sqrt(value) for value in d[::2]])
    b = trim([sqrt(value) for value in d[1::2]])
    degrees = [len(a)-1]
    while any(b):
        degrees.append(len(b)-1)
        a, b = b, remainder(a, b)
    return degrees


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rng = random.Random(202611110614)
    manual_checks = 0
    for _ in range(4096):
        a, b = rng.randrange(4096), rng.randrange(4096)
        assert manual_mul(a, b) == mul(a, b)
        assert square(sqrt(a)) == a
        manual_checks += 1
    rows = []
    for degree, count in [(2, 64), (4, 64), (6, 64), (8, 64), (32, 16), (34, 16)]:
        top_zero = 0
        zero_rhs = 0
        profile_histogram = {}
        for shot in range(count):
            while True:
                roots = rng.sample(range(4096), degree)
                if degree > 2 and shot % 4 == 0:
                    final = 0
                    for root in roots[:-1]:
                        final ^= root
                    roots[-1] = final
                if len(set(roots)) == degree:
                    break
            d = [rng.randrange(1, 4096)]
            for root in roots:
                d = product(d, [root, 1])
            omega = [0 if shot % 13 == 0 else rng.randrange(4096) for _ in range(degree)]
            converted = even_forney(d, omega)
            derivative = trim([d[i+1] if i % 2 == 0 else 0 for i in range(degree)])
            restored = remainder(product(converted, derivative), d)
            assert trim(omega) == restored, (degree, shot)
            top_zero += not d[-2]
            zero_rhs += not any(omega)
            profile = half_profile(d)
            assert profile[-1] == 0
            key = ",".join(map(str, profile))
            profile_histogram[key] = profile_histogram.get(key, 0)+1
        rows.append(dict(degree=degree, cases=count, zero_top_derivative_coefficient=top_zero,
                         zero_numerators=zero_rhs, half_profile_histogram=profile_histogram))
    result = dict(status="PASS_CLASSICAL_EVEN_FORNEY_IDENTITY_ONLY",
                  cases=sum(r["cases"] for r in rows), field_crosschecks=manual_checks, rows=rows,
                  limitations="Dense reference linear algebra. No quantum emitter, T/Q measurement, "
                              "dynamic degree controller, phase test, or converter failure certificate.")
    args.output.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
