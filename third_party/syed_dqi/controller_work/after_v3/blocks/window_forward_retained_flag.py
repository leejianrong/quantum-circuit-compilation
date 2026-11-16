# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Borrowed forward tensor with the caller's already-computed third flag.

New candidate, separate from the queued self-contained56-T improvement.
Contract: the caller supplies a disjoint live quantum bit equal to zero(G[-1]).
It remains unchanged and owned by the caller. Only f/m are queried and their
actual HMR masks are returned as slots0/1. All target-product masks close here.
The mathematical four-mode domain and complete source/head restoration are
identical to window_forward_borrowed; no caller control is treated as free.

Model:168*m+634 T inside this function,14 owned helpers plus the suppliedflag.
The caller separately eliminates its second11-T query, for22 T per forward
call relative to the self-contained borrowed tensor. No transpose change.
"""
import kickmix as km
from raw_window_tensor import evaluate
from monic_forney import F as FIELD, add_scaled
from coherent_border import toggle_zero
from tower_inverse import xor_product, phase_product, kernel


def emit(builder, F, G, q0, q1, rhss, record_flag, third_flag):
    # Validate the entire physical view before emitting or allocating.
    m = len(G)-1
    assert m >= 1 and len(F) == m+2 and len(rhss) == 2
    assert all(len(rhs) == m+3 for rhs in rhss)
    words = [*F, *G, q0, q1, *rhss[0], *rhss[1]]
    assert all(len(word) == 12 for word in words)
    wires = [wire for word in words for wire in word]
    assert all(isinstance(wire, km.q) for wire in wires)
    assert len(set(wires)) == len(wires), 'source, head, or target views overlap'
    assert callable(record_flag)
    assert len(third_flag) == 1 and isinstance(third_flag[0], km.q)
    assert third_flag[0] not in set(wires)
    witnesses = (q1, F[-1], G[-1])
    flags = []
    for witness in witnesses[:2]:
        flag = builder.alloc_qubits(1)
        toggle_zero(builder, witness, flag[0])
        flags.append(flag)
    f, middle = flags
    third = third_flag

    def source_form():
        masked = builder.alloc_qubits(12)
        builder.init_and(f[0], q0, masked)
        builder.cx(masked, q0)
        for rhs in rhss:
            xor_product(builder, q0, rhs[-1], rhs[-2])
        builder.cx(masked, q0)
        builder.del_and(f[0], q0, masked)
        builder.free(masked)

    evaluate(builder, F, m)
    evaluate(builder, G, m)
    for point in range(m):
        add_scaled(builder, G[point], F[point], point)
    source_form()
    for rhs in rhss:
        low = rhs[:m]
        k, y, h = rhs[m:]
        product = builder.alloc_qubits(12)
        # The original quotient is restored before either borrowed-source
        # interval and before its measurement mask is repaid.
        builder.cx(f[0], q1[0])
        xor_product(builder, q1, h, product)
        builder.cx(f[0], q1[0])

        # Only F[:m] is read during this interval.  F[-1] is known zero
        # exactly on the branch that moves the product into that field.
        builder.cswap(middle[0], product, F[-1])
        builder.cswap(middle[0], h, y)
        for point, (coefficient, target) in enumerate(zip(F[:m], low)):
            add_scaled(builder, product, y, point)
            xor_product(builder, coefficient, y, target)
            add_scaled(builder, product, y, point)
        builder.cswap(middle[0], h, y)
        builder.cswap(middle[0], product, F[-1])

        # The three G coefficients become k0, y+m*h+t*k, and product.
        # G[-1] is borrowed only under its actual zero predicate.  G[:m]
        # still contains the evaluations of the unmodified source G.
        builder.ccx(middle[0], h, y)
        builder.ccx(third[0], k, y)
        builder.cswap(third[0], k, G[-1])
        builder.cx(h, k)
        builder.ccx(f[0], h, k)
        builder.ccx(middle[0], h, k)
        for point, (coefficient, target) in enumerate(zip(G[:m], low)):
            square = FIELD.mul(point, point)
            add_scaled(builder, y, k, point)
            add_scaled(builder, product, k, square)
            xor_product(builder, coefficient, k, target)
            add_scaled(builder, product, k, square)
            add_scaled(builder, y, k, point)
        builder.ccx(middle[0], h, k)
        builder.ccx(f[0], h, k)
        builder.cx(h, k)
        builder.cswap(third[0], k, G[-1])
        builder.ccx(third[0], k, y)
        builder.ccx(middle[0], h, y)

        mask = builder.alloc_bits(12)
        builder.hmr(product, mask)
        builder.free(product)
        phase_product(builder, q1, h, mask, kernel(12))
        for bit in range(12):
            builder.ccz(mask[bit], f[0], h[bit])
        builder.free(mask)
    source_form()
    for point in range(m):
        add_scaled(builder, G[point], F[point], point)
    evaluate(builder, G, m, True)
    evaluate(builder, F, m, True)
    for slot, flag in enumerate(flags):
        mask = builder.alloc_bits(1)
        builder.hmr(flag, mask)
        builder.free(flag)
        record_flag(slot, mask)
