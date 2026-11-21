# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""prodcoef2 patch H2RET: retire the second-table metadata bit H2 through the whole inverse product + seed cleanup
(one more clean wire for every inverse adder row) and rebuild it with 3 Toffolis before the late metadata (T1).

Measured fact (full domain, Q46 raw build pc2_q46a, op 22342 = inverse_product_data; 39 reachable rows of 64):
H2 is a function of D9, D10, D11, D12, H0, H1 only, and the exact minimum-AND search (tools/minand_sat.py) gives
k=1 UNSAT, k=2 UNSAT, k=3 SAT:
    H2 = D10 ^ D11 ^ D12 ^ (D9^D11)(D9^H1) ^ g0*M,   g0 = (D9^D10^D11^H1)(D10^H0),   M = D9^D10^D11^D12^H0^H1.
D (post second coefficient forward), H0 and H1 are unchanged through the inverse product (source / dirty spectators).
H2's last use before the inverse product is the H3 erasure of the second erase_high_H call; next use is T1.
Steps: X-measure H2 at the start of product_inverse (removed from the dirty list); after seed_cleanup rebuild it on a
fresh wire (3 CCX; the temporary g0 is X-measured, its sign paid by CZ on its two factors); pay H2's outcome by Z on
the rebuilt owner; the body's Hlow list (the object returned by erase_high_H) gets the new owner in place.
Wraps baseline.erase_high_H, lifecycle.product_inverse and baseline.seed_cleanup (all delegate). Apply AFTER
patch_seedinv.py (and after patch_coef2_q46.py if used).
"""

STATE = dict(erase_calls=0, hlow=None, outcome=None, applied=0)


def _form(builder, wires):
    """XOR of wires onto a fresh temporary (returns (wire, owned))."""
    if len(wires) == 1:
        return wires[0], False
    t = builder.alloc_qubits(1)[0]
    for w in wires:
        builder.cx(w, t)
    return t, True


def _unform(builder, t, owned, wires):
    if owned:
        for w in wires:
            builder.cx(w, t)
        builder.free(t)


def _and_into(builder, left, right, target):
    a, oa = _form(builder, left); b, ob = _form(builder, right)
    builder.ccx(a, b, target)
    _unform(builder, b, ob, right); _unform(builder, a, oa, left)


def rebuild_h2(builder, D, H0, H1):
    D9, D10, D11, D12 = D[9], D[10], D[11], D[12]
    L0 = [D9, D10, D11, H1]; R0 = [D10, H0]
    M = [D9, D10, D11, D12, H0, H1]
    t = builder.alloc_qubits(1)[0]
    for w in (D10, D11, D12):
        builder.cx(w, t)
    _and_into(builder, [D9, D11], [D9, H1], t)              # (D9^D11)(D9^H1)
    g0 = builder.alloc_qubits(1)[0]
    _and_into(builder, L0, R0, g0)                          # g0
    _and_into(builder, [g0], M, t)                          # g0 * M
    # erase g0 = L0*R0 by X-measurement; sign paid by CZ on its factors
    m = builder.alloc_bits(1)[0]; builder.hmr(g0, m); builder.free(g0)
    a, oa = _form(builder, L0); b, ob = _form(builder, R0)
    builder.push_condition(m); builder.cz(a, b); builder.pop_condition()
    _unform(builder, b, ob, R0); _unform(builder, a, oa, L0)
    builder.free(m)
    return t


def apply(ctx):
    bl = ctx.baseline
    lc = ctx.components['lifecycle']
    previous_erase = bl.erase_high_H
    previous_inverse = lc.product_inverse
    previous_cleanup = bl.seed_cleanup

    def erase_high_H(builder, v, D, H, *, initial=False):
        out = previous_erase(builder, v, D, H, initial=initial)
        if not initial:
            STATE['erase_calls'] += 1
            if STATE['erase_calls'] == 2:
                out = list(out)
                STATE['hlow'] = out
        return out

    def product_inverse(builder, v, D, word, token, dirty):
        hlow = STATE['hlow']
        assert hlow is not None and len(hlow) == 3 and hlow[2] is not None
        h2 = hlow[2]
        assert sum(1 for q in dirty if q is h2) == 1
        m = builder.alloc_bits(1)[0]; builder.hmr(h2, m); builder.free(h2)
        hlow[2] = None; STATE['outcome'] = m
        dirty = [q for q in dirty if q is not h2]
        return previous_inverse(builder, v, D, word, token, dirty)

    def seed_cleanup(builder, v, D, seed, token):
        out = previous_cleanup(builder, v, D, seed, token)
        hlow = STATE['hlow']
        if hlow is not None and hlow[2] is None:
            t = rebuild_h2(builder, D, hlow[0], hlow[1])
            m = STATE['outcome']; STATE['outcome'] = None
            builder.push_condition(m); builder.z(t); builder.pop_condition(); builder.free(m)
            hlow[2] = t; STATE['applied'] += 1
        return out

    bl.erase_high_H = erase_high_H
    lc.product_inverse = product_inverse
    bl.seed_cleanup = seed_cleanup
