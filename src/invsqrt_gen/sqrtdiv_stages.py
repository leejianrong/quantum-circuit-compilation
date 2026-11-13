# ruff: noqa: E501
"""Stages of the square-root-and-division circuit on the recorder (QCC-13): our own code.

Every stage appends to a `Rec` program; the full circuit is `replay(program)`, the phase section, then
`replay(inverse(program))`. Qubits are virtual ints, arrays are lists.
"""

import itertools
from typing import Any

import kickmix as km  # type: ignore[import-not-found,unused-ignore]

from invsqrt_gen.build import ripple_add as _ripple_add
from invsqrt_gen.defadd import fd_add, md_add
from invsqrt_gen.rec import Rec

DEFER = {"on": False, "split_over": 12}
_KEYS = itertools.count()


def _add_fwd(b: Any, bind: Any, a: Any, t: Any, cin: Any, key: Any, split: Any) -> None:
    bind.store[key] = fd_add(b, km.array(a), km.array(t), cin)


def _add_inv(b: Any, bind: Any, a: Any, t: Any, cin: Any, key: Any, split: Any) -> None:
    md_add(b, km.array(a), km.array(t), bind.store.pop(key), cin, split[1])


def ripple_add(r: Rec, a: Any, t: Any, subtract: bool = False, cin: Any = None) -> None:
    """`t +-= a + cin`: the deferred-phase adder pair when `DEFER["on"]`, else the plain ripple adder."""
    if not DEFER["on"]:
        _ripple_add(r, a, t, subtract=subtract, cin=cin)
        return
    t = list(t)
    n_c = max(0, len(t) - 2)
    split = (n_c + 1) // 2 if n_c > int(DEFER["split_over"]) else None
    if subtract:
        r.x(t)
    r.macro(_add_fwd, _add_inv, list(a), t, cin, ("k", next(_KEYS)), ("sp", split))
    if subtract:
        r.x(t)


LEVELS = (2, 4, 8, 16)  # even normalisation shifts, binary digits of 2 k, k = 0 .. 10


def _and_all(r: Rec, qs: list[int]) -> tuple[int, list[int]]:
    """AND chain of `qs`: returns the wire holding the AND and the chain wires (for `_unand`)."""
    if len(qs) == 1:
        return qs[0], []
    acc = r.alloc_qubits(len(qs) - 1)
    r.init_and(qs[0], qs[1], acc[0])
    for i in range(1, len(qs) - 1):
        r.init_and(acc[i - 1], qs[i + 1], acc[i])
    return acc[-1], acc


def _unand(r: Rec, qs: list[int], acc: list[int]) -> None:
    if not acc:
        return
    for i in range(len(qs) - 2, 0, -1):
        r.del_and(acc[i - 1], qs[i + 1], acc[i])
    r.del_and(qs[0], qs[1], acc[0])
    r.free(acc)


def normalise_even(r: Rec, x: list[int]) -> list[int]:
    """`x := x 4^k` in place (22 qubits, LSB first) with `k` in 0..10; returns 4 flag wires, LSB first of `k`.

    Largest shift first: the flag of shift `m` is set when the top `m` bits are all zero (their AND after an
    X), and then a row of controlled swaps moves the word up by `m`.
    """
    flags = r.alloc_qubits(len(LEVELS))
    n = len(x)
    for jf in range(len(LEVELS) - 1, -1, -1):
        m = LEVELS[jf]
        top = x[n - m :]
        r.x(top)
        last, acc = _and_all(r, list(top))
        r.cx(last, flags[jf])
        _unand(r, list(top), acc)
        r.x(top)
        for i in range(n - m - 1, -1, -1):
            r.cswap(flags[jf], x[i], x[i + m])
    return flags


