"""Paired shared-product loader planned by matroid parity (QCC-16, stage 2).

Setting (ANF lines, ``anf.py``): after the Moebius transform a table is ``T[o, h, l] = F[o, h] + G[o, l]
+ sum_{S >= 1, m >= 1} c[o, S, m] x^S(h) y^m(l)`` with ``x^S`` the hi monomials and ``y^m`` the low
monomials. One Toffoli computes ``(l1 + h1)(l2 + h2)`` of two forms over the lines and fans it out to a
set ``out`` of output planes; its cross part is ``out (x) (l1 (x) h2 + l2 (x) h1)``. Write ``M_S`` for
the ``(m, o)`` matrix of hi monomial ``S``. Choose pairs ``(l1, l2, out)`` whose rank-one matrices ``D1 =
l1 (x) out`` and ``D2 = l2 (x) out`` are linearly independent and span a space ``W`` containing every
``M_S``: then ``h2[S], h1[S]`` are the coordinates of ``M_S`` on ``D1, D2``, and the pure-``h`` and
pure-``l`` leftovers go to the CNOT-only ``F, G``. The count of Toffolis is ``dim W / 2``. ``W`` is the
kernel of "cuts" (functionals vanishing on every ``M_S``) that are local to a block of three low
monomials; the more cuts that keep a perfect pairing possible, the fewer products (``parity.py`` decides
that). Our own derivation of the setting; the idea (cuts plus parity matching) is described in
docs/experiments/dfthcsos-stage2.md and logged in docs/PROVENANCE.md.
"""

from __future__ import annotations

import random
from typing import Any

import numpy as np

from .anf import mobius
from .bilinear import _emit_product, _km, geometry, planes_of
from .loader import clog2
from .parity import bits, gf2_basis, gf2_nullspace, parity_rank, perfect_matching

LO = 15  # low monomials y^1 .. y^15 (four low address bits)


def outer(lmask: int, out: int, no: int) -> int:
    x = 0
    for m in bits(lmask):
        x ^= out << (no * m)
    return x


def cross_tensor(planes: np.ndarray, h: int) -> tuple[list[int], np.ndarray]:
    """``(M_S for S = 1..h-1 as bit masks over (m-1) * NO + o, residual-free ANF array c[o, S, m])``."""
    no = planes.shape[0]
    anf = np.zeros((no, h, 16), dtype=np.uint8)
    for o in range(no):
        g = planes[o].astype(np.uint8)  # (h, 16) as a function on the grid
        c = np.stack([mobius(g[:, lq]) for lq in range(16)], axis=1)  # over hi: (h, 16)
        c = np.stack([mobius(c[s, :]) for s in range(h)], axis=0)  # over lo
        anf[o] = c
    mats = []
    for s in range(1, h):
        x = 0
        for m in range(1, 16):
            for o in range(no):
                if anf[o, s, m]:
                    x |= 1 << ((m - 1) * no + o)
        mats.append(x)
    return mats, anf


def make_parts(seed: int) -> list[list[int]]:
    ms = list(range(15))
    random.Random(seed).shuffle(ms)
    return [sorted(ms[3 * i : 3 * i + 3]) for i in range(5)]


def _local(x: int, part: list[int], no: int) -> int:
    mask = (1 << no) - 1
    return sum(((x >> (no * m)) & mask) << (no * j) for j, m in enumerate(part))


def _dirs(parts: list[list[int]]) -> list[tuple[int, int, int]]:
    """``(part index, low-monomial mask over 0..14, local form 1..7)``."""
    out = []
    for pi, part in enumerate(parts):
        for form in range(1, 8):
            out.append((pi, sum(1 << part[j] for j in range(3) if (form >> j) & 1), form))
    return out


def _form_constraints(cuts: list[int], form: int, no: int) -> list[int]:
    mask = (1 << no) - 1
    res = []
    for phi in cuts:
        v = 0
        for j in range(3):
            if (form >> j) & 1:
                v ^= (phi >> (no * j)) & mask
        if v:
            res.append(v)
    return list(gf2_basis(res).values())


