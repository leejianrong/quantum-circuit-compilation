"""Circuit builder: normalise, look up, Horner, de-normalise, phase, uncompute.

Layout (all in one builder; the only named register is `x`, as the verifier requires):

    x          22 qubits, shifted in place to `x_norm` (leading one at the top)
    flags      5 qubits, binary leading zero count z; z % 2 picks the table half, z // 2 is the shift s
    V_0..V_d   Horner registers, loaded by one table lookup on the a bits below the leading one and z % 2
    scratch    AND temporaries for multiplier rows, reused for the de-normalisation headroom

Forward: normalise, lookup, Horner steps `V_j -= T(r V_{j+1})`, shift the phased word of V_0 left by `s`
(into headroom), phase by `Z_POW` per bit. Backward is the exact mirror, with measurement-based
uncompute for ANDs and the lookup.
"""

from dataclasses import dataclass
from fractions import Fraction

import kickmix as km  # type: ignore[import-not-found,unused-ignore]

from invsqrt_gen.model import Digit, Tables, digit_plan
from invsqrt_gen.params import FRAC, MAX_PAIRS, WIDTH, Params

LEVELS = 4  # de-normalisation shift levels 1, 2, 4, 8 (the binary digits of s = z // 2)
Z_LEVELS = 5  # leading-zero-count levels 1, 2, 4, 8, 16 bits


def _swaps(
    b: km.CircuitBuilder, ctl: km.q, reg: km.array, m: int, width: int, inverse: bool, descending: bool
) -> None:
    """Controlled move of `reg[0:width]` up by `m` into zero slots (or back), one CSWAP per bit."""
    idx = range(width - 1, -1, -1) if descending != inverse else range(width)
    for i in idx:
        b.cswap(ctl, reg[i], reg[i + m])


def normalise(b: km.CircuitBuilder, x: km.array, flags: km.array, inverse: bool = False) -> None:
    """`x := x 2^z` with `flags` the binary leading zero count `z` (5 levels, largest first).

    `flags[0]` is the parity of `z`; `flags[1:]` are the digits of `s = z // 2`.
    """
    order = range(Z_LEVELS) if inverse else range(Z_LEVELS - 1, -1, -1)
    for j in order:
        m = 1 << j  # bits shifted at this level
        top = x[WIDTH - m :]
        if not inverse:
            b.x(top)
            b.multi_controlled_x(top, flags[j])
            b.x(top)
        # the top m bits are zero whenever the flag is set, so the shift never wraps
        _swaps(b, flags[j], x, m, WIDTH - m, inverse, descending=True)
        if inverse:
            b.x(top)
            b.multi_controlled_x(top, flags[j])
            b.x(top)


def load(
    b: km.CircuitBuilder, p: Params, t: Tables, addr: km.array, regs: list[km.array], inverse: bool
) -> None:
    """`regs := table[address]` (unary iteration over the reachable range) or its measured uncompute."""
    words = t.words()
    flat = km.array([q for r in regs for q in r])
    if inverse:
        b.del_lookup(table=words, address=addr, target=flat)
        return
    with b.unary_iteration(addr, p.entries) as it:
        for v, match in it:
            bits = [flat[k] for k in range(len(flat)) if (words[v] >> k) & 1]
            if bits:
                b.cx(match, km.array(bits))


def ripple_add(b: km.CircuitBuilder, a: km.array, t: km.array, subtract: bool = False) -> None:
    """`t += a` (or `-=`) modulo 2^len(t), `a` unchanged and shorter than `t`; `len(t) - 1` Toffolis.

    Gidney-style carry chain: carries are computed into fresh ancillas on the way up (one AND per
    bit, also through the bits of `t` above `a`, where the addend is zero) and cleared by measurement
    on the way down, where the sum bits are also written.
    """
    w, m = len(a), len(t)
    if subtract:
        b.x(t)
    c = b.alloc_qubits(m - 1)
    for i in range(m - 1):
        if i < w:
            if i:
                b.cx(c[i - 1], a[i])
                b.cx(c[i - 1], t[i])
            b.init_and(a[i], t[i], c[i])
            if i:
                b.cx(c[i - 1], c[i])
        else:
            b.init_and(c[i - 1], t[i], c[i])
    top = m - 1
    if top < w:  # not used by the callers (the addend is always shorter than the target)
        raise ValueError("addend must be shorter than the target")
    b.cx(c[top - 1], t[top])
    for i in range(m - 2, -1, -1):
        if i < w:
            if i:
                b.cx(c[i - 1], c[i])
            b.del_and(a[i], t[i], c[i])
            if i:
                b.cx(c[i - 1], a[i])
            b.cx(a[i], t[i])
        else:
            b.del_and(c[i - 1], t[i], c[i])
            b.cx(c[i - 1], t[i])
    b.free(c)
    if subtract:
        b.x(t)


