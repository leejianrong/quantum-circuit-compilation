"""Split-phase generator (QCC-13): the phase of `V_0` is applied as a coarse word and a fine word.

`V_0 = c_0 - P` with `c_0 = c_hi 2^K + c_lo` (`K = f_0 - a`) and `P = T(r V_1) >= 0`. Write
`n = 2^K - c_lo` (the table stores `n`, so the Horner register ADDS the product) and `T = n + P < 2^(K+1)`.
Then `V_0 = (c_hi + 1) 2^K - T` exactly, and since phases add

    exp(2 pi i 2^(s-10) V_0 / 2^f)  =  exp(+ coarse word (c_hi + 1)) * exp(- fine word T).

* The coarse word is a table output of the address alone: it is loaded with the other coefficients in one
  unary-iteration pass, phased, and cleared at once by a measurement-based lookup (about 25 Toffolis), so
  the Horner stage never holds `c_hi` (7 qubits) and has no borrow into a high part.
* The fine word `T >> guard` is the whole `V_0` register (K bits plus the carry qubit); the phased integer is
  `ceil(V_0 / 2^guard)`, which the model in `model.py` reproduces with `Params(ceil=True)`.

Two ways to phase the coarse word, chosen by `coarse`:

* `barrel`: shift the word up by `s` with four levels of controlled swaps, rotate, shift back.
* `serial`: no shifted register at all. For every angle position one working qubit receives
  `XOR_s [s = s'] c_{k - s'}` (one Toffoli per term from a one-hot of `s`), takes the rotation, and is
  measured; the measurement fix-up is a conditional CZ per term (free).
"""

from fractions import Fraction

import kickmix as km  # type: ignore[import-not-found,unused-ignore]
import numpy as np

from invsqrt_gen.build import (
    LEVELS,
    Z_LEVELS,
    Level,
    _booth_digit,
    _swaps,
    alloc_level,
    horner_step,
    normalise,
    ripple_add,
)
from invsqrt_gen.model import (
    Tables,
    _shift,
    digit_plan,
    fit_tables,
    horner_pm1_levels,
    normalised_inputs,
    pm1_rows,
    reachable_mask,
)
from invsqrt_gen.params import MAX_PAIRS, WIDTH, Params


def fit_split(p: Params, passes: int = 3, stride: int = 13, polish: bool = False) -> Tables:
    """Tables for the split generator: the ordinary fit with ceiling rounding, `c_lo` never zero."""
    assert p.ceil, "the split generator needs Params(ceil=True)"
    t = fit_tables(p, passes=passes, stride=stride, polish=polish)
    k = p.frac[0] - p.a
    c0 = t.coef[0]
    t.coef[0] = np.where((c0 & ((1 << k) - 1)) == 0, c0 + 1, c0)  # n = 2^K - c_lo must fit K bits
    return t


def split_words(p: Params, t: Tables) -> tuple[list[int], list[int]]:
    """Per-address `(coarse words c_hi + 1, main words n | c_1 | c_2 ...)`."""
    k = p.frac[0] - p.a
    n_addr = 2 << p.a
    coarse, main = [0] * n_addr, [0] * n_addr
    for v in range(n_addr):
        c0 = int(t.coef[0][v])
        coarse[v] = (c0 >> k) + 1
        word, off = (1 << k) - (c0 & ((1 << k) - 1)), k
        for j in range(1, len(t.coef)):
            word |= int(t.coef[j][v]) << off
            off += p.frac[j]
        main[v] = word
    return coarse, main


def _angle(index: int, f_bits: int, sign: int) -> Fraction:
    """Half turns of the rotation for word position `index` of an `f_bits`-wide phase frame."""
    return sign * Fraction(2) ** (index - f_bits + 1)


