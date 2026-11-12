"""Bit-exact classical model of the generated pipeline, plus the coefficient fit.

The model works on the normalised mantissa `x_norm` (22 bits, top bit set, `M = x_norm / 2^21` in [1, 2)) and
the parity `par` of the leading zero count: the target is `1 / sqrt(M 2^(1 - par))`.
The circuit and this model share `row_plan`, so a mismatch is a bug in one of the two builders and the
tests compare them on simulated shots.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from invsqrt_gen.params import FRAC, Params

Int = NDArray[np.int64]


@dataclass(frozen=True)
class Digit:
    """One radix-4 Booth digit of the remainder in Horner step `j`.

    With `b_i` the bits of `r` (zero outside `0 <= i < rwidth`), digit `n` is
    `d_n = -2 b_{2n+1} + b_{2n} + b_{2n-1}` and `r = sum d_n 4^n`. The step subtracts
    `d_n * floor(V_{j+1} 2^e)` from `V_j`, with `e = e1` for `|d| = 1` and `e1 + 1` for `|d| = 2`.
    """

    n: int
    e1: int  # target index of source bit k is k + e1 (|d| = 1) or k + e1 + 1 (|d| = 2)
    kmin1: int  # first source bit inside the target when |d| = 1
    kmin2: int  # the same when |d| = 2


def digit_plan(p: Params, j: int) -> list[Digit]:
    """Booth digits of Horner step `j`; a digit whose slices are empty is dropped."""
    out = []
    for n in range((p.rwidth + 1) // 2 if p.centered else p.rwidth // 2 + 1):
        e1 = p.frac[j] - p.frac[j + 1] + 2 * n - FRAC
        d = Digit(n, e1, max(0, -e1), max(0, -e1 - 1))
        if d.kmin1 < p.frac[j + 1]:
            out.append(d)
    return out


def _shift(v: Int, e: int) -> Int:
    return (v >> -e) if e < 0 else (v << e)


def horner(p: Params, coef: list[Int], r: Int, check: bool = True) -> Int:
    """`V_0` for remainder `r` given per-element coefficient values `coef[j]` (shape of `r`)."""

    rc = (
        r - (1 << (p.rwidth - 1)) if p.centered else r
    )  # two's complement bits of a negative rc: arithmetic shift

    def bit(i: int) -> Int:
        return (rc >> i) & 1 if 0 <= i < p.rwidth else np.zeros_like(r)

    v = coef[p.degree]
    for j in range(p.degree - 1, -1, -1):
        acc = np.zeros_like(r)
        for dg in digit_plan(p, j):
            d = -2 * bit(2 * dg.n + 1) + bit(2 * dg.n) + bit(2 * dg.n - 1)
            t1, t2 = _shift(v, dg.e1), _shift(v, dg.e1 + 1)
            acc += np.where(np.abs(d) == 1, np.sign(d) * t1, np.where(np.abs(d) == 2, np.sign(d) * t2, 0))
        lim = 1 << (p.frac[j] - p.a)
        bad = (np.abs(acc) >= lim >> 2).any() if p.centered else ((acc < 0).any() or (acc >= lim).any())
        if check and bad:
            raise OverflowError(f"product of step {j} leaves its low part 2^{p.frac[j] - p.a}")
        v = coef[j] - acc
        if check and ((v < 0).any() or (v >= (1 << p.frac[j])).any()):
            raise OverflowError(f"V_{j} leaves [0, 2^{p.frac[j]})")
    return v


def normalised_inputs() -> tuple[Int, Int]:
    """Every `(x_norm, parity)` the circuit can see: 22-bit values with the top bit set, both parities."""
    xn = np.arange(1 << FRAC, 1 << (FRAC + 1), dtype=np.int64)
    return np.concatenate([xn, xn]), np.repeat(np.array([0, 1], dtype=np.int64), len(xn))


MAX_X = 3 * (2**10 - 2) ** 2  # the largest input of the benchmark (n_p = 10)


def reachable_mask() -> NDArray[np.bool_]:
    """Which `normalised_inputs()` some `x` in `[1, MAX_X]` produces: `x << z` with `z` of the same parity."""
    xn, par = normalised_inputs()
    reach = np.zeros(len(xn), dtype=bool)
    for z in range(FRAC + 1):
        x = xn >> z
        reach |= (par == (z & 1)) & ((xn & ((1 << z) - 1)) == 0) & (x >= 1) & (x <= MAX_X)
    return reach


def reachable_matrix(p: Params) -> NDArray[np.bool_]:
    """`reachable_mask()` as (segment `(par << a) | aa`, remainder `r`)."""
    return reachable_mask().reshape(2 << p.a, 1 << p.rwidth)


@dataclass
class Tables:
    p: Params
    coef: list[Int]  # coef[j][address - 2^a], address in p.entries

    def words(self) -> list[int]:
        """Per-address concatenated word `c_0 | c_1 << f0 | ...` for all addresses 0 .. 4 * 2^a - 1."""
        out = [0] * (2 << self.p.a)
        off = 0
        word = np.zeros(len(self.coef[0]), dtype=object)
        for j, c in enumerate(self.coef):
            word = word + c.astype(object) * (1 << off)
            off += self.p.frac[j]
        for k, w in enumerate(word):
            out[k] = int(w)
        return out


def model_y(p: Params, t: Tables, xn: Int, par: Int) -> Int:
    """`V_0 >> guard`: the phased word, for each `x_norm` and parity."""
    a_idx = (par << p.a) | ((xn >> p.rwidth) & ((1 << p.a) - 1))
    r = xn & ((1 << p.rwidth) - 1)
    v0 = horner(p, [c[a_idx] for c in t.coef], r)
    return p.phased(v0)


def rel_error(p: Params, t: Tables) -> tuple[float, NDArray[np.float64]]:
    """Max relative error of `y` against `1/sqrt(M 2^(1-par))` and the per-input errors."""
    xn, par = normalised_inputs()
    y = model_y(p, t, xn, par).astype(np.float64) / 2.0**p.wy
    exact = 1.0 / np.sqrt(xn.astype(np.float64) / 2.0**FRAC * 2.0 ** (1 - par))
    err = np.abs(y - exact) / exact
    return float(err.max()), err


def fit_tables(
    p: Params, passes: int = 3, stride: int = 1, polish: bool = False, reachable: bool = False
) -> Tables:
    """Quantised coefficients per segment, refined against the exact truncated model.

    Start from a Chebyshev-node polynomial fit, round, then do coordinate descent on c_d .. c_1 and
    recentre c_0 so that the signed error of the phased word is symmetric. With `reachable` only the inputs
    some `x <= MAX_X` produces count (the verifier never runs the others).
    """
    d, n_seg = p.degree, 2 << p.a
    r_all = np.arange(0, 1 << p.rwidth, stride, dtype=np.int64)
    if r_all[-1] != (1 << p.rwidth) - 1:
        r_all = np.append(r_all, (1 << p.rwidth) - 1)
    coef = [np.zeros(n_seg, dtype=np.int64) for _ in range(d + 1)]
    h = 2.0 ** (-p.a)  # segment width in M
    nodes = 0.5 * h * (1 - np.cos(np.pi * (np.arange(2 * d + 3) + 0.5) / (2 * d + 3)))
    if p.centered:
        nodes = nodes - 0.5 * h
    for k in range(n_seg):
        c = 2.0 ** (1 - (k >> p.a))
        m0 = 1 + (k & ((1 << p.a) - 1)) * h
        mid = 0.5 * h if p.centered else 0.0
        poly = np.polynomial.polynomial.polyfit(nodes, (c * (m0 + mid + nodes)) ** -0.5, d)
        # f(r) = c0 - r (c1' - r (c2 - ...)); polyfit gives f = sum q_j r^j, so c_j = |q_j| with
        # alternating signs. Fixed point: scale 2^f_j on the Horner value V_j = sum_{i>=j} ...
        # V_j = |q_j| + ... is the polynomial tail, so quantise q_j directly.
        for j in range(d + 1):
            coef[j][k] = (
                int(round((-1) ** j * poly[j] * 2.0 ** p.frac[j]))
                if p.centered
                else int(round(abs(poly[j]) * 2.0 ** p.frac[j]))
            )
    seg = np.arange(n_seg)
    xr = ((1 << p.a) + (seg[:, None] & ((1 << p.a) - 1))) * (1 << p.rwidth) + r_all[None, :]
    scale = 2.0 ** (1 - (seg[:, None] >> p.a))
    exact = 1.0 / np.sqrt(xr.astype(np.float64) / 2.0**FRAC * scale)
    valid = reachable_matrix(p) if reachable else None
    valid_s = None if valid is None else valid[:, r_all]
    for _ in range(passes):
        for j in range(d, 0, -1):
            best = _seg_err(p, coef, r_all, exact, valid_s)
            for delta in (-2, -1, 1, 2):
                trial = [c.copy() for c in coef]
                trial[j] += delta
                e = _seg_err(p, trial, r_all, exact, valid_s)
                better = e < best
                coef[j] = np.where(better, trial[j], coef[j])
                best = np.where(better, e, best)
        _recentre(p, coef, r_all, exact, valid=valid_s)
    if polish:
        _polish(p, coef, exact_full(p), valid)
    return Tables(p, coef)


def exact_full(p: Params) -> NDArray[np.float64]:
    """Exact targets for every segment (rows) and every remainder (columns)."""
    seg = np.arange(2 << p.a)[:, None]
    r = np.arange(1 << p.rwidth, dtype=np.int64)[None, :]
    xr = ((1 << p.a) + (seg & ((1 << p.a) - 1))) * (1 << p.rwidth) + r
    return 1.0 / np.sqrt(xr.astype(np.float64) / 2.0**FRAC * 2.0 ** (1 - (seg >> p.a)))


def _polish(
    p: Params, coef: list[Int], exact: NDArray[np.float64], valid: NDArray[np.bool_] | None = None
) -> None:
    """Joint +-1 search on c_1 .. c_d for every segment against all remainders, then recentre c_0."""
    r = np.arange(1 << p.rwidth, dtype=np.int64)
    d = p.degree
    best = _seg_err(p, coef, r, exact, valid)
    combos = [c for c in np.ndindex(*([3] * d)) if any(c)]
    for _ in range(2):
        for combo in combos:
            trial = [c.copy() for c in coef]
            for j, v in enumerate(combo, start=1):
                trial[j] += v - 1
            _recentre(p, trial, r, exact, rounds=1, valid=valid)
            e = _seg_err(p, trial, r, exact, valid)
            better = e < best
            for j in range(d + 1):
                coef[j] = np.where(better, trial[j], coef[j])
            best = np.where(better, e, best)


def _seg_err(
    p: Params, coef: list[Int], r: Int, exact: NDArray[np.float64], valid: NDArray[np.bool_] | None = None
) -> NDArray[np.float64]:
    """Max absolute error of the phased word per segment, in ulps of the phased word."""
    n_seg = len(coef[0])
    rr = np.broadcast_to(r[None, :], (n_seg, len(r)))
    v = horner(p, [np.broadcast_to(c[:, None], rr.shape) for c in coef], rr, check=False)
    y = p.phased(v).astype(np.float64)
    rel = np.abs(y - exact * 2.0**p.wy) / (exact * 2.0**p.wy)
    return (rel if valid is None else np.where(valid, rel, 0.0)).max(axis=1)


def _recentre(
    p: Params,
    coef: list[Int],
    r: Int,
    exact: NDArray[np.float64],
    rounds: int = 2,
    valid: NDArray[np.bool_] | None = None,
) -> None:
    n_seg = len(coef[0])
    rr = np.broadcast_to(r[None, :], (n_seg, len(r)))
    for _ in range(rounds):
        v = horner(p, [np.broadcast_to(c[:, None], rr.shape) for c in coef], rr, check=False)
        err = p.phased(v).astype(np.float64) - exact * 2.0**p.wy
        hi, lo = (
            (err, err) if valid is None else (np.where(valid, err, -np.inf), np.where(valid, err, np.inf))
        )
        mid = 0.5 * (hi.max(axis=1) + lo.min(axis=1))
        mid = np.where(np.isfinite(mid), mid, 0.0)  # a segment with no reachable input keeps its coefficient
        coef[0] = coef[0] - np.round(mid * 2.0**p.guard).astype(np.int64)
    v = horner(p, [np.broadcast_to(c[:, None], rr.shape) for c in coef], rr, check=False)
    coef[0] = coef[0] - np.maximum(0, v.max(axis=1) - ((1 << p.frac[0]) - 1))
