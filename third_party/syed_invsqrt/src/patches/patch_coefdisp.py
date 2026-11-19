# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""prodcoef patch COEFDISP: coefficient forward with early release of its owned
incoming carries (Pro 1's research/q47_forward_disposable/forward_source.py,
coefficient_forward_disposable + coefficient_overflow_forward_disposable +
forward_add_disposable, copied with baseline/km bound explicitly).

Zero Toffolis by itself: the owned rounding carry (and the overflow wrap) is
erased by del_and right after the first sum, so both coefficient forwards peak
at 47. The recomputed R-frame product (ops ~5873/~6198) then has a spare wire
over the whole first coefficient forward, which the lead's hold pass uses.
Debt positions/widths are identical to the original (merge stays valid).
Replaces baseline.coefficient_forward only.
"""


def make(baseline):
    km = baseline.km

    def forward_add_disposable(arithmetic, builder, source, target, *, carry_in, erase_input):
        assert isinstance(carry_in, km.q) and callable(erase_input)
        a, b, preserve = arithmetic._inputs(source, target, carry_in, False)
        width = len(b); debts = {}; released = False
        assert preserve is None
        if not width:
            return arithmetic.CarryDebt(debts, width), False
        if width == 1:
            builder.cx(a[0], b[0]); builder.cx(carry_in, b[0])
            return arithmetic.CarryDebt(debts, width), False

        def measure(carry, position):
            if carry is False:
                return
            outcome = builder.alloc_bits(1)[0]; builder.hmr(carry, outcome); builder.free(carry)
            debts[position] = outcome

        carry = carry_in
        for index, (aa, bb) in enumerate(zip(a[:-2], b[:-2])):
            frame = arithmetic._compute_carry(builder, aa, bb, carry, preserve=preserve)
            arithmetic._sum_keep_carry(builder, frame)
            if index == 0:
                assert frame.incoming == carry_in and frame.outgoing is not False and frame.outgoing != carry_in
                erase_input(carry_in); released = True
            if index:
                measure(carry, index)
            carry = frame.outgoing
        arithmetic._finish_top(builder, a, b, carry, preserve)
        if width > 2:
            measure(carry, width - 2)
        return arithmetic.CarryDebt(debts, width), released

    def overflow_forward_disposable(builder, residual, source, target, token):
        if token.saved_bit is None:
            return
        assert not token.plan.signed_source
        sigma = residual[token.plan.last - 1]; top = target[token.window - 1]; saved = token.saved_bit
        builder.cx(sigma, saved); builder.cx(sigma, top); builder.x(top)
        wrap = builder.alloc_qubits(1)[0]; builder.ccx(saved, top, wrap)
        high = target[token.window:]
        for wire in high:
            builder.cx(sigma, wire)

        def erase_wrap(value):
            builder.del_and(saved, top, value); builder.free(value)

        token.overflow_debt, released = forward_add_disposable(baseline.ar, builder, [], high,
                                                               carry_in=wrap, erase_input=erase_wrap)
        for wire in high:
            builder.cx(sigma, wire)
        if not released:
            erase_wrap(wrap)
        builder.x(top); builder.cx(sigma, top); builder.cx(sigma, saved)

    def coefficient_forward(builder, v, D, H):
        S = [v[8]] + list(H); snapshot = builder.alloc_qubits(1)[0]; builder.cx(D[6], snapshot)
        token = baseline.ar.DeferredBoundedToken(baseline.SimpleNamespace(last=5, signed_source=False), snapshot, 7, [])
        for i in range(5):
            k = 4 - i; carry = baseline._coefficient_carry(builder, S, v[i], k)
            for q in D[:7]:
                builder.cx(v[i], q)
            debt, released = forward_add_disposable(
                baseline.ar, builder, S[k + 1:], D[:7], carry_in=carry,
                erase_input=lambda value, i=i, k=k: baseline._clear_coefficient_carry(builder, S, v[i], k, value))
            token.row_debts.append(debt)
            for q in D[:7]:
                builder.cx(v[i], q)
            if not released:
                baseline._clear_coefficient_carry(builder, S, v[i], k, carry)
        overflow_forward_disposable(builder, v[:5], S, D, token)
        return token
    return coefficient_forward


def apply(ctx):
    ctx.baseline.coefficient_forward = make(ctx.baseline)