def barrel_phase(
    b: km.CircuitBuilder,
    word: km.array,
    shift_flags: km.array,
    width: int,
    base: int,
    f_bits: int,
    sign: int,
    low_is_one: bool = False,
) -> None:
    """Shift `word` (`width` data bits, then headroom) up by `s`, rotate position `base + i`, shift back.

    With `low_is_one` the lowest data bit is a constant 1 (an odd table word). The first level's swap of that
    bit with the slot above it only has to flip both when the level's flag is set (the slot above is empty
    exactly then), which is two CNOTs instead of a Toffoli.
    """
    windows = [width, width + 1, width + 3, width + 2]

    def level(j: int, inverse: bool) -> None:
        if not (low_is_one and j == 0):
            _swaps(b, shift_flags[j], word, 1 << j, windows[j], inverse, descending=True)
            return
        if inverse:
            b.cx(shift_flags[0], word[0])
            b.cx(shift_flags[0], word[1])
        _swaps(b, shift_flags[0], word[1:], 1, windows[0] - 1, inverse, descending=True)
        if not inverse:
            b.cx(shift_flags[0], word[0])
            b.cx(shift_flags[0], word[1])

    for j in range(LEVELS):
        level(j, False)
    for i in range(len(word)):
        if base + i < f_bits:
            b.z_pow(word[i], _angle(base + i, f_bits, sign))
    for j in range(LEVELS - 1, -1, -1):
        level(j, True)


def _lit_and(b: km.CircuitBuilder, qa: km.q, va: int, qb: km.q, vb: int, out: km.q, undo: bool) -> None:
    """`out := [qa = va] & [qb = vb]` (or its measured clear)."""
    if not va:
        b.x(qa)
    if not vb:
        b.x(qb)
    if undo:
        b.del_and(qa, qb, out)
    else:
        b.init_and(qa, qb, out)
    if not vb:
        b.x(qb)
    if not va:
        b.x(qa)


def serial_phase(
    b: km.CircuitBuilder, word: km.array, shift_flags: km.array, base: int, f_bits: int, sign: int
) -> None:
    """Phase `word << s` bit by bit through one working qubit (no shifted register, no headroom)."""
    w = len(word)
    lo2, hi2 = b.alloc_qubits(4), b.alloc_qubits(3)
    for v in range(4):
        _lit_and(b, shift_flags[0], v & 1, shift_flags[1], v >> 1, lo2[v], undo=False)
    for v in range(3):
        _lit_and(b, shift_flags[2], v & 1, shift_flags[3], v >> 1, hi2[v], undo=False)
    onehot = b.alloc_qubits(MAX_PAIRS + 1)
    for v in range(MAX_PAIRS + 1):
        b.init_and(lo2[v & 3], hi2[v >> 2], onehot[v])
    for k in range(w + MAX_PAIRS):
        if base + k >= f_bits:
            continue
        terms = [(sh, k - sh) for sh in range(MAX_PAIRS + 1) if 0 <= k - sh < w]
        if not terms:
            continue
        work = b.alloc_qubits(1)
        for sh, bit in terms:
            b.ccx(onehot[sh], word[bit], work[0])
        b.z_pow(work[0], _angle(base + k, f_bits, sign))
        flag = b.alloc_bits(1)
        b.hmr(work, flag)
        b.push_condition(flag[0])
        for sh, bit in terms:
            b.cz(onehot[sh], word[bit])
        b.pop_condition()
        b.free(flag)
        b.free(work)
    for v in range(MAX_PAIRS, -1, -1):
        b.del_and(lo2[v & 3], hi2[v >> 2], onehot[v])
    b.free(onehot)
    for v in range(2, -1, -1):
        _lit_and(b, shift_flags[2], v & 1, shift_flags[3], v >> 1, hi2[v], undo=True)
    for v in range(3, -1, -1):
        _lit_and(b, shift_flags[0], v & 1, shift_flags[1], v >> 1, lo2[v], undo=True)
    b.free(hi2)
    b.free(lo2)