def candidates(
    parts: list[list[int]], cuts: list[list[int]], no: int, sums: int = 24
) -> list[tuple[int, int, int, int, int]]:
    """``(D1, D2, l1, l2, out)`` for every pair of directions and allowed ``out``: a basis of them plus
    ``sums`` pairwise sums (a plane has 15 monomials, so some pairs must carry a sum of two planes)."""
    dirs = _dirs(parts)
    rng = random.Random(len(parts) * 7919 + no)
    cons = {(pi, f): _form_constraints(cuts[pi], f, no) for pi in range(len(parts)) for f in range(1, 8)}
    pairs = []
    for i in range(len(dirs)):
        for j in range(i + 1, len(dirs)):
            p1, l1, f1 = dirs[i]
            p2, l2, f2 = dirs[j]
            vs = gf2_nullspace(cons[(p1, f1)] + cons[(p2, f2)], no)
            vv = list(vs)
            allsums = [(x, y) for ix, x in enumerate(vs) for y in vs[ix + 1 :]]
            for x, y in rng.sample(allsums, min(sums, len(allsums))):
                vv.append(x ^ y)
            for v in vv:
                pairs.append((outer(l1, v, no), outer(l2, v, no), l1, l2, v))
    return pairs


def search_cuts(
    mats: list[int], no: int, parts: list[list[int]], tries: int, seed: int, verbose: bool = False
) -> list[list[int]]:
    """Greedy: add random annihilating local cuts while a perfect pairing still spans the cut kernel."""
    rng = random.Random(seed)
    ann = [gf2_nullspace([_local(x, part, no) for x in mats], 3 * no) for part in parts]
    cuts: list[list[int]] = [[] for _ in parts]
    total = 0
    for t in range(tries):
        trial = [list(c) for c in cuts]
        added = 0
        for _ in range(2):  # the kernel dimension must stay even for a perfect pairing
            pi = rng.randrange(len(parts))
            if not ann[pi]:
                continue
            phi = 0
            for a in ann[pi]:
                if rng.getrandbits(1):
                    phi ^= a
            if not phi:
                continue
            trial[pi].append(phi)
            added += 1
        if added != 2 or any(len(gf2_basis(c)) != len(c) for c in trial):
            continue
        pairs = [(a, b) for a, b, *_ in candidates(parts, trial, no)]
        rank, span = parity_rank(pairs, seed=1)
        if rank == span and span == LO * no - (total + 2):
            cuts = trial
            total += 2
            if verbose:
                print(f"try {t}: cuts {total}, products {span // 2}", flush=True)
    return cuts


def coords(basis_vecs: list[int], target: int) -> int | None:
    """GF(2) combination mask of ``basis_vecs`` equal to ``target`` (``None`` when outside the span)."""
    piv: dict[int, tuple[int, int]] = {}
    for i, v in enumerate(basis_vecs):
        comb = 1 << i
        while v:
            j = v.bit_length() - 1
            if j in piv:
                v ^= piv[j][0]
                comb ^= piv[j][1]
            else:
                piv[j] = (v, comb)
                break
    out = 0
    while target:
        j = target.bit_length() - 1
        if j not in piv:
            return None
        target ^= piv[j][0]
        out ^= piv[j][1]
    return out


def plan_products(
    planes: np.ndarray, h: int, parts: list[list[int]], cuts: list[list[int]]
) -> list[dict[str, int]] | None:
    """Products ``{l1, l2, out, h1, h2}`` realising the cross tensor, or ``None`` if no perfect pairing."""
    no = planes.shape[0]
    mats, _ = cross_tensor(planes, h)
    cands = candidates(parts, cuts, no)
    chosen = perfect_matching([(a, b) for a, b, *_ in cands], seed=1)
    if chosen is None:
        return None
    sel = [cands[i] for i in chosen]
    basis_vecs = [x for s in sel for x in s[:2]]
    prods = [{"l1": s[2], "l2": s[3], "out": s[4], "h1": 0, "h2": 0} for s in sel]
    for si, mat in enumerate(mats):
        c = coords(basis_vecs, mat)
        if c is None:
            return None
        for t in range(len(prods)):
            if (c >> (2 * t)) & 1:  # coefficient on D1 = l1 (x) out is h2[S]
                prods[t]["h2"] |= 1 << (si + 1)
            if (c >> (2 * t + 1)) & 1:  # coefficient on D2 = l2 (x) out is h1[S]
                prods[t]["h1"] |= 1 << (si + 1)
    return [p for p in prods if p["h1"] or p["h2"]]


