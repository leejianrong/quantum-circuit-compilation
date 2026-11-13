"""Circuit stages of the square-root-and-division design (QCC-13), our own code.

Stage 1, `sqrt_root`: the non-restoring digit recurrence for `R = isqrt(16 n)` on the normalised `n`
(22 qubits), in place: the radicand qubits are consumed pair by pair and become the low bits of the
signed remainder window.

    R_0 = 0, Q_0 = 0;  for each radicand pair p (13 of them: 11 real ones, then 00, 00):
        R <- 4 R + p - (4 Q + 1)   if R >= 0        (Q's lsb is [R >= 0])
        R <- 4 R + p + (4 Q + 3)   if R <  0
        Q <- 2 Q + [R >= 0]

Both cases are one ripple add of `A = 4 Q + 1 + 2 s` (`s = [R < 0]`) into the window, complemented by
`[R >= 0]` before and after. At the end `Q = isqrt(16 n)` (13 bits, the top one always 1) and `R` is
`rem` or `rem - 2 Q - 1`. Checked against the integer recurrence in
`tests/unit/test_invsqrt_sqrtdiv_build.py` (102 Toffolis, 42 qubits).
"""

import kickmix as km  # type: ignore[import-not-found,unused-ignore]
import numpy as np
from numpy.typing import NDArray

from invsqrt_gen.build import ripple_add


def nr_model(n: NDArray[np.int64]) -> tuple[NDArray[np.int64], NDArray[np.int64], list[int]]:
    """Integer model of the recurrence: `(Q, R, widths)` where `widths[j]` is the signed width `R_j` needs."""
    m = n << 4
    q = np.zeros_like(n)
    r = np.zeros_like(n)
    widths: list[int] = []
    for j in range(13):
        p = (m >> (2 * (12 - j))) & 3
        r = np.where(r >= 0, 4 * r + p - (4 * q + 1), 4 * r + p + (4 * q + 3))
        q = 2 * q + (r >= 0)
        widths.append(int(max(abs(int(r.min())), abs(int(r.max())) + 1)).bit_length() + 1)
    return q, r, widths


class Pool:
    """Zero qubits ready for reuse. Register qubits (the input `x`) cannot be freed, so they wait here."""

    def __init__(self, b: km.CircuitBuilder, fixed: km.array) -> None:
        self.b = b
        self.fixed = {int(str(q)[1:]) for q in fixed}
        self.zeros: list[km.q] = []

    def take(self) -> km.q:
        return self.zeros.pop() if self.zeros else self.b.alloc_qubits(1)[0]

    def give(self, q: km.q) -> None:
        """Return a qubit that is |0>."""
        if int(str(q)[1:]) in self.fixed:
            self.zeros.append(q)
        else:
            self.b.free(km.array([q]))


def _fit_window(pool: Pool, w: list[km.q], width: int, signed: bool = True) -> list[km.q]:
    """Shrink (clear a redundant top sign copy) or grow (copy the sign, or zero extend) the window `w`."""
    b = pool.b
    while len(w) > width:
        b.cx(w[-2], w[-1])  # the top two bits are equal, so this clears the top one
        pool.give(w.pop())
    while len(w) < width:
        top = pool.take()
        if signed:
            b.cx(w[-1], top)
        w.append(top)
    return w


def sqrt_root(
    b: km.CircuitBuilder, x: km.array, widths: list[int], steps: int = 13
) -> tuple[list[km.q], list[km.q], Pool]:
    """In-place root of the normalised `n` held in `x` (22 qubits, LSB first), `steps` of the 13 digit steps.

    Returns `(Q, W, pool)`: the root bits so far (LSB first; the top one is a qubit holding 1), the signed
    remainder window (LSB first) and the pool of zero qubits (consumed radicand qubits and others).
    `widths` comes from `nr_model` and fixes how many qubits the window keeps per step.
    """
    pool = Pool(b, x)
    one = b.alloc_qubits(1)[0]
    b.x(one)
    q: list[km.q] = [one]
    # step 1: R = p - 1 for p = (n21, n20) in {1, 2, 3}: a 2-bit decrement, no Toffoli
    lo, hi = x[20], x[21]
    b.x(lo)
    b.cx(lo, hi)
    w = _fit_window(pool, [lo, hi], widths[0], signed=False)
    for j in range(1, steps):
        # X = 4 R + p: the pair qubits (or two fresh zeros) are the new low bits
        low = [x[20 - 2 * j], x[21 - 2 * j]] if j <= 10 else [pool.take(), pool.take()]
        win = low + w
        ctl = q[0]  # [R >= 0]
        sq = pool.take()
        b.cx(ctl, sq)
        b.x(sq)  # s = [R < 0]
        b.cx(ctl, km.array(win))  # complement the window when R >= 0
        # A = 1 + 2 s + 4 Q: bit 0 is the carry-in, bit 1 is s, the rest is Q
        ripple_add(b, km.array([sq] + q), km.array(win[1:]), cin=win[0])
        b.x(win[0])
        b.cx(ctl, km.array(win))
        b.x(sq)
        b.cx(ctl, sq)
        pool.give(sq)
        w = _fit_window(pool, win, widths[j])
        qn = pool.take()
        b.cx(w[-1], qn)
        b.x(qn)  # the new root bit [R >= 0]
        q = [qn] + q
    return q, w, pool
