"""Shared-product loader: output bits that share their rank-one products (QCC-16, stage 2).

Structure learned by simulating a public angle loader (docs/experiments/dfthcsos-stage2.md, logged in
docs/PROVENANCE.md); the construction below is written fresh from that description.

Split the address ``a = h * L + l``. A table of ``nout`` output bits is

    T[o, h, l] = F[o, h] + G[o, l] + sum_t v[t, o] * alpha[t, h] * beta[t, l]       (over GF(2))

``F`` and ``G`` cost only CNOTs from the one-hot lines of ``h`` and ``l``. A term ``t`` costs ONE Toffoli
however many output bits it feeds: its two pivot lines (CNOT-combinations of the lines of ``alpha_t`` and
``beta_t``) are ANDed into one output bit ``p``, and the other output bits ``o`` in ``v_t`` get the product by
a CNOT ``p -> o`` before and after the Toffoli (``o ^= p_old ^ (p_old ^ prod) = prod``). So the Toffoli count
of a circuit is ``lines + number of terms``, set by the tensor rank of the table, not by its planes singly
(``bilinear.py``). The loader is correct for every table of this form; choosing ``alpha, beta, v`` for a given
table, or rounding a fit into the form, is a separate problem.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .bilinear import _emit_onehot, _km, geometry
from .loader import clog2


@dataclass
class SharedPlan:
    f: np.ndarray  # (nout, H) 0/1
    g: np.ndarray  # (nout, L) 0/1
    alpha: np.ndarray  # (T, H) 0/1
    beta: np.ndarray  # (T, L) 0/1
    v: np.ndarray  # (T, nout) 0/1

    @property
    def terms(self) -> int:
        return int(
            sum(
                1
                for t in range(len(self.alpha))
                if self.alpha[t].any() and self.beta[t].any() and self.v[t].any()
            )
        )


def table_of(plan: SharedPlan) -> np.ndarray:
    """``(nout, H, L)`` bits of the table the plan loads."""
    f, g = plan.f.astype(np.int64), plan.g.astype(np.int64)
    t = f[:, :, None] + g[:, None, :]
    t = t + np.einsum(
        "to,th,tl->ohl", plan.v.astype(np.int64), plan.alpha.astype(np.int64), plan.beta.astype(np.int64)
    )
    return np.asarray(t & 1, dtype=np.uint8)


def random_plan(nout: int, h: int, ll: int, terms: int, rng: np.random.Generator) -> SharedPlan:
    def bits(*shape: int) -> np.ndarray:
        return rng.integers(0, 2, size=shape).astype(np.uint8)

    return SharedPlan(bits(nout, h), bits(nout, ll), bits(terms, h), bits(terms, ll), bits(terms, nout))


def shared_toffolis(plan: SharedPlan, num_addresses: int, lb: int) -> int:
    """Static Toffoli count of ``build_shared_loader``."""
    from .bilinear import line_toffolis

    n = clog2(num_addresses)
    h, ll = geometry(num_addresses, lb)
    return line_toffolis(h, n - lb, ll, lb) + plan.terms


def build_shared_loader(plan: SharedPlan, num_addresses: int, brot: int, lb: int) -> Any:
    """One ``ANGLE_k`` circuit: selection of ``clog2(A)`` qubits and ``nout / brot`` word registers."""
    km = _km()
    nout = plan.f.shape[0]
    if nout % brot:
        raise ValueError("nout must be a multiple of brot")
    n = clog2(num_addresses)
    h, ll = geometry(num_addresses, lb)
    b = km.CircuitBuilder()
    sel = b.create_quantum_register(n, "selection")
    words = [b.create_quantum_register(brot, f"word_{w}") for w in range(nout // brot)]
    out = [words[o // brot][o % brot] for o in range(nout)]
    msb_first = [sel[i] for i in reversed(range(n))]
    hi, undo_hi = _emit_onehot(b, msb_first[: n - lb], h)
    lo, undo_lo = _emit_onehot(b, msb_first[n - lb :], ll)
    for o in range(nout):
        for q in np.flatnonzero(plan.f[o]):
            b.cx(hi[q], out[o])
        for q in np.flatnonzero(plan.g[o]):
            b.cx(lo[q], out[o])
    for t in range(len(plan.alpha)):
        sa, sb, so = (np.flatnonzero(x) for x in (plan.alpha[t], plan.beta[t], plan.v[t]))
        if not (len(sa) and len(sb) and len(so)):
            continue
        pa, pb, p = sa[0], sb[0], so[0]
        for q in sa[1:]:
            b.cx(hi[q], hi[pa])
        for q in sb[1:]:
            b.cx(lo[q], lo[pb])
        for o in so[1:]:
            b.cx(out[p], out[o])
        b.ccx(hi[pa], lo[pb], out[p])
        for o in so[1:]:
            b.cx(out[p], out[o])
        for q in reversed(sb[1:]):
            b.cx(lo[q], lo[pb])
        for q in reversed(sa[1:]):
            b.cx(hi[q], hi[pa])
    undo_lo()
    undo_hi()
    return b.finish_circuit()