@dataclass
class Level:
    """Register V_j split at `K = f_j - a`: rows only touch `lo + [sign]`; `hi` takes the borrow once."""

    lo: km.array
    sign: km.q | None
    hi: km.array
    ext: km.array | None = (
        None  # centered generator: the qubits above `lo` in the add window (instead of `sign`)
    )

    @property
    def tail(self) -> list[km.q]:
        """Qubits above `lo` that take part in each add."""
        return list(self.ext) if self.ext is not None else [self.sign]

    @property
    def value(self) -> km.array:
        return km.array(list(self.lo) + list(self.hi))


def alloc_level(b: km.CircuitBuilder, p: Params, j: int) -> Level:
    f = p.frac[j]
    if j == p.degree:  # never modified after the lookup
        return Level(b.alloc_qubits(f), None, km.array([]))
    k = f - p.a
    return Level(b.alloc_qubits(k), b.alloc_qubits(1)[0], b.alloc_qubits(f - k))


def _booth_digit(
    b: km.CircuitBuilder,
    p: Params,
    x: km.array,
    src: km.array,
    tgt: Level,
    dg: Digit,
    inverse: bool,
    flip: bool = False,
) -> None:
    """`V_j -= d_n floor(V_{j+1} 2^e)` (or `+=`) for one radix-4 Booth digit of the remainder.

    The magnitude selects `sel1 = b_{2n} ^ b_{2n-1}` and `sel2 = !sel1 & (b_{2n+1} ^ b_{2n})` choose `V`
    or `2V` into a clean operand register (one AND per bit each, cleared by measurement); the sign
    `b_{2n+1}` turns the subtraction into an addition by complementing the window around the add.
    """
    rw, f = p.rwidth, len(src)

    def bit(i: int) -> km.q | None:
        return x[i] if 0 <= i < rw else None

    b0, b1, bm = bit(2 * dg.n), bit(2 * dg.n + 1), bit(2 * dg.n - 1)
    s1 = b.alloc_qubits(1)[0]
    for q in (b0, bm):
        if q is not None:
            b.cx(q, s1)
    has2 = b0 is not None
    if has2:
        u, s2 = b.alloc_qubits(1)[0], b.alloc_qubits(1)[0]
        for q in (b1, b0):
            if q is not None:
                b.cx(q, u)
        b.x(s1)
        b.init_and(s1, u, s2)
        b.x(s1)
    lo = max(0, dg.e1)
    top = f - 1 + dg.e1 + (1 if has2 else 0)
    op = b.alloc_qubits(top - lo + 1)
    parts: list[tuple[int, int | None, int | None]] = []
    for pos in range(lo, top + 1):
        k1 = pos - dg.e1 if dg.kmin1 <= pos - dg.e1 <= f - 1 else None
        k2 = pos - dg.e1 - 1 if has2 and dg.kmin2 <= pos - dg.e1 - 1 <= f - 1 else None
        parts.append((pos, k1, k2))
        if k1 is not None:
            b.init_and(s1, src[k1], op[pos - lo])
            if k2 is not None:
                b.ccx(s2, src[k2], op[pos - lo])
        elif k2 is not None:
            b.init_and(s2, src[k2], op[pos - lo])
    window = km.array(list(tgt.lo[lo:]) + tgt.tail)
    if b1 is not None:
        b.cx(b1, window)
    ripple_add(b, op, window, subtract=(not inverse) != flip)
    if b1 is not None:
        b.cx(b1, window)
    flags = b.alloc_bits(len(op))
    b.hmr(op, flags)
    for pos, k1, k2 in parts:
        b.push_condition(flags[pos - lo])
        if k1 is not None:
            b.cz(s1, src[k1])
        if k2 is not None:
            b.cz(s2, src[k2])
        b.pop_condition()
    b.free(flags)
    b.free(op)
    if has2:
        b.x(s1)
        b.del_and(s1, u, s2)
        b.x(s1)
        for q in (b1, b0):
            if q is not None:
                b.cx(q, u)
        b.free(u)
        b.free(s2)
    for q in (b0, bm):
        if q is not None:
            b.cx(q, s1)
    b.free(s1)