def build_split(p: Params, t: Tables, coarse: str = "barrel", max_qubits: int | None = None) -> km.Circuit:
    """The split-phase circuit; `coarse` is `barrel` or `serial` (see the module docstring)."""
    assert p.ceil and coarse in ("barrel", "serial")
    b = km.CircuitBuilder()
    if max_qubits is not None:
        b.set_max_qubits(max_qubits)
    x = b.create_quantum_register(WIDTH, name="x")
    flags = b.alloc_qubits(Z_LEVELS)
    shift_flags = flags[1:]
    k = p.frac[0] - p.a
    # V_0 has no high part: that is the coarse word, loaded, phased and cleared before the Horner stage
    levels = [Level(b.alloc_qubits(k), b.alloc_qubits(1)[0], km.array([]))]
    levels += [alloc_level(b, p, j) for j in range(1, p.degree + 1)]
    addr = km.array(list(x[p.rwidth : WIDTH - 1]) + [flags[0]])
    cwords, mwords = split_words(p, t)
    cw = b.alloc_qubits(p.a + 1)
    main = km.array(list(levels[0].lo) + [q for lv in levels[1:] for q in lv.value])
    f_bits = p.wy + MAX_PAIRS

    with b.mark("normalise"):
        normalise(b, x, flags)
    with b.mark("lookup"):
        with b.unary_iteration(addr, p.entries) as it:
            for v, match in it:
                bits = [cw[i] for i in range(len(cw)) if (cwords[v] >> i) & 1]
                bits += [main[i] for i in range(len(main)) if (mwords[v] >> i) & 1]
                if bits:
                    b.cx(match, km.array(bits))
    with b.mark("coarse"):
        base = k - p.guard  # position of the lowest coarse bit in the phase frame
        if coarse == "barrel":
            head = b.alloc_qubits(MAX_PAIRS)
            low_one = all(w & 1 for w in cwords)
            barrel_phase(b, km.array(list(cw) + list(head)), shift_flags, len(cw), base, f_bits, 1, low_one)
            b.free(head)
        else:
            serial_phase(b, cw, shift_flags, base, f_bits, 1)
        b.del_lookup(table=cwords, address=addr, target=cw)
    b.free(cw)
    for j in range(p.degree - 1, -1, -1):
        with b.mark(f"horner{j}"):
            horner_step(b, p, j, x, levels, inverse=False, flip=(j == 0))
    with b.mark("fine"):
        head = b.alloc_qubits(MAX_PAIRS)
        word = km.array(list(levels[0].lo[p.guard :]) + [levels[0].sign] + list(head))
        barrel_phase(b, word, shift_flags, k - p.guard + 1, 0, f_bits, -1)
        b.free(head)
    for j in range(p.degree):
        with b.mark(f"unhorner{j}"):
            horner_step(b, p, j, x, levels, inverse=True, flip=(j == 0))
    with b.mark("unlookup"):
        b.del_lookup(table=mwords, address=addr, target=main)
    with b.mark("unnormalise"):
        normalise(b, x, flags, inverse=True)
    for lv in levels:
        b.free(lv.lo)
        b.free(lv.hi)
        if lv.sign is not None:
            b.free(lv.sign)
    b.free(flags)
    return b.finish_circuit()


