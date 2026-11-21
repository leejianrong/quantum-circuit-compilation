# normroot agent, 2026-11-12. Composable patch: normalization forward only (supersedes patch_fwd_neighbor).
"""Narrow forward normalization: same 18+1+32 Toffolis, no conditional CCZ, local peak 37 instead of 46.

Changes against normalization9475.forward (inverse untouched, n22/flags4 interface identical):
1. P1 = NOT x21 gets no wire: X(x21) turns x21 into P1; it is used as a CX source while it is P1 and then
   becomes the H accumulator (H = 1 xor P1 xor ... xor P20 xor P20*NOT x1), so it is never measured.
2. Every odd prefix P_(L-1) is measured right after P_L is computed and its CX uses are done. Its HMR
   fix-up uses the running parity x21 = 1 xor sum_(l<=L) P_l:
       P_(L-1) = P_(L-2) xor P_(L-2)*x21 xor P_L*x21      (L even)  -> Z/CZ only.
   The leading-one clearing of position 22-L, and the x0/x1/H accumulations, are done as soon as P_L
   exists (position 22-L is no longer needed as data). x1 is accumulated early; when P20 = 1 all
   P1..P19 are 1, so the accumulated x1' equals NOT x1 and CCX(P20, x1', x21) is the base H gate.
3. Thresholds are erased with the neighbour trick of patch_fwd_neighbor (no conditional CCZ).
"""


def apply(ctx):
    norm = ctx.components['normalization']
    route_lane, rows = norm.route_lane, norm.FORWARD_ROWS
    assert all(((rows[j - 1] >> 6) & 1) == 0 for j in (2, 4, 6, 8, 10))

    def forward(builder, x, flags):
        x = list(x); flags = list(flags)
        assert len(x) == 22 and len(flags) == 4
        h = x[21]
        builder.x(h)                       # h = P1
        P = {1: h}
        builder.cx(h, x[0]); builder.cx(h, x[1])   # P1 parts of the x0 / x1 clearing
        q = builder.alloc_qubits(1)[0]     # P2 = P1 xor x20 (task promise: not both top bits)
        builder.cx(h, q); builder.cx(x[20], q)
        P[2] = q
        builder.cx(h, x[20]); builder.cx(q, x[20])  # clear position 20 (prefixes 1,2)
        builder.x(h)                       # h = 1 xor P1
        builder.cx(q, h)                   # h = 1 xor P1 xor P2
        builder.cx(q, x[0]); builder.cx(q, x[1])
        for L in range(3, 21):
            i = 22 - L
            q = builder.alloc_qubits(1)[0]
            builder.x(x[i]); builder.ccx(P[L - 1], x[i], q); builder.x(x[i])
            P[L] = q
            builder.cx(P[L - 1], x[i]); builder.cx(q, x[i])   # clear position i (prefixes L-1, L)
            builder.cx(q, h); builder.cx(q, x[0])
            if L <= 19: builder.cx(q, x[1])
            if L % 2 == 0:                 # erase odd prefix P_(L-1) with the running parity h
                odd, low, up = P[L - 1], P[L - 2], P[L]
                m = builder.alloc_bits(1)[0]; builder.hmr(odd, m)
                builder.push_condition(m)
                builder.z(low); builder.cz(low, h); builder.cz(up, h)
                builder.pop_condition()
                builder.free(m); builder.free(odd)
                del P[L - 1]
        T = [P[2 * j] for j in range(1, 11)]
        builder.ccx(T[-1], x[1], h)        # h = H (x1 here is NOT x1 whenever P20 = 1)
        builder.x(x[0]); builder.cx(h, x[0])
        builder.x(x[1]); builder.cx(h, x[1])
        for bit, flag in enumerate(flags):
            for j in range(1 << bit, 11, 1 << bit): builder.cx(T[j - 1], flag)
        route_lane(builder, x[0::2], T); route_lane(builder, x[1:21:2], T)
        builder.x(x[20]); builder.cx(x[21], x[20])
        k0 = flags[0]
        for j in (1, 3, 5, 7, 9):
            q = T[j - 1]
            outcome = builder.alloc_bits(1)[0]; builder.hmr(q, outcome)
            builder.push_condition(outcome)
            upper = T[j]
            builder.z(upper)
            if j == 1: builder.z(k0)
            else: builder.cz(k0, T[j - 2])
            builder.cz(k0, upper)
            builder.pop_condition()
            builder.free(outcome); builder.free(q)
        for j in (2, 4, 6, 8, 10):
            q, row = T[j - 1], rows[j - 1]
            outcome = builder.alloc_bits(1)[0]; builder.hmr(q, outcome)
            builder.push_condition(outcome)
            for mask in range(1, 11):
                if ((row >> (mask - 1)) & 1) == 0: continue
                controls = [flags[i] for i in range(4) if (mask >> i) & 1]
                if len(controls) == 1: builder.z(controls[0])
                else: assert len(controls) == 2; builder.cz(*controls)
            builder.pop_condition()
            builder.free(outcome); builder.free(q)

    norm.forward = forward
