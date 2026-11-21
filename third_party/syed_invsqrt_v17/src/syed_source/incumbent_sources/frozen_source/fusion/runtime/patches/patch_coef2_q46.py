# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""prodcoef2 patch COEF2Q46: the SECOND coefficient forward at cap 46 for +1 expected Toffoli.

Fact used (the pinned H4 plan, slope_h3_h4_retirement_v3.json): H4 = D12 ^ H3 ^ D11*H3, so D12 = H4 ^ H3 ^ D11*H3.
In the second coefficient forward D12 is idle through the five coefficient rows (rows touch D[:7]; sources are
S = v8, H0..H4) and H4 is idle through the overflow (D[7:13] += wrap) and is erased right after the forward anyway.
Second call only (v[11] already retired):
  1. X-measure D12 before the rows (outcome m): the rows then peak at 46 instead of 47;
  2. after the rows turn the H4 wire into D12 in place (CX H3, CCX D11 H3: 1 Toffoli) and pay m by Z on the
     rebuilt D12 owner; the overflow then also peaks at 46;
  3. erase_high_H skips the H4 erasure of that call (H4 no longer exists; its wire is D[12]).
Rows and overflow are the COEFDISP kernels (own copy of agents/prodcoef/patch_coefdisp.py), so the debt positions
and widths are unchanged and merge_coefficient_transcripts stays valid. The first call goes to whatever
coefficient_forward is live. Compose AFTER patch_coefdisp.py (and before patch_capwin46.py if that is used).
Replaces baseline.coefficient_forward and baseline.erase_high_H (both delegate to the previous ones otherwise).
"""

STATE = dict(calls=0, converted=None, applied=0)


def make(baseline, previous_forward, previous_erase):
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

    def second_forward(builder, v, D, H):
        assert len(D) == 13 and len(H) == 5 and v[11] is None
        h3, h4, d11 = H[3], H[4], D[11]
        # 1. D12 is idle through the rows: X-measure it; its sign is paid by Z on the rebuilt owner (step 2).
        m = builder.alloc_bits(1)[0]; builder.hmr(D[12], m); builder.free(D[12]); D[12] = None
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
        # 2. H4 -> D12 in place: H4 ^ H3 ^ D11*H3 = D12 (D11, H3 untouched by the rows). 1 Toffoli.
        builder.cx(h3, h4); builder.ccx(d11, h3, h4)
        builder.push_condition(m); builder.z(h4); builder.pop_condition(); builder.free(m)
        D[12] = h4; STATE['converted'] = h4; STATE['applied'] += 1
        overflow_forward_disposable(builder, v[:5], S, D, token)
        return token

    def coefficient_forward(builder, v, D, H):
        STATE['calls'] += 1
        if STATE['calls'] == 2:
            return second_forward(builder, v, D, H)
        return previous_forward(builder, v, D, H)

    def erase_high_H(builder, v, D, H, *, initial=False):
        h4 = STATE['converted']
        if h4 is not None and not initial and len(H) == 5 and H[4] is h4:
            assert D[12] is h4
            STATE['converted'] = None
            # H4 is gone (its wire now holds D12); erase H3 exactly as the original second call does.
            variables = [D[i] for i in (9, 10, 11, 12)] + [H[2], v[10]]
            baseline._erase(builder, H[3], variables, baseline.H3_CURRENT)
            return list(H[:3])
        return previous_erase(builder, v, D, H, initial=initial)

    return coefficient_forward, erase_high_H


def apply(ctx):
    bl = ctx.baseline
    for name in ('_erase', 'H3_CURRENT', '_coefficient_carry', '_clear_coefficient_carry', 'SimpleNamespace', 'ar', 'km'):
        assert hasattr(bl, name), name
    bl.coefficient_forward, bl.erase_high_H = make(bl, bl.coefficient_forward, bl.erase_high_H)
