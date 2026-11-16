# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Retimed transpose returning its final restored third-source predicate.

The arithmetic and twelve-query tensor body are unchanged from the separate
retimed provider. At the final head restoration, the third bit remains live
through the last shared source form and public inverse views. Ownership is
returned explicitly to the caller, which avoids its next identical query.

The returned bit equals zero of the supplied G's last field. Only that final
slot-two HMR mask disappears; all earlier masks retain their exact witnesses.
Core cost168*m+876 T,25 helpers, plus one owned output bit at the boundary.
The actual two-call preimage saves22 fixed T through the caller handoffs.
"""
import kickmix as km
from raw_window_tensor import evaluate
from monic_forney import add_scaled
from coherent_border import toggle_zero
from tower_inverse import xor_product, phase_product, kernel

FIELD = km.GF2Field(12)


class ThirdFlagHandoff:
    """One-use ownership of an actual queried flag on an unchanged witness."""
    def __init__(self, builder, flag, witness):
        assert len(flag) == 1 and isinstance(flag[0], km.q)
        assert len(witness) == 12 and all(isinstance(q, km.q) for q in witness)
        assert flag[0] not in set(witness)
        self.builder_id = id(builder)
        self.flag = flag
        self.witness = tuple(witness)
        self.claimed = False

    def claim(self, builder, witness):
        assert not self.claimed, 'flag ownership already transferred'
        assert id(builder) == self.builder_id, 'different builder'
        assert tuple(witness) == self.witness, 'different source witness'
        self.claimed = True
        return self.flag


def emit(builder, F, G, q0, q1, rhss, record_flag):
    m = len(G)-1
    assert m >= 1 and len(F) == m+2 and len(rhss) == 2 and all(len(r) == m+3 for r in rhss)
    words = [*F, *G, q0, q1, *rhss[0], *rhss[1]]
    assert all(len(word) == 12 for word in words)
    wires = [wire for word in words for wire in word]
    assert all(isinstance(wire, km.q) for wire in wires)
    assert len(set(wires)) == len(wires), 'source, head, or target views overlap'
    assert callable(record_flag)
    witnesses = (q1, F[-1], G[-1])

    def query(slot):
        flag = builder.alloc_qubits(1)
        toggle_zero(builder, witnesses[slot], flag[0])
        return flag

    def release(slot, flag):
        mask = builder.alloc_bits(1)
        builder.hmr(flag, mask)
        builder.free(flag)
        record_flag(slot, mask)

    def phase_moment(moment, coefficients, low, power):
        mask = builder.alloc_bits(12)
        builder.hmr(moment, mask)
        builder.free(moment)
        for point, (c, y) in enumerate(zip(coefficients, low)):
            factor = FIELD.pow(point, power)
            if factor:
                phase_product(builder, c, y, mask,
                              tuple((a, b, FIELD.mul(out, factor)) for a, b, out in kernel(12)))
        builder.free(mask)

    def shared_source_form(f=None):
        if f is None:
            f = query(0)
        masked = builder.alloc_qubits(12)
        builder.init_and(f[0], q0, masked)
        builder.cx(masked, q0)
        for rhs in rhss:
            xor_product(builder, q0, rhs[-2], rhs[-1])
        builder.cx(masked, q0)
        builder.del_and(f[0], q0, masked)
        builder.free(masked)
        release(0, f)

    evaluate(builder, F, m)
    evaluate(builder, G, m)
    shared_source_form()
    for rhs_index, rhs in enumerate(rhss):
        low = rhs[:m]
        h3, h2, h1 = rhs[m:]
        if rhs_index == 0:
            middle = query(1)
        x0, x1 = builder.alloc_qubits(12), builder.alloc_qubits(12)
        for point, (c, y) in enumerate(zip(F[:m], low)):
            add_scaled(builder, x0, x1, point)
            xor_product(builder, c, y, x0)
            add_scaled(builder, x0, x1, point)
        builder.cx(x0, h2)
        builder.ccx(middle[0], x0, h1)
        builder.ccx(middle[0], x0, h2)
        phase_moment(x0, F[:m], low, 0)
        masked = builder.alloc_qubits(12)
        builder.init_and(middle[0], q1, masked)
        builder.cx(masked, q1)
        xor_product(builder, q1, x1, h1)
        builder.cx(masked, q1)
        builder.del_and(middle[0], q1, masked)
        builder.free(masked)
        # The masked field is gone. Keep middle while querying f:
        # x1(12)+middle/f(2)+query ladder(10)=24 helpers, below25.
        f = query(0)
        builder.ccx(f[0], x1, h1)
        phase_moment(x1, F[:m], low, 1)

        # F[-1] and q1 have their original values throughout that interval.
        # The existing flags therefore enter G setup without two requeries.
        third = query(2)
        builder.cswap(third[0], h1, h3)
        builder.cx(h3, h1)
        builder.ccx(f[0], h3, h1)
        builder.ccx(middle[0], h3, h1)
        builder.ccx(third[0], h3, h1)
        release(0, f)
        builder.cswap(middle[0], h1, h2)
        builder.cx(middle, third)
        release(1, middle)
        y1, y2 = builder.alloc_qubits(12), builder.alloc_qubits(12)
        for point, (c, y) in enumerate(zip(G[:m], low)):
            square = FIELD.mul(point, point)
            add_scaled(builder, h3, y1, point)
            add_scaled(builder, h3, y2, square)
            xor_product(builder, c, y, h3)
            add_scaled(builder, h3, y2, square)
            add_scaled(builder, h3, y1, point)
        builder.ccx(third[0], y1, h1)
        phase_moment(y1, G[:m], low, 1)
        shared = builder.alloc_bits(1)
        builder.hmr(third, shared)
        builder.free(third)
        duplicate = builder.alloc_bits(1)
        builder.bit_store(duplicate, False)
        builder.cx(shared, duplicate)
        record_flag(1, shared)
        record_flag(2, duplicate)
        middle = query(1)
        masked = builder.alloc_qubits(12)
        builder.init_and(middle[0], q1, masked)
        xor_product(builder, masked, y2, h2)
        builder.del_and(middle[0], q1, masked)
        builder.free(masked)
        builder.cswap(middle[0], h1, h2)
        # y2 plus middle needs13 helpers; its HMR phase reads only G/low.
        # Keep this exact F[-1] predicate for final head restoration.
        phase_moment(y2, G[:m], low, 2)
        f, third = query(0), query(2)
        builder.ccx(third[0], h3, h1)
        builder.ccx(middle[0], h3, h1)
        builder.ccx(f[0], h3, h1)
        builder.cx(h3, h1)
        builder.cswap(third[0], h1, h3)
        if rhs_index+1 < len(rhss):
            # The first boundary retains only middle across its two fields.
            release(2, third)
            release(0, f)
        else:
            # The final shared source form needs only f with one field.
            release(1, middle)
    shared_source_form(f)
    evaluate(builder, G, m, True)
    evaluate(builder, F, m, True)
    # The final third bit never crosses a two-moment span. Both public
    # inverse views leave its high-word witness unchanged.
    return ThirdFlagHandoff(builder, third, G[-1])
