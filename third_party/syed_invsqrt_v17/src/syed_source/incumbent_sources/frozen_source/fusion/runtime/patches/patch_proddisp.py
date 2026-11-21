# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""prodcoef patch PRODDISP: product forward with early release of the owned
rounding carry of rows 0-7 (Pro 1's research/q47_forward_disposable/forward_source.py
product_forward_disposable, copied with baseline bound; adder kernel shared
with patch_coefdisp.py in spirit).  Zero Toffolis; product forward peaks at 47.
Debt positions/widths identical to the original. Replaces baseline.product_forward only.
"""


def make(baseline):
    km = baseline.km

    def forward_add_disposable(arithmetic, builder, source, target, *, carry_in, erase_input):
        assert isinstance(carry_in, km.q) and callable(erase_input)
        a, b, preserve = arithmetic._inputs(source, target, carry_in, False)
        width = len(b); debts = {}; released = False
        assert preserve is None and width > 2

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
        measure(carry, width - 2)
        return arithmetic.CarryDebt(debts, width), released

    def product_forward(builder, D, seed, h):
        word = list(seed) + list(h); C = [False] + list(D); rows = []; builder.x(word[15])
        for i in range(10):
            q = word[6 + i]; target = word[:6 + i]; source = C[9 - i:] if i < 9 else C
            for t in target:
                builder.cx(q, t)
            carry = baseline._product_carry(builder, C, q, i)
            if i < 8:
                debt, released = forward_add_disposable(
                    baseline.product_ar, builder, source, target, carry_in=carry,
                    erase_input=lambda value, i=i, q=q: baseline._clear_product_carry(builder, C, q, i, value))
                assert released
            else:
                debt = baseline.product_ar.forward_add(builder, source, target, carry_in=carry); released = False
            rows.append(debt)
            if not released:
                baseline._clear_product_carry(builder, C, q, i, carry)
            for t in target:
                builder.cx(q, t)
        builder.x(word[15])
        return word, baseline.ProductToken(rows)
    return product_forward


def apply(ctx):
    ctx.baseline.product_forward = make(ctx.baseline)
