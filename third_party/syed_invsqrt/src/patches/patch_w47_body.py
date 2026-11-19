# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""MICRO47 COPY of agents/loader2/nopack46/patch_w47_body.py (no h0 pack, Q46): identical except A6_EARLY=True:
a6 = v[11] is X-measured right after prepare_H3_initial (its last reader before the divider) instead of after the seed,
so it is absent through the first coefficient forward, metadata retirement, seed and product forward; the existing
1-CCX current-D rebuild after the product forward (and the Z on the rebuilt owner that pays the HMR sign) is unchanged.
This gives coef1 its 46th-wire headroom at zero extra Toffolis. Copyright 2026 Syed Asad Ali, Apache-2.0; credits Opus and Astra.

AGENT LOADER2 COPY (no h0 pack) of agents/tk_q46/p/patch_w47_body.py: identical except PACK=False (h0 is NOT packed
into the flags in the root forward and NOT unpacked after the seed), because the first loader now fits at work cap 20
(agents/loader2/p/patch_ld_first20.py, 26 other owners + 20 = 46). Same file name on purpose (the decoder resynthesis
patch looks the body module up by name). The same edit as agents/loader/nopack/patch_w47_body.py made for Q47.
Original header: Agent width Q46 BODY (copy of patch_w47_body.py + a6 retired through the product forward, rebuilt from current D with 1 CCX).

Agent width Q47 BODY: free h0 packing into the exponent flags + Pro 2 snapshot2 table-cleanup tail (one emit_body).

Tail: identical to patch_snapshot2.py (decoder06 + 14 capture CX, paid-R, joint20 cleanup 769/128).
h0 packing (Pro 1 firstpack3, re-derived from its native text):

Measured from pro1_012 .../native_firstpack3/forward.kmx: it equals candidate10's root forward plus 11 ops
inserted just before the root's final carry_clear:
    h0' = h0 ^ 1 ^ v2 ^ v3 ^ v4 ^ c        (c = root conversion carry, still live there)
    flags2 ^= h0', flags3 ^= h0'            (h0' = 1 only when flags2 = flags3 = 0, so code 12..15 marks h0'=1)
    HMR h0'; CZ flags2 flags3 if outcome    (h0' == flags2 & flags3 after packing)
Unpack (3 Toffolis, from native_firstpack3/unpacked.kmx), after the first metadata retirement (raw R frame):
    h0 = (f2 f3) ^ 1 ^ v2 ^ v4 ^ (v0^v1)(v0^v2)(v0^v3^1);  flags2/3 restored.