def build_pair_loader(
    delta: np.ndarray, brot: int, lb: int, products: list[dict[str, int]], sign_ext: bool = True
) -> Any:
    """``ANGLE_k`` circuit: ANF lines, the given paired products, CNOT-only ``F, G`` for the leftover."""
    from .anf import QUBIT_CAP, _fan_set, _line_index, _live_planes, work_qubits

    km = _km()
    delta = np.asarray(delta, dtype=np.int64)
    a, j = delta.shape
    n = clog2(a)
    h, ll = geometry(a, lb)
    if lb != 4:
        raise ValueError("the pair planner is written for four low bits")
    if n + j * brot + work_qubits(a, lb) - 1 > QUBIT_CAP:
        raise ValueError("does not fit in the qubit cap")
    live = _live_planes(delta, brot, lb, sign_ext)
    no = len(live)
    builder = km.CircuitBuilder()
    sel = builder.create_quantum_register(n, "selection")
    words = [builder.create_quantum_register(brot, f"word_{w}") for w in range(j)]
    out_q = [words[idx // brot][idx % brot] for idx, _ in live]
    # lines: index S-1 for hi monomial S (1..h-1), (h-1) + (m-1) for low monomial m (1..15)
    lines: list[Any] = [None] * (h - 1 + 15)
    hi_i, lo_i = _line_index(h, ll)
    ands: list[tuple[Any, Any, Any]] = []
    for count, idx, off in ((h, hi_i, lb), (ll, lo_i, 0)):
        for s in range(1, count):
            li = idx(s) - 1
            if s.bit_count() == 1:
                lines[li] = sel[off + s.bit_length() - 1]
                continue
            top = s.bit_length() - 1
            ctrl = lines[idx(s ^ (1 << top)) - 1]
            q = builder.alloc_qubits(1)[0]
            builder.init_and(ctrl, sel[off + top], q)
            ands.append((ctrl, sel[off + top], q))
            lines[li] = q
    if sign_ext:
        for w in words:
            builder.cx(w[brot - 2], w[brot - 1])
    # products
    value = np.zeros((no, h, 16), dtype=np.uint8)
    hh, ls = np.meshgrid(np.arange(h), np.arange(16), indexing="ij")

    def form_grid(hmask: int, lmask: int) -> np.ndarray:
        g = np.zeros((h, 16), dtype=np.uint8)
        for s in bits(hmask):
            g ^= ((hh & s) == s).astype(np.uint8)
        for m in bits(lmask):
            g ^= ((ls & (m + 1)) == m + 1).astype(np.uint8)
        return g

    for p in products:
        s1 = frozenset([(S - 1) for S in bits(p["h1"])] + [h - 1 + m for m in bits(p["l1"])])
        s2 = frozenset([(S - 1) for S in bits(p["h2"])] + [h - 1 + m for m in bits(p["l2"])])
        outs = [out_q[k] for k in bits(p["out"])]
        fan = [(outs[0], q) for q in outs[1:]]
        for src, dst in fan:
            builder.cx(src, dst)
        _emit_product(builder, lines, outs[0], s1, s2)
        for src, dst in fan:
            builder.cx(src, dst)
        prod = form_grid(p["h1"], p["l1"]) & form_grid(p["h2"], p["l2"])
        for k in bits(p["out"]):
            value[k] ^= prod
    # leftover must be F(h) + G(l)
    planes = np.stack([pl for _, pl in live]).astype(np.uint8)
    resid = planes ^ value
    for o in range(no):
        f = resid[o][:, 0]
        g = resid[o][0, :] ^ resid[o][0, 0]
        if not (resid[o] == (f[:, None] ^ g[None, :])).all():
            raise ValueError("products do not realise the cross part of the table")
        for q in sorted(_fan_set(f, "hi", h, ll)):
            if q == 0:
                builder.x(out_q[o])
            else:
                builder.cx(lines[q - 1], out_q[o])
        for q in sorted(_fan_set(g, "lo", h, ll)):
            if q == 0:
                builder.x(out_q[o])
            else:
                builder.cx(lines[q - 1], out_q[o])
    if sign_ext:
        for w in words:
            builder.cx(w[brot - 2], w[brot - 1])
    for ctrl, x, q in reversed(ands):
        builder.del_and(ctrl, x, q)
    return builder.finish_circuit()


def planes_for(delta: np.ndarray, brot: int, lb: int, sign_ext: bool) -> tuple[np.ndarray, int]:
    from .anf import _live_planes

    live = _live_planes(delta, brot, lb, sign_ext)
    h, _ = geometry(delta.shape[0], lb)
    return np.stack([p for _, p in live]).astype(bool), h


__all__ = ["build_pair_loader", "plan_products", "search_cuts", "make_parts", "planes_for", "planes_of"]