def centered_words(p: Params, t: Tables) -> tuple[list[int], list[int]]:
    """Per-address `(coarse word, main word)` of the centered generator.

    `V_0 = CW + W` with `CW = (c_0 >> (K-1)) 2^(K-1) - 2^(K-2)` (a table word of the address) and the window
    `W = (c_0 mod 2^(K-1)) + 2^(K-2) - P` in `[0, 2^K)`, `K = f_0 - a`. The coarse word is `CW >> (K - 2)`.
    The middle levels hold `c_j mod 2^K` in `lo`, `(c_j >> K) - 1` in `hi` and a `1` in the first window qubit
    above `lo`, so the window `lo + 2^K - Q` stays inside `[0, 2^(K+2))`; `hi + ext` is the high part.

    Signed-digit levels (`Params.pm1`) need one extension qubit only: the table loads it with `e = 1` exactly
    when `lo < 2^(K-2)` (and `hi = (c_j >> K) - e`), which keeps `lo + e 2^K +- Q` inside `[0, 2^(K+1))`
    because `|Q| < 2^(K-2)`; `hi + ext` is again the high part.
    """
    d, a = p.degree, p.a
    k0 = p.frac[0] - a
    coarse, main = [0] * (2 << a), [0] * (2 << a)
    for v in range(2 << a):
        c0 = int(t.coef[0][v])
        coarse[v] = 2 * (c0 >> (k0 - 1)) - 1
        word, off = (c0 & ((1 << (k0 - 1)) - 1)) + (1 << (k0 - 2)), k0
        for j in range(1, d):
            kj = p.frac[j] - a
            cj = int(t.coef[j][v])
            assert cj >> kj >= 1
            word |= (cj & ((1 << kj) - 1)) << off
            off += kj
            if p.pm1:  # one window extension qubit, loaded with the table: the offset is 2^K only when needed
                e = 1 if (cj & ((1 << kj) - 1)) < (1 << (kj - 2)) else 0
                word |= e << off
                off += 1
                word |= ((cj >> kj) - e) << off
            else:
                word |= ((cj >> kj) - 1) << off
            off += a
        word |= int(t.coef[d][v]) << off
        main[v] = word
    return coarse, main


def unused_top_bits(p: Params, t: Tables) -> list[int]:
    """Top bits of `V_j` (j >= 1) that are 0 for every input: `[d_0, d_1, ..]`, `d_0 = 0` always.

    The table word keeps those bit positions at 0 and no add ever carries into them (the model checks
    `V_j < 2^(f_j - d_j)` over all normalised inputs), so the registers can be that much narrower.
    """
    if not p.pm1:
        return [0] * (p.degree + 1)
    xn, par = normalised_inputs()
    a_idx = (par << p.a) | ((xn >> p.rwidth) & ((1 << p.a) - 1))
    vs = horner_pm1_levels(p, [c[a_idx] for c in t.coef], xn & ((1 << p.rwidth) - 1))
    return [0] + [p.frac[j] - int(vs[j].max()).bit_length() for j in range(1, p.degree + 1)]


def row_window_tops(p: Params, t: Tables) -> list[list[int]]:
    """For each Horner step `j` and signed-digit row: how many low window bits the row ever changes.

    The verifier runs exactly the reachable inputs, so a row whose carries never reach window bit `top` for
    any of them can skip the ripple above it (the circuit then differs from the model only on inputs nobody
    runs). The state before a row is the table window minus the earlier rows, evaluated with the model's own
    arithmetic.
    """
    if not p.pm1:
        return [[] for _ in range(p.degree)]
    xn, par = normalised_inputs()
    keep = reachable_mask()
    xn, par = xn[keep], par[keep]
    a_idx = (par << p.a) | ((xn >> p.rwidth) & ((1 << p.a) - 1))
    r = xn & ((1 << p.rwidth) - 1)
    coef = [c[a_idx] for c in t.coef]
    vs = horner_pm1_levels(p, coef, r)
    out: list[list[int]] = []
    for j in range(p.degree):
        kj = p.frac[j] - p.a
        if j == 0:
            window, w = kj, (coef[0] & ((1 << (kj - 1)) - 1)) + (1 << (kj - 2))
        elif p.pm1:
            u = coef[j] & ((1 << kj) - 1)
            window, w = kj + 1, u + np.where(u < (1 << (kj - 2)), 1 << kj, 0)
        else:
            window, w = kj + 2, (coef[j] & ((1 << kj) - 1)) + (1 << kj)
        tops = []
        for i, sh in pm1_rows(p, j):
            v = vs[j + 1]
            sl = _shift(v, sh)
            if p.rnd and sh < 0:
                sl = sl + ((v >> (-sh - 1)) & 1)
            w2 = (w - (2 * ((r >> i) & 1) - 1) * sl) % (1 << window)
            tops.append(max(int(np.max(w ^ w2)).bit_length(), max(0, sh) + 1))
            w = w2
        out.append(tops)
    return out