def sqrt_root(
    r: Rec, x: list[int], widths: list[int], steps: int = 13
) -> tuple[list[int], list[int], list[int]]:
    """In-place non-restoring root of the normalised `n` in `x`; see `sqrtdiv_build.sqrt_root`.

    Returns `(Q, W, zeros)`: root bits LSB first (the top one is the constant `one` wire), the signed remainder window
    and the consumed radicand wires that are |0> again and may be reused.
    """
    zeros: list[int] = []

    def take() -> int:
        return zeros.pop() if zeros else r.alloc_qubits(1)[0]

    def fit(w: list[int], width: int, signed: bool = True) -> list[int]:
        while len(w) > width:
            r.cx(w[-2], w[-1])
            zeros.append(w.pop())
        while len(w) < width:
            top = take()
            if signed:
                r.cx(w[-1], top)
            w.append(top)
        return w

    one = r.alloc_qubits(1)[0]
    r.x(one)
    q = [one]
    lo, hi = x[20], x[21]
    r.x(lo)
    r.cx(lo, hi)
    w = fit([lo, hi], widths[0], signed=False)
    for j in range(1, steps):
        low = [x[20 - 2 * j], x[21 - 2 * j]] if j <= 10 else [take(), take()]
        win = low + w
        ctl = q[0]
        sq = take()
        r.cx(ctl, sq)
        r.x(sq)
        r.cx(ctl, win)
        ripple_add(r, [sq] + q, win[1:], cin=win[0])
        r.x(win[0])
        r.cx(ctl, win)
        r.x(sq)
        r.cx(ctl, sq)
        zeros.append(sq)
        w = fit(win, widths[j])
        qn = take()
        r.cx(w[-1], qn)
        r.x(qn)
        q = [qn] + q
    return q, w, zeros


def finish_root(r: Rec, q: list[int], w: list[int], zeros: list[int]) -> list[int]:
    """`R -> t = 16 n - Q^2 - Q - 1` (14 signed bits): add `Q` to `R` complemented by `[R >= 0]` with carry-in that bit."""
    c = q[0]
    cc = zeros.pop() if zeros else r.alloc_qubits(1)[0]
    r.cx(c, cc)
    r.cx(c, w)
    ripple_add(r, q, w, cin=cc)
    r.cx(c, w)
    r.cx(c, cc)
    zeros.append(cc)
    while len(w) > 14:
        r.cx(w[-2], w[-1])
        zeros.append(w.pop())
    return w


def regs(**kw: Any) -> dict[str, Any]:
    return kw


def _cadd(r: Rec, ctl: int, addend: list[int], target: list[int], subtract: bool = False) -> None:
    """`target +-= ctl * addend` (addend aligned at `target[0]`): AND temporaries, one add, measured clean-up."""
    if not addend:
        return
    tmp = r.alloc_qubits(len(addend))
    for q, a in zip(tmp, addend, strict=True):
        r.init_and(ctl, a, q)
    ripple_add(r, tmp, target, subtract=subtract)
    for q, a in zip(tmp, addend, strict=True):
        r.del_and(ctl, a, q)
    r.free(tmp)


def load_table(
    r: Rec, q: list[int], words: list[int], d_bits: int, e_bits: int
) -> tuple[list[int], list[int]]:
    """`D, E := table[a]` with `a` the top 7 bits of the root `v` (`q[5:12]`)."""
    dw = r.alloc_qubits(d_bits)
    ew = r.alloc_qubits(e_bits)
    r.lookup(words, q[5:12], dw + ew)
    return dw, ew


def refine_d(r: Rec, q: list[int], dw: list[int], ew: list[int]) -> None:
    """`D -= sum_i u_i (E >> (6 - i))`, `u = q[0:5]`: the linear refinement by the low root bits."""
    for i in range(5):
        _cadd(r, q[i], ew[6 - i :], dw, subtract=True)


