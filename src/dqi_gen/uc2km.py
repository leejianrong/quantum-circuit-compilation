"""Convert an `uncompute` circuit (Gu, Kemeny, Yelin, Lukin; Apache-2.0) into a kickmix circuit.

The op model of that repository follows the kickmix model, so each op maps to one kickmix instruction:
X, Z, NEG, CX, CZ, SWAP, CCX, CCZ, R, HMR, outcome accumulation (OXOR) and the bit-only ops. A condition on
an op (an outcome on a sign gate, or a bit on X, Z, NEG, CX, CZ) becomes a `push_condition` / `pop_condition`
pair around it.

This file is original to this repository (written for the port recorded in `THIRD_PARTY_NOTICES.md`); it
reads the in-memory op tuples of the vendored `uncompute.Builder` and copies none of its code.

Id spaces: qubit ids map one to one and the first `n_syn * deg` qubits form the registers `S0 ...`. Stream
bit id `i` is kickmix bit `i`, so the first `n_err * deg` stream bits are the input registers `E0 ...`;
outcome ids follow all stream bits.
"""

from __future__ import annotations

from typing import Any

import kickmix as km  # type: ignore[import-not-found,unused-ignore]

NO = (1 << 64) - 1
X, Z, NEG, CX, CZ, SWAP, CCX, CCZ, R, HMR, OXOR, BIT_INVERT, BIT_STORE0, BIT_STORE1 = range(14)


def convert(ub: Any, *, n_syn: int, deg: int, n_err: int = 0) -> Any:
    """Build the kickmix circuit for the finished `uncompute.Builder` `ub`."""
    b = km.CircuitBuilder()
    for i in range(n_syn):
        b.create_quantum_register(deg, name=f"S{i}")
    for j in range(n_err):
        b.create_classical_register(deg, name=f"E{j}")
    rest = int(ub.peak_qubits) - n_syn * deg
    if rest > 0:
        b.alloc_qubits(rest)
    n_bits, n_out = int(ub.next_bit), int(ub.next_out)
    assert n_bits >= n_err * deg, "the first stream bit ids must be the input mask bits"
    b.alloc_bits(n_bits + n_out - n_err * deg)
    q = [km.q(i) for i in range(int(ub.peak_qubits))]
    bits = [km.b(i) for i in range(n_bits)]
    outs = [km.b(n_bits + i) for i in range(n_out)]
    push, pop = b.push_condition, b.pop_condition

    def cond_of(oc: int, cc: int) -> list[Any]:
        c = []
        if oc != NO:
            c.append(outs[oc])
        if cc != NO:
            c.append(bits[cc])
        return c

    for kind, qa, qb, qt, ot, oc, _rt, ct, cc in ub.iter_expanded():
        conds = cond_of(oc, cc) if (oc != NO or cc != NO) else None
        if kind == HMR:
            b.hmr(q[qt], outs[ot])
            continue
        if kind == OXOR:
            b.cx(outs[oc], outs[ot])
            continue
        if kind == BIT_INVERT:
            if conds:
                for c in conds:
                    push(c)
                b.x(bits[ct])
                for _ in conds:
                    pop()
            else:
                b.x(bits[ct])
            continue
        if kind == BIT_STORE0 or kind == BIT_STORE1:
            if conds:
                for c in conds:
                    push(c)
            b.bit_store(bits[ct], 1 if kind == BIT_STORE1 else 0)
            if conds:
                for _ in conds:
                    pop()
            continue
        if conds:
            for c in conds:
                push(c)
        if kind == X:
            b.x(q[qt])
        elif kind == Z:
            b.z(q[qt])
        elif kind == NEG:
            b.neg()
        elif kind == CX:
            b.cx(q[qb], q[qt])
        elif kind == CZ:
            b.cz(q[qb], q[qt])
        elif kind == SWAP:
            b.swap(q[qb], q[qt])
        elif kind == CCX:
            b.ccx(q[qa], q[qb], q[qt])
        elif kind == CCZ:
            b.ccz(q[qa], q[qb], q[qt])
        elif kind == R:
            b.reset(q[qt])
        else:  # pragma: no cover
            raise ValueError(f"unknown op kind {kind}")
        if conds:
            for _ in conds:
                pop()
    return b.finish_circuit()