def horner_step(
    b: km.CircuitBuilder,
    p: Params,
    j: int,
    x: km.array,
    levels: list[Level],
    inverse: bool,
    flip: bool = False,
) -> None:
    """`V_j -= T(r V_{j+1})` (or `+=` when inverse) as one add per Booth digit of the remainder.

    Digits add into `lo + [sign]` only. The product is below 2^K, so the two's-complement window never
    wraps more than once and the borrow lands in `sign`; one controlled decrement then moves it into
    `hi`. The inverse increments `hi` back first, and the digit adds' carries clear `sign` again.
    """
    src, tgt = levels[j + 1].value, levels[j]
    assert tgt.sign is not None
    if inverse and len(tgt.hi):
        b.iadd(1, target=tgt.hi, control=tgt.sign)
    plan = digit_plan(p, j)
    for dg in reversed(plan) if inverse else plan:
        _booth_digit(b, p, x, src, tgt, dg, inverse, flip)
    if not inverse and len(tgt.hi):
        b.isub(1, target=tgt.hi, control=tgt.sign)


def phase_word(b: km.CircuitBuilder, p: Params, word: km.array, flags: km.array, inverse: bool) -> None:
    """Shift `word` (wy bits) up by `s` inside `word + headroom`, phase, shift back."""
    wy = p.wy
    f_bits = wy + MAX_PAIRS
    # ascending levels need windows wy, wy+1, wy+3, wy+2 (flag 3 excludes flags 2 and larger totals)
    windows = [wy, wy + 1, wy + 3, wy + 2]
    levels = range(LEVELS - 1, -1, -1) if inverse else range(LEVELS)
    if not inverse:
        for j in levels:
            _swaps(b, flags[j], word, 1 << j, windows[j], False, descending=True)
        for i in range(f_bits):
            b.z_pow(word[i], Fraction(2) ** (i - f_bits + 1))
        return
    for j in levels:
        _swaps(b, flags[j], word, 1 << j, windows[j], True, descending=True)


def build(p: Params, t: Tables) -> km.Circuit:
    """The full circuit for parameters `p` and fitted tables `t`."""
    b = km.CircuitBuilder()
    x = b.create_quantum_register(WIDTH, name="x")
    flags = b.alloc_qubits(Z_LEVELS)
    shift_flags = flags[1:]
    levels = [alloc_level(b, p, j) for j in range(p.degree + 1)]
    regs = [lv.value for lv in levels]
    addr = km.array(list(x[p.rwidth : WIDTH - 1]) + [flags[0]])  # segment bits, then the parity

    with b.mark("normalise"):
        normalise(b, x, flags)
    with b.mark("lookup"):
        load(b, p, t, addr, regs, inverse=False)
    for j in range(p.degree - 1, -1, -1):
        with b.mark(f"horner{j}"):
            horner_step(b, p, j, x, levels, inverse=False)
    with b.mark("phase"):
        # headroom for the shift: the phased word is the top wy bits of V_0, and the 10 qubits above
        # it are fresh (clean at this point)
        headroom = b.alloc_qubits(MAX_PAIRS)
        word = km.array(list(regs[0][p.guard :]) + list(headroom))
        phase_word(b, p, word, shift_flags, inverse=False)
        phase_word(b, p, word, shift_flags, inverse=True)
        b.free(headroom)
    for j in range(p.degree):
        with b.mark(f"unhorner{j}"):
            horner_step(b, p, j, x, levels, inverse=True)
    with b.mark("unlookup"):
        load(b, p, t, addr, regs, inverse=True)
    with b.mark("unnormalise"):
        normalise(b, x, flags, inverse=True)
    for lv in levels:
        for q in (lv.lo, lv.hi):
            b.free(q)
        if lv.sign is not None:
            b.free(lv.sign)
    b.free(flags)
    return b.finish_circuit()


__all__ = ["FRAC", "build", "normalise"]
