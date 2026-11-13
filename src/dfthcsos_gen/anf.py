"""Qubit-lean two-dimensional loader: the lines are monomials of the selection bits (QCC-16, stage 2).

``bilinear.py`` keeps the one-hot lines of ``h`` and ``l`` (``H + L`` qubits), which leaves almost
no room for word registers. Here the lines are the algebraic-normal-form monomials ``m_S(h) =
prod_{i in S} h_i``, for ``S < H`` (as bit masks) on the high address bits and ``T < L`` on the low
ones:

* any function ``alpha(h)`` on ``h < H`` is a GF(2) combination of ``m_S``, ``S < H``: the matrix
  ``[S subset of h]`` is triangular, and the coefficients are the Moebius transform ``c_S = XOR_{h
  subset of S} alpha(h)``;
* ``m_0`` is the constant 1 (one qubit set to 1, so a constant in a form is an ordinary CNOT), the
  degree-one monomials are the selection qubits themselves, and only the ``S`` with two or more bits
  take a work qubit and one Toffoli (``m_S = m_{S without its top bit} AND x_top``), uncomputed by
  measurement. For 1,220 addresses at ``lb = 4`` that is 69 + 11 work qubits against 93 for one-hot
  lines.

The per-plane plan (``plan_plane``: fan-outs and ``ceil(rank / 2)`` Toffoli products of two linear
forms) is unchanged; its forms over one-hot lines are converted to monomial sets by the Moebius
transform. Written from the description in docs/experiments/dfthcsos-stage2.md (idea logged in
docs/PROVENANCE.md).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .bilinear import PlanePlan, _emit_product, _km, geometry, plan_plane, planes_of
from .loader import angle_deltas, clog2

QUBIT_CAP = 128


def mobius(vec: np.ndarray) -> np.ndarray:
    """ANF coefficients ``c_S = XOR_{h subset of S} vec[h]`` for a vector over ``0 .. n-1``."""
    c = np.asarray(vec, dtype=np.uint8).copy()
    n = len(c)
    bit = 1
    while bit < n:
        for s in range(n):
            if s & bit:
                c[s] ^= c[s ^ bit]
        bit <<= 1
    return c


def monomial_ands(count: int) -> int:
    """Toffolis (= work qubits) of the monomials ``S < count``: those with at least two bits."""
    return sum(1 for s in range(count) if s.bit_count() >= 2)


def work_qubits(num_addresses: int, lb: int) -> int:
    h, ll = geometry(num_addresses, lb)
    return 1 + monomial_ands(h) + monomial_ands(ll)  # + the constant line


def max_words(num_addresses: int, brot: int, lb: int, cap: int = QUBIT_CAP) -> int:
    return (cap - clog2(num_addresses) - work_qubits(num_addresses, lb)) // brot


def _line_index(h: int, ll: int) -> tuple[Any, Any]:
    """Index of monomial ``S`` of the hi side and ``T`` of the lo side in one list (index 0 = constant)."""

    def hi(s: int) -> int:
        return s

    def lo(t: int) -> int:
        return h - 1 + t

    return hi, lo


def convert_set(s: frozenset[int], h: int, ll: int) -> frozenset[int]:
    """A one-hot line set (hi ``0..h-1``, lo ``h..h+ll-1``) as a monomial line set."""
    hi_v = np.zeros(h, dtype=np.uint8)
    lo_v = np.zeros(ll, dtype=np.uint8)
    for q in s:
        if q < h:
            hi_v[q] ^= 1
        else:
            lo_v[q - h] ^= 1
    hi_i, lo_i = _line_index(h, ll)
    ch, cl = mobius(hi_v), mobius(lo_v)
    out: set[int] = set()
    if ch[0] ^ cl[0]:
        out.add(0)
    out |= {hi_i(int(q)) for q in np.flatnonzero(ch) if q}
    out |= {lo_i(int(q)) for q in np.flatnonzero(cl) if q}
    return frozenset(out)


def _fan_set(vec: np.ndarray, side: str, h: int, ll: int) -> frozenset[int]:
    n = h if side == "hi" else ll
    c = mobius(np.asarray(vec, dtype=np.uint8)[:n])
    hi_i, lo_i = _line_index(h, ll)
    idx = hi_i if side == "hi" else lo_i
    return frozenset({0 if q == 0 else idx(int(q)) for q in np.flatnonzero(c)})


def plane_toffolis(plan: PlanePlan) -> int:
    return len(plan.products)


def anf_toffolis(delta: np.ndarray, brot: int, lb: int) -> int:
    """Static Toffoli count of ``build_anf_loader(delta, brot, lb)``."""
    a = delta.shape[0]
    h, ll = geometry(a, lb)
    planes = planes_of(np.asarray(delta, dtype=np.int64), brot, lb)
    return monomial_ands(h) + monomial_ands(ll) + sum(len(plan_plane(p).products) for p in planes)


def build_anf_loader(delta: np.ndarray, brot: int, lb: int) -> Any:
    """One ``ANGLE_k`` circuit for an ``(A, J)`` XOR table of ``brot``-bit words, on monomial lines."""
    km = _km()
    delta = np.asarray(delta, dtype=np.int64)
    a, j = delta.shape
    if delta.min() < 0 or delta.max() >= 1 << brot:
        raise ValueError(f"words must lie in [0, 2**{brot})")
    n = clog2(a)
    h, ll = geometry(a, lb)
    if n + j * brot + work_qubits(a, lb) > QUBIT_CAP:
        raise ValueError("does not fit in the qubit cap; use fewer words per circuit")
    planes = planes_of(delta, brot, lb)
    b = km.CircuitBuilder()
    sel = b.create_quantum_register(n, "selection")
    words = [b.create_quantum_register(brot, f"word_{w}") for w in range(j)]
    # line list: index 0 constant, 1..h-1 hi monomials, h..h+ll-2 lo monomials
    lines: list[Any] = [None] * (h + ll - 1)
    const = b.alloc_qubits(1)[0]
    b.x(const)
    lines[0] = const
    hi_i, lo_i = _line_index(h, ll)
    ands: list[tuple[Any, Any, Any]] = []
    for count, idx, sel_off in ((h, hi_i, lb), (ll, lo_i, 0)):
        for s in range(1, count):
            if s.bit_count() == 1:
                lines[idx(s)] = sel[sel_off + s.bit_length() - 1]
                continue
            top = s.bit_length() - 1
            rest = s ^ (1 << top)
            ctrl = lines[idx(rest)]
            out = b.alloc_qubits(1)[0]
            b.init_and(ctrl, sel[sel_off + top], out)
            ands.append((ctrl, sel[sel_off + top], out))
            lines[idx(s)] = out
    for idx_w, plane in enumerate(planes):
        target = words[idx_w // brot][idx_w % brot]
        plan = plan_plane(plane)
        for q in sorted(_fan_set(plan.f, "hi", h, ll)):
            b.cx(lines[q], target)
        for q in sorted(_fan_set(plan.g, "lo", h, ll)):
            b.cx(lines[q], target)
        for s1, s2 in plan.products:
            _emit_product(b, lines, target, convert_set(s1, h, ll), convert_set(s2, h, ll))
    for ctrl, x, out in reversed(ands):
        b.del_and(ctrl, x, out)
    b.x(const)
    return b.finish_circuit()


def build_anf_family(words: np.ndarray, brot: int, J: int, lb: int) -> tuple[Any, ...]:
    return tuple(build_anf_loader(d, brot, lb) for d in angle_deltas(np.asarray(words), J))