def compress_words(words: list[int], keep: list[int]) -> list[int]:
    """Each word restricted to the bit positions `keep` (in order)."""
    return [sum(((w >> k) & 1) << i for i, k in enumerate(keep)) for w in words]


def centered_step(
    b: km.CircuitBuilder,
    p: Params,
    j: int,
    x: km.array,
    levels: list[Level],
    inverse: bool,
    tops: list[int] | None = None,
) -> None:
    """`V_j -= T(rho V_{j+1})`, then `hi += ext` (undone first on the way back)."""
    src, tgt = levels[j + 1].value, levels[j]
    assert tgt.ext is not None
    if inverse and len(tgt.hi):
        if len(tgt.hi) > len(tgt.ext):
            ripple_add(b, tgt.ext, tgt.hi, subtract=True)
        else:
            b.isub(tgt.ext, target=tgt.hi)
    if p.pm1:
        window = km.array(list(tgt.lo) + list(tgt.ext if tgt.ext is not None else []))
        rows = pm1_rows(p, j)
        order = list(range(len(rows)))
        for k in reversed(order) if inverse else order:
            i, sh = rows[k]
            # t -= e_i a with e_i = 2 r_i - 1: complement the window around one add when r_i = 0
            op = src[max(0, -sh) :]
            cin = src[-sh - 1] if p.rnd and sh < 0 else None
            if not len(op) and cin is None:  # a trimmed register can leave nothing to add
                continue
            win = window[max(0, sh) : tops[k] if tops else len(window)]
            b.x(x[i])
            b.cx(x[i], win)
            ripple_add(b, op, win, subtract=not inverse, cin=cin)
            b.cx(x[i], win)
            b.x(x[i])
    else:
        plan = digit_plan(p, j)
        for dg in reversed(plan) if inverse else plan:
            _booth_digit(b, p, x, src, tgt, dg, inverse)
    if not inverse and len(tgt.hi):
        if len(tgt.hi) > len(tgt.ext):
            ripple_add(b, tgt.ext, tgt.hi)
        else:
            b.iadd(tgt.ext, target=tgt.hi)


