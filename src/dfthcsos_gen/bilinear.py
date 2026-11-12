"""Two-dimensional one-hot loader: one Toffoli per two ranks of a bit plane (stage 1, derived here).

Split the address ``a = h * L + l`` (``L = 2**lb`` low values). Compute the one-hot lines of ``h`` and of
``l`` once per circuit (about ``H + L`` Toffolis and ``H + L`` qubits). A bit plane of the table is then the
``H x L`` bit matrix ``P[h, l]``, and everything below is linear algebra over GF(2):

* ``F(h)`` and ``G(l)`` cost nothing: CNOT from the lines that are set into the target bit.
* A rank-one term ``alpha(h) beta(l)`` costs one Toffoli: CNOT the lines of ``alpha`` into one pivot line,
  the lines of ``beta`` into another, ``CCX`` into the target, undo the CNOTs.
* Two rank-one terms cost one Toffoli, because ``(alpha1(h) + beta2(l)) (alpha2(h) + beta1(l))`` expands to
  ``alpha1 beta1 + alpha2 beta2`` plus a pure-``h`` and a pure-``l`` part, which ``F`` and ``G`` absorb.

So a plane costs ``ceil(rank / 2)`` Toffolis, where ``rank`` is the GF(2) rank of ``P`` after removing
``F`` and ``G`` (the "centered" rank). A random table has centered rank ``min(H, L) - 1`` and the loader is
then no better than the unary iteration; a table fitted to a rank budget is cheap. This module builds the
loader for any table and counts it; fitting the table is separate (``scripts/dfthcsos_codesign.py``).

The one-hot lines come from a binary tree of ANDs (one Toffoli per node, measurement-based uncompute, the
right child is the parent XORed with the left child in place), so only the leaves occupy qubits.

kickmix is imported lazily.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .loader import clog2


def _km() -> Any:
    import kickmix  # type: ignore[import-not-found,unused-ignore]

    return kickmix


def geometry(num_addresses: int, lb: int) -> tuple[int, int]:
    """``(H, L)``: hi lines needed and lo lines (``2**lb``)."""
    return math.ceil(num_addresses / (1 << lb)), 1 << lb


def best_lb(num_addresses: int) -> int:
    """The split that minimises ``H + L`` (the qubits and Toffolis of the lines)."""
    return min(range(1, clog2(num_addresses)), key=lambda lb: sum(geometry(num_addresses, lb)))


# --- GF(2) linear algebra on small matrices (rows as python ints) -----------------------------------------


def _rows(mat: np.ndarray) -> list[int]:
    return [int("".join("1" if x else "0" for x in row[::-1]), 2) for row in np.asarray(mat, dtype=bool)]


def gf2_rank(mat: np.ndarray) -> int:
    basis: dict[int, int] = {}  # leading bit -> row
    rank = 0
    for r in _rows(mat):
        while r:
            top = r.bit_length() - 1
            if top in basis:
                r ^= basis[top]
            else:
                basis[top] = r
                rank += 1
                break
    return rank


def center(plane: np.ndarray) -> np.ndarray:
    """``P`` with ``F(h)`` and ``G(l)`` removed: zero in row 0 and column 0, same rank as the best choice."""
    p = np.asarray(plane, dtype=bool)
    return np.asarray(p ^ p[:, :1] ^ p[:1, :] ^ p[:1, :1])


def centered_rank(plane: np.ndarray) -> int:
    return gf2_rank(center(plane))


def plane_toffolis(plane: np.ndarray) -> int:
    return (centered_rank(plane) + 1) // 2


def rank_factors(mat: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    """``mat = XOR_u alpha_u beta_u^T`` with ``rank`` terms (row-space basis, then coefficients)."""
    m = np.asarray(mat, dtype=bool)
    basis: list[np.ndarray] = []
    pivots: list[int] = []
    for row in m:
        r = row.copy()
        for b, p in zip(basis, pivots, strict=True):
            if r[p]:
                r ^= b
        if r.any():
            p = int(np.flatnonzero(r)[0])
            for i, b in enumerate(basis):  # keep the basis reduced
                if b[p]:
                    basis[i] = b ^ r
            basis.append(r)
            pivots.append(p)
    out = []
    for b, p in zip(basis, pivots, strict=True):
        out.append((m[:, p].copy(), b))  # column p of every row is its coefficient on b
    return out


@dataclass
class PlanePlan:
    """How one bit plane is produced: fan-outs ``F`` (hi lines) and ``G`` (lo lines) and products."""

    f: np.ndarray
    g: np.ndarray
    products: list[tuple[frozenset[int], frozenset[int]]] = field(default_factory=list)


def plan_plane(plane: np.ndarray) -> PlanePlan:
    """Decompose a plane (``H x L`` bits) into fan-outs and Toffoli products over line indices.

    Line indices: ``0 .. H-1`` are the hi lines, ``H .. H+L-1`` the lo lines.
    """
    p = np.asarray(plane, dtype=bool)
    h, ll = p.shape
    terms = rank_factors(center(p))
    products: list[tuple[frozenset[int], frozenset[int]]] = []
    for i in range(0, len(terms), 2):
        a1, b1 = terms[i]
        if i + 1 < len(terms):
            a2, b2 = terms[i + 1]
            s1 = frozenset(np.flatnonzero(a1).tolist()) | frozenset((h + np.flatnonzero(b2)).tolist())
            s2 = frozenset(np.flatnonzero(a2).tolist()) | frozenset((h + np.flatnonzero(b1)).tolist())
        else:
            s1 = frozenset(np.flatnonzero(a1).tolist())
            s2 = frozenset((h + np.flatnonzero(b1)).tolist())
        products.append((s1, s2))
    realized = np.zeros((h, ll), dtype=bool)
    for s1, s2 in products:
        realized ^= _form_grid(s1, h, ll) & _form_grid(s2, h, ll)
    resid = p ^ realized
    f = resid[:, 0].copy()
    g = resid[0, :] ^ resid[0, 0]
    return PlanePlan(f=f, g=g, products=products)


def _form_grid(s: frozenset[int], h: int, ll: int) -> np.ndarray:
    """Value of the XOR of the lines in ``s`` on every ``(h, l)`` (exactly one hi and one lo line is set)."""
    hi = np.zeros(h, dtype=bool)
    lo = np.zeros(ll, dtype=bool)
    for q in s:
        if q < h:
            hi[q] = True
        else:
            lo[q - h] = True
    return hi[:, None] ^ lo[None, :]


def evaluate_plan(plan: PlanePlan, h: int, ll: int) -> np.ndarray:
    """Classical value of the planned plane on the full ``H x L`` grid."""
    out = plan.f[:, None] ^ plan.g[None, :]
    for s1, s2 in plan.products:
        out = out ^ (_form_grid(s1, h, ll) & _form_grid(s2, h, ll))
    return np.asarray(out)


def planes_of(delta: np.ndarray, brot: int, lb: int) -> np.ndarray:
    """``(J * brot, H, L)`` bit planes of an ``(A, J)`` table; addresses past ``A`` are 0 (don't care)."""
    a, j = delta.shape
    h, ll = geometry(a, lb)
    full = np.zeros((h * ll, j), dtype=np.int64)
    full[:a] = delta
    bits = (full[:, :, None] >> np.arange(brot)[None, None, :]) & 1  # (A', J, brot)
    return np.asarray(bits.reshape(h, ll, j * brot).transpose(2, 0, 1).astype(bool))


def line_toffolis(num_hi: int, hi_bits: int, num_lo: int, lo_bits: int) -> int:
    """Toffolis of the two one-hot trees (``num_*`` lines of ``*_bits`` address bits)."""

    def tree(count: int, bits: int) -> int:
        def rec(lo: int, size: int, top: bool) -> int:
            if lo >= count or size == 1:
                return 0
            half = size // 2
            if lo + half >= count:
                return rec(lo, half, top)
            return (0 if top else 1) + rec(lo, half, False) + rec(lo + half, half, False)

        return rec(0, 1 << bits, True)

    return tree(num_hi, hi_bits) + tree(num_lo, lo_bits)


def bilinear_toffolis(delta: np.ndarray, brot: int, lb: int) -> int:
    """Static Toffoli count of ``build_bilinear_loader(delta, brot, lb)``."""
    a = delta.shape[0]
    n = clog2(a)
    h, ll = geometry(a, lb)
    lines = line_toffolis(h, n - lb, ll, lb)
    planes = planes_of(np.asarray(delta, dtype=np.int64), brot, lb)
    return lines + sum(len(plan_plane(p).products) for p in planes)


def _emit_onehot(b: Any, bits_msb: list[Any], count: int) -> tuple[list[Any], Any]:
    """Qubits holding the one-hot of the address bits (MSB first) for values ``< count``, and its undo."""
    ops: list[tuple[Any, ...]] = []
    leaves: dict[int, Any] = {}

    def new_qubit() -> Any:
        return b.alloc_qubits(1)[0]

    def rec(c: Any, level: int, lo: int, size: int) -> None:
        if lo >= count:
            return
        if size == 1:
            if c is None:
                c = new_qubit()
                b.x(c)
                ops.append(("x", c))
            leaves[lo] = c
            return
        half = size // 2
        bit = bits_msb[level]
        if lo + half >= count:  # every valid address below has this bit clear: skip it
            rec(c, level + 1, lo, half)
            return
        left = new_qubit()
        if c is None:  # top of the tree: copies of the bit and its complement
            right = new_qubit()
            b.cx(bit, left)
            b.x(left)
            b.cx(bit, right)
            ops.append(("top", bit, left, right))
            c = right
        else:
            b.x(bit)
            b.init_and(c, bit, left)
            b.x(bit)
            b.cx(left, c)  # c becomes the right child: parent XOR left
            ops.append(("and", c, bit, left))
        rec(left, level + 1, lo, half)
        rec(c, level + 1, lo + half, half)

    rec(None, 0, 0, 1 << len(bits_msb))

    def undo() -> None:
        for op in reversed(ops):
            if op[0] == "x":
                b.x(op[1])
            elif op[0] == "top":
                _, bit, left, right = op
                b.cx(bit, right)
                b.x(left)
                b.cx(bit, left)
            else:
                _, c, bit, left = op
                b.cx(left, c)
                b.x(bit)
                b.del_and(c, bit, left)
                b.x(bit)

    return [leaves[i] for i in range(count)], undo


def _emit_product(b: Any, lines: list[Any], target: Any, s1: frozenset[int], s2: frozenset[int]) -> None:
    """``target ^= (XOR of lines in s1) AND (XOR of lines in s2)`` with one Toffoli (or none)."""
    only1, only2, both = s1 - s2, s2 - s1, s1 & s2
    if not only1 and not only2:  # same form: x AND x = x
        for q in sorted(s1):
            b.cx(lines[q], target)
        return
    if only1 and only2:
        a, c = sorted(s1), sorted(s2)  # L1 * L2 with distinct pivots outside the other form
        pa, pc = min(only1), min(only2)
    elif only2:  # s1 within s2: L1 * L2 = L1 + L1 * (L2 minus L1)
        for q in sorted(s1):
            b.cx(lines[q], target)
        a, c = sorted(s1), sorted(only2)
        pa, pc = min(s1), min(only2)
    else:  # s2 within s1
        for q in sorted(s2):
            b.cx(lines[q], target)
        a, c = sorted(only1), sorted(s2)
        pa, pc = min(only1), min(s2)
    del both
    for q in a:
        if q != pa:
            b.cx(lines[q], lines[pa])
    for q in c:
        if q != pc:
            b.cx(lines[q], lines[pc])
    b.ccx(lines[pa], lines[pc], target)
    for q in reversed(c):
        if q != pc:
            b.cx(lines[q], lines[pc])
    for q in reversed(a):
        if q != pa:
            b.cx(lines[q], lines[pa])


def build_bilinear_loader(delta: np.ndarray, brot: int, lb: int | None = None) -> Any:
    """One ``ANGLE_k`` circuit for an ``(A, J)`` XOR table of ``brot``-bit words."""
    km = _km()
    delta = np.asarray(delta, dtype=np.int64)
    a, j = delta.shape
    if a < 4:
        raise ValueError("need at least four addresses")
    if delta.min() < 0 or delta.max() >= 1 << brot:
        raise ValueError(f"words must lie in [0, 2**{brot})")
    n = clog2(a)
    lb = best_lb(a) if lb is None else lb
    h, ll = geometry(a, lb)
    planes = planes_of(delta, brot, lb)
    b = km.CircuitBuilder()
    sel = b.create_quantum_register(n, "selection")
    words = [b.create_quantum_register(brot, f"word_{w}") for w in range(j)]
    msb_first = [sel[i] for i in reversed(range(n))]
    hi_lines, undo_hi = _emit_onehot(b, msb_first[: n - lb], h)
    lo_lines, undo_lo = _emit_onehot(b, msb_first[n - lb :], ll)
    lines = hi_lines + lo_lines
    for idx, plane in enumerate(planes):
        target = words[idx // brot][idx % brot]
        plan = plan_plane(plane)
        for q in np.flatnonzero(plan.f):
            b.cx(lines[q], target)
        for q in np.flatnonzero(plan.g):
            b.cx(lines[h + q], target)
        for s1, s2 in plan.products:
            _emit_product(b, lines, target, s1, s2)
    undo_lo()
    undo_hi()
    return b.finish_circuit()


def build_bilinear_family(words: np.ndarray, brot: int, J: int, lb: int | None = None) -> tuple[Any, ...]:
    from .loader import angle_deltas

    return tuple(build_bilinear_loader(d, brot, lb) for d in angle_deltas(np.asarray(words), J))