def product(
    r: Rec, t: list[int], dw: list[int], p_bits: int, sh: int, init_minus_one: bool = True
) -> list[int]:
    """`P = sum_{i<13} t_i (D >> (sh - i)) - t_13 (D << (13 - sh)) + (D >> (sh + 1)) + (D >> (sh + 2))` (signed)."""
    p = r.alloc_qubits(p_bits)
    if init_minus_one:  # the register holds P - 1 (so that ~ of it is -P, see `numerator_inplace`)
        r.x(p)
    for i in range(13):
        if i <= sh:
            _cadd(r, t[i], dw[sh - i :], p)
        else:
            _cadd(r, t[i], dw, p[i - sh :])
    _cadd(r, t[13], dw, p[13 - sh :], subtract=True)
    ripple_add(r, dw[sh + 1 :], p)
    ripple_add(r, dw[sh + 2 :], p)
    return p


def numerator_window(r: Rec, q: list[int], p: list[int], fp: int) -> list[int]:
    """`r_1 = 2 (1 - P) - s` in units `2^-fp` as a signed window of `fp + 2` wires (LSB first).

    `P' = P + 2^(p-1)` (sign bit flipped) is non-negative, so `r_1 = K + ((~d) << (fp - 13)) - (P' << 1)` with the
    constant `K` a few X gates.
    """
    nb = len(p)
    sh = fp - 13
    w = r.alloc_qubits(fp + 2)
    r.x(p[-1])  # P' = P + 2^(nb-1)
    # K = (1 << sh) + (2^(nb) - 2^... ) : r_1 = (2^14 - d) 2^sh + 2^(nb) - 2 P'  with 2^(nb) from the removed offset
    # (2^14 - d) 2^sh = (~d + 1) 2^sh: (~d) << sh plus 1 << sh
    r.x(w[sh])
    r.x(w[nb])
    r.x(q)  # ~Q: bits of ~d above d_0 (d_0 = 1 so ~d_0 = 0)
    ripple_add(r, q, w[sh + 1 :])
    r.x(q)
    ripple_add(r, p, w[1:], subtract=True)
    r.x(p[-1])
    return w


def divide_rows(r: Rec, q: list[int], w: list[int], fp: int, digits: int) -> tuple[list[int], list[int]]:
    """Consuming non-restoring division rows 2 .. `digits`; returns `(digit wires g_2 .. g_J, final window)`.

    `g_j = [r_{j-1} >= 0]`. Each row doubles `r` (relabelling, plus a fresh LSB once the window reaches 13
    fractional bits), complements the window by `g` before and after one ripple add of `d = 2 Q + 1`, and frees the
    redundant top wire, which becomes the next digit wire.
    """
    f = fp
    zeros: list[int] = []
    gs: list[int] = []
    for _ in range(2, digits + 1):
        g = zeros.pop() if zeros else r.alloc_qubits(1)[0]
        r.cx(w[-1], g)
        r.x(g)
        gs.append(g)
        if f > 13:
            f -= 1
        else:
            w = [r.alloc_qubits(1)[0]] + w
        r.cx(g, w)
        ripple_add(r, q, w[f - 12 :], cin=w[f - 13])
        r.x(w[f - 13])
        r.cx(g, w)
        r.cx(w[-2], w[-1])
        zeros.append(w.pop())
    for z in zeros:
        r.free(z)
    return gs, w


def numerator_inplace(r: Rec, q: list[int], p: list[int], fp: int) -> list[int]:
    """`r_1 = 2 (1 - P) - s` built in place on the product wires.

    The product register holds `Pr = P - 1` (it was initialised to all ones), so `~Pr = -P` and the window is
    `[0, ~Pr (2x), sign copies] + ((2^14 - d) << sh)` with `2^14 - d = [1, ~Q_0 .. ~Q_12]` (`d` is odd: no carry). The
    product wires become window bits 1 ..., nothing is copied except the sign extension.
    """
    sh = fp - 13
    nb = len(p)
    low = r.alloc_qubits(1)
    r.x(p)  # ~Pr
    ext = r.alloc_qubits(fp + 2 - 1 - nb)
    r.cx(p[-1], ext)
    w = low + list(p) + ext
    r.x(q)
    ripple_add(r, q, w[sh + 1 :], cin=w[sh])
    r.x(w[sh])
    r.x(q)
    return w