def build_centered(
    p: Params,
    t: Tables,
    coarse: str = "barrel",
    max_qubits: int | None = None,
    fine: str = "barrel",
    spare_leading_one: bool = True,
    trim_windows: bool = True,
) -> km.Circuit:
    """Split-phase generator with the remainder centered on its segment (`Params(centered=True)`)."""
    assert p.centered and not p.ceil and coarse in ("barrel", "serial") and fine in ("barrel", "serial")
    b = km.CircuitBuilder()
    if max_qubits is not None:
        b.set_max_qubits(max_qubits)
    x = b.create_quantum_register(WIDTH, name="x")
    flags = b.alloc_qubits(Z_LEVELS)
    shift_flags = flags[1:]
    d, a = p.degree, p.a
    k0 = p.frac[0] - a
    empty = km.array([])
    addr = km.array(list(x[p.rwidth : WIDTH - 1]) + [flags[0]])
    cwords, mwords = centered_words(p, t)
    f_bits = p.wy + MAX_PAIRS
    top = x[p.rwidth - 1]  # holds the sign of the centered remainder: inverted while the Horner stage runs

    with b.mark("normalise"):  # before the table registers exist: the zero tests need their own ancillas
        normalise(b, x, flags)
    drop = unused_top_bits(p, t)
    tops = row_window_tops(p, t) if trim_windows else [[] for _ in range(d)]
    levels = [Level(b.alloc_qubits(k0), None, empty, empty)]
    keep = list(range(k0))  # bit positions of the table word that get a qubit
    off = k0
    # after normalising, x[21] is the leading one, so it is 1 for every input: flip it to |0> and lend it
    # to the first window as its upper extension qubit (one qubit less at every stage; it is given back
    # before un-normalising)
    spare = x[WIDTH - 1] if spare_leading_one else None
    if spare is not None:
        b.x(spare)
    n_ext = 1 if p.pm1 else 2  # window extension qubits above `lo`
    flat: list[km.q] = list(levels[0].lo)
    for j in range(1, d):
        kj = p.frac[j] - a
        if spare is not None and j == 1:
            ext = km.array([spare] if n_ext == 1 else [b.alloc_qubits(1)[0], spare])
        else:
            ext = b.alloc_qubits(n_ext)
        lv = Level(b.alloc_qubits(kj), None, b.alloc_qubits(a - drop[j]), ext)
        levels.append(lv)
        keep += list(range(off, off + kj + (1 if p.pm1 else 0) + a - drop[j]))
        off += kj + (1 if p.pm1 else 0) + a
        flat += list(lv.lo) + (list(ext) if p.pm1 else []) + list(lv.hi)
        if not p.pm1:
            b.x(ext[0])  # the window starts at lo + 2^K
    levels.append(Level(b.alloc_qubits(p.frac[d] - drop[d]), None, empty, empty))
    flat += list(levels[-1].lo)
    keep += list(range(off, off + p.frac[d] - drop[d]))
    mwords = compress_words(mwords, keep)
    cw = b.alloc_qubits(a + 2)
    main = km.array(flat)
    with b.mark("lookup"):
        with b.unary_iteration(addr, p.entries) as it:
            for v, match in it:
                bits = [cw[i] for i in range(len(cw)) if (cwords[v] >> i) & 1]
                bits += [main[i] for i in range(len(main)) if (mwords[v] >> i) & 1]
                if bits:
                    b.cx(match, km.array(bits))
    with b.mark("coarse"):
        base = k0 - 2 - p.guard
        if coarse == "barrel":
            head = b.alloc_qubits(MAX_PAIRS)
            low_one = all(w & 1 for w in cwords)
            barrel_phase(b, km.array(list(cw) + list(head)), shift_flags, len(cw), base, f_bits, 1, low_one)
            b.free(head)
        else:
            serial_phase(b, cw, shift_flags, base, f_bits, 1)
        b.del_lookup(table=cwords, address=addr, target=cw)
    b.free(cw)
    if not p.pm1:
        b.x(top)
    for j in range(d - 1, -1, -1):
        with b.mark(f"horner{j}"):
            centered_step(b, p, j, x, levels, inverse=False, tops=tops[j] or None)
    with b.mark("fine"):
        if fine == "serial":
            serial_phase(b, levels[0].lo[p.guard :], shift_flags, 0, f_bits, 1)
        else:
            head = b.alloc_qubits(MAX_PAIRS)
            word = km.array(list(levels[0].lo[p.guard :]) + list(head))
            barrel_phase(b, word, shift_flags, k0 - p.guard, 0, f_bits, 1)
            b.free(head)
    for j in range(d):
        with b.mark(f"unhorner{j}"):
            centered_step(b, p, j, x, levels, inverse=True, tops=tops[j] or None)
    if not p.pm1:
        b.x(top)
    with b.mark("unlookup"):
        b.del_lookup(table=mwords, address=addr, target=main)
    for lv in levels:
        ext = lv.ext if lv.ext is not None else empty
        if len(ext) and not p.pm1:
            b.x(ext[0])
        if spare is not None and len(ext) and ext[-1] == spare:
            ext = km.array(list(ext)[:-1])
        for q in (lv.lo, lv.hi, ext):
            b.free(q)
    if spare is not None:
        b.x(spare)
    with b.mark("unnormalise"):
        normalise(b, x, flags, inverse=True)
    b.free(flags)
    return b.finish_circuit()
