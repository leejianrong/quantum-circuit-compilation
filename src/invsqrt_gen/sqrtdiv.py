"""Square-root-and-division model of the invsqrt phase (QCC-13): our own derivation, exact integer arithmetic.

`1/sqrt(x) = 2^k / sqrt(n)` with `n = x 4^k` in `[2^20, 2^22)` (even shift only, `k` in 0..10).
Let `R = isqrt(16 n)` (13 bits; `v = R - 4096` is the 12-bit root) and `t = 16 n - R^2 - R - 1`, an exact
integer in `[-R-1, R)`: its high bits `h = t >> 4` fit 10 signed bits and its low bits are a function of `R`,
so `n` is recovered from `(v, h)`. With the centred root `s = (2R + 1) / 2^13` and
`N = n / 2^20 = s^2 + (t + 3/4) / 2^24`:

    1/sqrt(N) = (1 - P) / s,   P = D (t + 3/4),   D = 1 / (2 s^2 2^24)

to first order (the second order is below 2^-25.4 and its mean is absorbed by one constant). `D` is the
only table: rows by the top bits of `v`, a linear refinement by the low bits. The division by `s` has the
odd 14-bit divisor `2R + 1`. This module holds the numbers; the circuit builder lives next to it.
"""

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

MAX_X = 3 * (2**10 - 2) ** 2  # the largest input of the benchmark (n_p = 10)

Int = NDArray[np.int64]


def reachable_n() -> Int:
    """Every distinct normalised `n = x 4^k` (k = 0..10) that some `x` in `[1, MAX_X]` produces."""
    xs = np.arange(1, MAX_X + 1, dtype=np.int64)
    bl = np.zeros_like(xs)
    for b in range(23):
        bl[xs >= (1 << b)] = b + 1
    return np.unique(xs << (2 * ((22 - bl) // 2)))


def root(n: Int) -> tuple[Int, Int]:
    """`(R, t)`: `R = isqrt(16 n)` and `t = 16 n - R^2 - R - 1`."""
    r = np.floor(np.sqrt(16.0 * n)).astype(np.int64)
    r = np.where(r * r > 16 * n, r - 1, r)
    r = np.where((r + 1) * (r + 1) <= 16 * n, r + 1, r)
    return r, 16 * n - r * r - r - 1


@dataclass(frozen=True)
class DTable:
    """`D(R) ~ D0[a] + D1[a] u` with `a = v >> (12 - addr_bits)`, `u = v mod 2^(12 - addr_bits)`.

    `d0` is an integer multiple of `2^-f0` and `d1` of `2^-f1` (plain reals of `D`).
    """

    addr_bits: int
    f0: int
    f1: int
    d0: NDArray[np.int64]
    d1: NDArray[np.int64]

    def value(self, v: Int) -> NDArray[np.float64]:
        sh = 12 - self.addr_bits
        a, u = v >> sh, v & ((1 << sh) - 1)
        return np.asarray(self.d0[a] / 2.0**self.f0 + self.d1[a] * u / 2.0**self.f1, dtype=np.float64)


def true_d(r: NDArray[np.float64] | Int) -> NDArray[np.float64]:
    s = (2 * np.asarray(r, dtype=np.float64) + 1) / 8192.0
    return np.asarray(1.0 / (2 * s * s * 2.0**24), dtype=np.float64)


def fit_d(addr_bits: int = 7, f0: int = 38, f1: int = 44) -> DTable:
    """Per-row linear least-squares fit of `D(R)`, quantised to `2^-f0` and `2^-f1`."""
    sh = 12 - addr_bits
    d0 = np.zeros(1 << addr_bits, dtype=np.int64)
    d1 = np.zeros(1 << addr_bits, dtype=np.int64)
    ur = np.arange(1 << sh)
    for row in range(1 << addr_bits):
        dr = true_d(4096 + (row << sh) + ur)
        slope, icpt = np.polyfit(ur, dr, 1)
        d0[row] = round(icpt * 2.0**f0)
        d1[row] = round(slope * 2.0**f1)
    return DTable(addr_bits, f0, f1, d0, d1)


def relative_error(n: Int, table: DTable) -> NDArray[np.float64]:
    """Signed relative error of `(1 - D (t + 3/4)) / s` against `1/sqrt(N)` (exact division and product)."""
    r, t = root(n)
    s = (2 * r + 1) / 8192.0
    p = table.value(r - 4096) * (t + 0.75)
    exact = 1.0 / np.sqrt(n / 2.0**20)
    return ((1 - p) / s - exact) / exact


def worst_error_bits(n: Int, table: DTable) -> float:
    """`log2` of the largest relative error after removing the mean bias (one free constant)."""
    e = relative_error(n, table)
    return math.log2(float(np.abs(e - 0.5 * (e.max() + e.min())).max()))
