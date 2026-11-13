# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Manual classical references for the new outer converters; no kickmix."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research_audit'))
import even_forney_classical as F


def half_source(d):
    a = [F.sqrt(value) for value in d[::2]]
    b = [F.sqrt(value) for value in d[1::2]]
    if (len(d)-1) % 2:
        q = F.divide(a[-1], b[-1])
        return b, [x ^ F.mul(q, y) for x, y in zip(a[:-1], b[:-1])]
    return a, b


def profile(d):
    a, b = map(F.trim, half_source(d))
    degrees = [len(a)-1]
    while any(b):
        degrees.append(len(b)-1)
        a, b = b, F.remainder(a, b)
    return degrees


def admitted(d):
    degrees = profile(d)
    if degrees[-1] != 0:
        return False
    drops = [a-b for a, b in zip(degrees, degrees[1:])]
    padded = {a for a, b in zip(degrees, degrees[1:]) if a-b == 2}
    return max(drops, default=1) <= 2 and not {17, 15} <= padded and not {14, 12} <= padded


def full_preimage(d, omega):
    degree = len(d)-1
    a = [F.sqrt(value) for value in d[::2]]
    b = [F.sqrt(value) for value in d[1::2]]
    if degree % 2:
        s = b[-1]
        h = F.divide(F.sqrt(omega[-1]), s)
        q = F.divide(a[-1], s)
        u = [F.sqrt(x) ^ F.mul(h, y) for x, y in zip(omega[::2][:-1], b[:-1])]
        v = list(map(F.sqrt, omega[1::2]))
        reduced = [x ^ F.mul(q, y) for x, y in zip(a[:-1], b[:-1])]
        u, v = F.solve_two(F.bezout(b, reduced), u, v)
        for coefficient, value in zip(b[:-1], v):
            h ^= F.mul(coefficient, value)
        h = F.divide(h, s)
        roots = [x for pair in zip(v, u) for x in pair]+[h]
    else:
        s = a[-1]
        u, v = list(map(F.sqrt, omega[::2])), list(map(F.sqrt, omega[1::2]))
        q = F.divide(v[-1], s)
        u = [x ^ F.mul(y, q) for x, y in zip(u, b)]
        u, v = F.solve_two(F.bezout(a, b), u, v)
        roots = [x for pair in zip(v, u) for x in pair]
    z = list(map(F.square, roots))
    derivative = F.trim([d[i+1] if i % 2 == 0 else 0 for i in range(degree)])
    matrix = F.bezout(d, derivative)
    for row, target in zip(matrix, omega):
        value = 0
        for coefficient, source in zip(row, z):
            value ^= F.mul(coefficient, source)
        assert value == target
    return z


def toeplitz(coefficients, vector):
    out = []
    for i in range(len(vector)):
        value = 0
        for j in range(i+1):
            if i-j < len(coefficients):
                value ^= F.mul(coefficients[i-j], vector[j])
        out.append(value)
    return out


def fused(d, omega, histories):
    z = full_preimage(d, omega)
    return list(reversed(toeplitz(list(reversed(d)), list(reversed(histories))+z)))
