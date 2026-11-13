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


@dataclass(frozen=True)
class SdTables:
    """Integer pipeline of the circuit: `D = D0[a] - sum_i u_i (E[a] >> (6 - i))` (units 2^-fd), the product
    `P` of `D (4 t + 3) / 4` in rows of shifted `D` (units 2^-fp), and the quotient digits."""

    fd: int
    fp: int
    d0: NDArray[np.int64]
    e: NDArray[np.int64]


def fit_sd(fd: int = 40, fp: int = 29) -> SdTables:
    """Per row: the pair `(D0, E)` whose floored refinement is closest to `D(R)` (max error over the row)."""
    sc = 2.0**fd
    d0 = np.zeros(128, dtype=np.int64)
    e = np.zeros(128, dtype=np.int64)
    u = np.arange(32)
    for row in range(128):
        dr = true_d(4096 + (row << 5) + u) * sc
        e0 = int(round(-(dr[-1] - dr[0]) / 31 * 64))
        best: tuple[float, int, int] | None = None
        for ee in range(max(0, e0 - 10), e0 + 11):
            sub = np.array([sum(((uu >> i) & 1) * (ee >> (6 - i)) for i in range(5)) for uu in range(32)])
            c = int(round(float((dr + sub).mean())))
            for dd in (c - 1, c, c + 1):
                err = float(np.abs(dd - sub - dr).max())
                if best is None or err < best[0]:
                    best = (err, dd, ee)
        assert best is not None
        d0[row], e[row] = best[1], best[2]
    return SdTables(fd, fp, d0, e)


def d_int(tab: SdTables, v: Int) -> Int:
    a, u = v >> 5, v & 31
    return np.asarray(
        tab.d0[a] - sum(((u >> i) & 1) * (tab.e[a] >> (6 - i)) for i in range(5)), dtype=np.int64
    )


def p_int(tab: SdTables, t: Int, dd: Int) -> Int:
    """`floor`-row product of `D` and `t + 3/4` in units `2^-fp`; `t` signed (14 bits)."""
    sh = tab.fd - tab.fp
    tu = t & ((1 << 14) - 1)
    p = np.zeros_like(t)
    for i in range(13):
        p += ((tu >> i) & 1) * ((dd >> (sh - i)) if i <= sh else (dd << (i - sh)))
    p -= ((tu >> 13) & 1) * (dd << (13 - sh))
    p += (dd >> (sh + 1)) + (dd >> (sh + 2))
    return p


def divide(tab: SdTables, r: Int, p: Int, digits: int) -> tuple[NDArray[np.float64], list[Int]]:
    """Non-restoring division of `X = 1 - P` by `s = (2R + 1) / 2^13`: `(sum q_j 2^-j, [q_j])`."""
    d = 2 * r + 1
    rem = ((1 << tab.fp) - p) * (1 << 13)
    s = d * (1 << tab.fp)
    total = np.zeros(len(r), dtype=np.float64)
    qs: list[Int] = []
    for j in range(1, digits + 1):
        q = np.where(rem >= 0, 1, -1).astype(np.int64)
        total += q * 2.0**-j
        qs.append(q)
        rem = 2 * rem - q * s
    return total, qs


def p_int_pm1(tab: SdTables, t: Int, dd: Int, offset: int = -3) -> Int:
    """Signed-digit product: `2 t + 1 = sum_{i<13} e_i 2^i - e_13 2^13`, `e_i = 2 b_i - 1` (`b` the bits of
    `t`), `P = D (t + 3/4)` as `sum e_i R(D >> k_i)` plus `R(D >> 13)` for `D/4`, `R` rounding half up,
    `k_i = 12 - i` (units `2^-fp`, `fp = fd - 11`), plus a constant `offset` that centres the error."""
    assert tab.fd - tab.fp == 11
    tu = t & ((1 << 14) - 1)
    e = [2 * ((tu >> i) & 1) - 1 for i in range(14)]

    def rnd(k: int) -> Int:
        return (dd >> k) + ((dd >> (k - 1)) & 1) if k >= 1 else (dd >> k if k == 0 else dd << -k)

    p = np.zeros_like(t)
    for i in range(13):
        p += e[i] * rnd(12 - i)
    p -= e[13] * (dd << 1)
    return p + rnd(13) + offset