This module supplies emit_body (a copy of candidate10 lifecycle10.emit_body that accepts an absent h0 and calls
unpack_h0 after first_metadata_retired) and wraps components['root'].forward. All other callbacks are read from the
live lifecycle/baseline modules at call time, so other agents' function replacements still compose.
"""
import types

import importlib.util, sys
from pathlib import Path

CTX = None
STATE = dict(flags=None, packed=False)
SNAPSHOT2_TAIL = True
TAIL = 'donor'
A6_AROUND_PRODUCT = True
A6_EARLY = True   # micro47: retire a6 right after prepare_H3_initial (covers coef1)   # Q46 body: retire a6 through the product forward (+1 Toffoli)
PACK = False   # agent loader2: no h0 pack
SNAP_PATH = Path('@FG_ROOT@/agents/width/src/decoder_snapshot_cleanup_q48.py')


def _snapshot_module():
    name = 'width_pro2_decoder_snapshot_cleanup_q48'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, SNAP_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def _pack(builder, h0, Q, c, flags):
    b = builder
    b.x(h0)
    for q in (Q[2], Q[3], Q[4], c):
        b.cx(q, h0)
    b.cx(h0, flags[2]); b.cx(h0, flags[3])
    m = b.alloc_bits(1)[0]
    b.hmr(h0, m); b.free(h0)
    b.push_condition(m); b.cz(flags[2], flags[3]); b.pop_condition()
    b.free(m)


def unpack_h0(builder, v, h, flags):
    b = builder
    assert h[0] is None
    q = b.alloc_qubits(1)[0]
    b.ccx(flags[2], flags[3], q)
    b.cx(q, flags[2]); b.cx(q, flags[3])
    t = b.alloc_qubits(1)[0]
    b.cx(v[0], v[1]); b.cx(v[0], v[2]); b.ccx(v[1], v[2], t); b.cx(v[0], v[2]); b.cx(v[0], v[1])
    b.x(q); b.cx(v[2], q); b.cx(v[4], q)
    b.cx(v[0], v[3]); b.x(v[3]); b.ccx(t, v[3], q); b.x(v[3]); b.cx(v[0], v[3])
    m = b.alloc_bits(1)[0]
    b.hmr(t, m); b.free(t)
    b.cx(v[0], v[1]); b.cx(v[0], v[2])
    b.push_condition(m); b.cz(v[1], v[2]); b.pop_condition()
    b.cx(v[0], v[2]); b.cx(v[0], v[1])
    b.free(m)
    h = list(h)
    h[0] = q
    return h


UNPACK_AFTER_SEED = True


def unpack_h0_after_seed(builder, v, h, flags, seed):
    """2 Toffolis. Measured on all inputs at seed_ready (raw v0..v4 unchanged by the seed):
    (v0^v1)(v0^v2) == v0 ^ v3 ^ 1 ^ seed[5], hence
    h0 = f2'f3' ^ v0 ^ v2 ^ v3 ^ v4 ^ seed[5]*(v0^v3^1)."""
    b = builder
    assert h[0] is None and len(seed) == 6
    q = b.alloc_qubits(1)[0]
    b.ccx(flags[2], flags[3], q)
    b.cx(q, flags[2]); b.cx(q, flags[3])
    for w in (v[0], v[2], v[3], v[4]):
        b.cx(w, q)
    b.cx(v[0], v[3]); b.x(v[3])
    b.ccx(seed[5], v[3], q)
    b.x(v[3]); b.cx(v[0], v[3])
    h = list(h)
    h[0] = q
    return h


def apply(ctx):
    global CTX
    CTX = ctx
    if not PACK:
        return
    norm_mod = ctx.components['normalization']
    root_mod = ctx.components['root']
    norm_forward = norm_mod.forward

    def normalization_forward(builder, original, flags):
        STATE['flags'] = list(flags)
        return norm_forward(builder, original, flags)
    new_norm = types.SimpleNamespace(**{k: getattr(norm_mod, k) for k in dir(norm_mod) if not k.startswith('__')})
    new_norm.forward = normalization_forward
    ctx.components['normalization'] = new_norm

    original_clear = root_mod.carry_clear
    original_forward = root_mod.forward

    def forward(builder, norm):
        norm = list(norm)
        h0 = norm[0]
        flags = STATE['flags']
        if flags is None:   # another patch replaced normalization.forward after us: build() allocates flags as q22..q25
            km = CTX.km
            flags = [km.q(22 + i) for i in range(4)]
            STATE['flags'] = flags
        assert len(flags) == 4

        def carry_clear(b, Q, p, c):
            if not STATE['packed']:
                STATE['packed'] = True
                _pack(b, h0, Q, c, flags)
            return original_clear(b, Q, p, c)
        root_mod.carry_clear = carry_clear
        try:
            out = original_forward(builder, norm)
        finally:
            root_mod.carry_clear = original_clear
        assert STATE['packed']
        residual = list(out['residual'])
        assert residual[0] == h0
        residual[0] = None
        return dict(root=out['root'], residual=residual)
    new_root = types.SimpleNamespace(**{k: getattr(root_mod, k) for k in dir(root_mod) if not k.startswith('__')})
    new_root.forward = forward
    ctx.components['root'] = new_root



DONOR = Path('@FG_ROOT@/work/pro1_013/narrow/arithmetic_round3/native/candidate11r2/candidate11r2.build.json')
_TAIL = {}


def _load_src(name, path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def _tail_modules():
    if not _TAIL:
        import json
        W = Path('@FG_ROOT@/agents/width')
        _TAIL['T1'] = json.loads((W / 'plans/T1_late_metadata.json').read_text())
        _TAIL['T2'] = json.loads((W / 'plans/T2_decoder_capture.json').read_text())
        assert _TAIL['T1']['ccx'] == 3 and _TAIL['T2']['ccx'] == 20 and _TAIL['T1']['external_bits'] == ['b75']
        cuts = {c['name']: c for c in json.loads(DONOR.read_text())['cuts']}
        _TAIL['T2_exit'] = cuts['raw_root_restored_with_paid_phase_product']['owners']
        _TAIL['replay'] = _load_src('width_block_replay', W / 'src/block_replay.py').replay
        _TAIL['paidR'] = _load_src('width_pro2_paid_R_cleanup_q48', W / 'src/paid_R_cleanup_q48.py')
    return _TAIL


def _role_map(plan, ours):
    m = {}
    for w, (role, i) in plan['entry_owner'].items():
        q = ours[role][i]
        assert q is not None, (w, role, i)
        m[w] = q
    return m

def _mark(builder, trace, label, owners=None):
    L = CTX.components['lifecycle']
    live = builder.num_allocated_qubits
    assert live <= builder.max_qubits, (label, live)
    if trace is not None:
        trace.append(dict(label=label, live_owners=live))
    if L.CUT_HOOK is not None:
        L.CUT_HOOK(label, builder, {} if owners is None else {key: list(value) for key, value in owners.items()})


def emit_body(builder, v12, h10, flags4, table_module, divider_module, decode_root_callback, *, trace=None):
    """candidate10 lifecycle10.emit_body with packed h0 (absent until unpack_h0) and the snapshot2 tail."""
    L = CTX.components['lifecycle']
    baseline = L.baseline
    assert builder.max_qubits in (46, 47, 48)
    v = list(v12); h = list(h10); flags = list(flags4)
    assert (len(v), len(h), len(flags)) == (12, 10, 4)
    if PACK:
        assert h[0] is None and len(set(v + h[1:] + flags)) == 25
    else:
        assert h[0] is not None and len(set(v + h + flags)) == 26
    _mark(builder, trace, 'body_entry', dict(v=v, h=h, flags=flags))
    table_debts = table_module.TableDebts(); truths = table_module.model_truths()

    D, Hlow = table_module.load_joint16(builder, v[5:], variant='first', debts=table_debts)
    D = list(D); H = list(Hlow)
    _mark(builder, trace, 'first_table', dict(v=v, h=h, flags=flags, D=D, H=H))
    H.append(baseline.prepare_H3_initial(builder, v, D, H))
    if A6_AROUND_PRODUCT and A6_EARLY:
        # micro47: a6 = v[11] is idle from here to the divider; X-measure it now (sign paid by Z on the rebuilt owner)
        a6_outcome = builder.alloc_bits(1)[0]; builder.hmr(v[11], a6_outcome); builder.free(v[11]); v[11] = None
    baseline.root_R_frame(builder, v)
    H.append(baseline.prepare_H4(builder, D, H[3]))
    first = baseline.coefficient_forward(builder, v, D, H)
    _mark(builder, trace, 'first_coefficient', dict(v=v, h=h, flags=flags, D=D, H=H, snapshot=[first.saved_bit]))
    Hlow = baseline.erase_high_H(builder, v, D, H)
    for i, q in enumerate(Hlow): table_debts.erase(builder, q, truths['H'][i], free=True)
    first_snapshot = baseline.ar.release_saved_bit(builder, first.saved_bit); first.saved_bit = None
    baseline.root_R_frame(builder, v, inverse=True)
    _mark(builder, trace, 'first_metadata_retired')
    if PACK and not UNPACK_AFTER_SEED:
        h = unpack_h0(builder, v, h, flags)
        _mark(builder, trace, 'width_h0_unpacked', dict(v=v, h=h, flags=flags, D=D))

    seed, seed_token = baseline.seed_forward(builder, v, D)
    if PACK and UNPACK_AFTER_SEED:
        h = unpack_h0_after_seed(builder, v, h, flags, seed)
    _mark(builder, trace, 'seed_ready', dict(v=v, h=h, flags=flags, D=D, seed=seed))
    if A6_AROUND_PRODUCT and not A6_EARLY:
        # Q46: a6 = v[11] is idle through the product forward; X-measure it (sign paid later by Z on the rebuilt owner)
        a6_outcome = builder.alloc_bits(1)[0]; builder.hmr(v[11], a6_outcome); builder.free(v[11]); v[11] = None
    word, product_token = baseline.product_forward(builder, D, seed, h)
    if A6_AROUND_PRODUCT:
        # current-D identity (research/current_D_a6_restore, exact on all 4096 roots): a6 = D10^D11^D12^(D10^a5)(D11^a5)
        q = builder.alloc_qubits(1)[0]
        for w in (D[10], D[11], D[12]):
            builder.cx(w, q)
        builder.cx(v[10], D[10]); builder.cx(v[10], D[11])
        builder.ccx(D[10], D[11], q)
        builder.cx(v[10], D[11]); builder.cx(v[10], D[10])
        builder.push_condition(a6_outcome); builder.z(q); builder.pop_condition(); builder.free(a6_outcome)
        v[11] = q
    builder.x(word[15]); builder.cx(word[14], word[15]); builder.free(word[15]); P = word[:15]
    _mark(builder, trace, 'signed_product15', dict(v=v, P=P, flags=flags, D=D))
    first_D = []
    for q in D:
        m = builder.alloc_bits(1)[0]; builder.hmr(q, m); builder.free(q); first_D.append(m)
    _mark(builder, trace, 'coefficient_retired_for_divider', dict(v=v, P=P, flags=flags))
    P = list(divider_module.compute_phase_cleanup(builder, v, P, flags))
    assert len(P) == 15 and len(set(v + P + flags)) == 31
    _mark(builder, trace, 'divider_return', dict(v=v, P=P, flags=flags))

    baseline.root_R_frame(builder, v)
    D, Hlow = table_module.load_joint16(builder, v[5:], variant='second', debts=table_debts)
    D = list(D); H = list(Hlow)
    retired = {a: None for a in (0, 1, 2, 4)}
    for a in retired: v[5 + a] = None
    assert all(v[5 + a] is None for a in (0, 1, 2, 4))
    assert v[8] is not None and v[10] is not None and v[11] is not None
    _mark(builder, trace, 'second_table', dict(v=v, P=P, flags=flags, D=D, H=H))
    baseline.ar.repay_saved_bit(builder, D[6], first_snapshot)

    H.append(baseline.prepare_H3_initial(builder, v, D, H))
    _mark(builder, trace, 'second_H3_ready', dict(v=v, P=P, flags=flags, D=D, H=H))
    q = v[11]; m = builder.alloc_bits(1)[0]; builder.hmr(q, m); builder.free(q)
    v[11] = None; retired[6] = m
    assert set(retired) == {0, 1, 2, 4, 6} and all(retired[a] is None for a in (0, 1, 2, 4))
    _mark(builder, trace, 'second_a6_retired', dict(v=v, P=P, flags=flags, D=D, H=H))
    H.append(baseline.prepare_H4(builder, D, H[3]))
    second = baseline.coefficient_forward(builder, v, D, H)
    _mark(builder, trace, 'second_coefficient', dict(v=v, P=P, flags=flags, D=D, H=H, snapshot=[second.saved_bit]))
    for q, m in zip(D, first_D):
        builder.push_condition(m); builder.z(q); builder.pop_condition(); builder.free(m)
    baseline.merge_coefficient_transcripts(builder, first, second)
    Hlow = baseline.erase_high_H(builder, v, D, H)
    _mark(builder, trace, 'second_metadata_retired')

    high = builder.alloc_qubits(1)[0]; builder.cx(P[14], high); builder.x(high); word = P + [high]
    _mark(builder, trace, 'inverse_product_data', dict(v=v, word=word, flags=flags, D=D, H=Hlow, snapshot=[second.saved_bit]))
    dirty = [q for q in v if q is not None] + flags + Hlow + [second.saved_bit]
    seed, h = L.product_inverse(builder, v, D, word, product_token, dirty)
    baseline.seed_cleanup(builder, v, D, seed, seed_token)
    if TAIL == 'donor':
        _mark(builder, trace, 'seed_cleared', dict(v=v, h=h, flags=flags, D=D, H=Hlow, snapshot=[second.saved_bit]))
        tail = _tail_modules()
        # donor T1 (candidate11r2 early metadata): a6 from current D (1 CCX, its HMR sign paid), then H3 (1) and H4 (1)
        wm = _role_map(tail['T1'], dict(v=v, h=h, flags=flags, D=D, H=Hlow, snapshot=[second.saved_bit]))
        out = tail['replay'](builder, tail['T1'], wm, ext_bits={'b75': retired[6]})
        builder.free(retired[6]); retired[6] = None
        v[11] = out['q26']
        H = list(Hlow) + [out['q9'], out['q43']]
        _mark(builder, trace, 'coefficient_sources_restored')
        baseline.coefficient_inverse(builder, v, D, H, second, [q for q in v if q is not None] + flags + h)
        _mark(builder, trace, 'A_restored', dict(v=v, h=h, flags=flags, A=D, H=H))
        # donor T2: decoder for the four consumed address bits (a6 already back) + paid-R capture around the R inverse
        wm = _role_map(tail['T2'], dict(v=v, h=h, flags=flags, A=D, H=H))
        out = tail['replay'](builder, tail['T2'], wm)
        ex = tail['T2_exit']
        v = [out[w] for w in ex['v']]; h = [out[w] for w in ex['h']]; flags = [out[w] for w in ex['flags']]
        D = [out[w] for w in ex['A']]; H = [out[w] for w in ex['H']]; product = out[ex['phase_snapshot'][0]]
        assert all(q is not None for q in v) and len(set(v + h + flags)) == 26
        _mark(builder, trace, 'raw_root_restored_with_paid_R', dict(v=v, h=h, flags=flags, A=D, H=H, phase_snapshot=[product]))
        tail['paidR'].cleanup_joint18(builder, v[5:], D, H, product, table_debts, table_api=table_module)

    else:
        _mark(builder, trace, 'seed_cleared', dict(v=v, h=h, flags=flags, D=D, H=Hlow, snapshot=[second.saved_bit]))
        H = list(Hlow); H.append(baseline.prepare_H3_current(builder, v, D, H))
        H.append(baseline.prepare_H4(builder, D, H[3]))
        _mark(builder, trace, 'coefficient_sources_restored')
        baseline.coefficient_inverse(builder, v, D, H, second, [q for q in v if q is not None] + flags + h)
        _mark(builder, trace, 'A_restored', dict(v=v, h=h, flags=flags, A=D, H=H))
        if SNAPSHOT2_TAIL:
            snap = _snapshot_module()
            v, snapshots = snap.decode_root_with_snapshots(builder, v, D, H, retired)
            v = list(v)
            assert all(q is not None for q in v) and len(set(v + h + flags)) == 26
            product = snap.capture_R_before_inverse(builder, v[8])
            baseline.root_R_frame(builder, v, inverse=True)
            snap.finish_R_capture(builder, v[8], v[7], product)
            _mark(builder, trace, 'raw_root_restored_with_paid_R', dict(v=v, h=h, flags=flags, A=D, H=H, snapshots=snapshots))
            snap.cleanup_joint20(builder, v[5:], D, H, snapshots, product, table_debts, table_api=table_module)
        else:
            v = list(decode_root_callback(builder, v, D, H, retired))
            assert all(q is not None for q in v) and len(set(v + h + flags)) == 26
            baseline.root_R_frame(builder, v, inverse=True)
            _mark(builder, trace, 'raw_root_restored', dict(v=v, h=h, flags=flags, A=D, H=H))
            Hlow = baseline.erase_high_H(builder, v, D, H, initial=True)
            table_module.cleanup_joint16(builder, v[5:], D, Hlow, table_debts)

    assert not table_debts.pending
    assert first.saved_bit is None and second.saved_bit is None
    for token in (first, second):
        assert all(debt.consumed and not debt.measurements for debt in token.row_debts)
        assert token.overflow_debt.consumed and not token.overflow_debt.measurements
    assert all(debt.consumed and not debt.measurements for debt in product_token.rows)
    _mark(builder, trace, 'body_return', dict(v=v, h=h, flags=flags))
    return v, h
