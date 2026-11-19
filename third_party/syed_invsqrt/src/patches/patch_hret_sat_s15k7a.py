# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0. Credits: Opus and Astra.
"""COMPOSER FROZEN PIN s15k7a (forms: k=15 hret_s15k7a_s15.json sha a742f55004f9; environment W2_HRET_SAT ignored).
width2 copy of the divider patch HRET q46 with SAT-form restores: env W2_HRET_SAT = "k:path.json,..." gives, for history
sign k, an exact straight-line AND program (tools/minand_sat.py JSON) over role-named inputs (v0..v11 = token.v, "next" =
s_{k+1} = token.u[-1] at the rebuild point); k is then also retired after the endpoint and rebuilt right before its
inverse row from that program (factors formed in place, helpers X-measured + CZ), sign paid by Z on the rebuilt owner.
W2_HRET_SAT_ROLES maps the JSON input names to roles (default: q16..q20,q42 -> v6..v11, q30 -> next).
Original docstring: Divider patch HRET (cap-aware 48/47/46): retire history signs 13..K after the phase endpoint and rebuild each one
right before its inverse row from root bits and the next sign; history12 retirement as in AR004.

Replaces only ctx.old.divider.cleanup_divider. Forward, endpoint and phase are unchanged.
- cap >= 48: pinned top12 kernel for the final row (as patch_hret14.py, byte-identical output).
- cap 47:   relaxed top12 copy ((4,4,4) final-row partition), as patch_hret14_cap.py.
- cap 46:   the final feed row j12 runs through the ordinary adaptive inverse_add (feed-carry lifecycle) and the
            original candidate01 cleanup_u12 (1 Toffoli, peak 45), because the top12 kernel cannot fit 12 lower
            positions at 42 data owners under 46.
Env DIVIDER_FORCE_CAP=46 lowers the builder cap to 46 only inside this cleanup (measurement inside a Q47 build).
Env DIVIDER_RETIRE="13,14" (default) selects the retired signs (15 needs its formula below).
"""
import os, sys
import importlib.util
from pathlib import Path

_RELAXED = Path('@FG_ROOT@/agents/divider/src/top12_kernel_relaxed.py')

FORMULAS = {
    13: dict(parents=[('v', 8), ('v', 9), ('v', 10), ('v', 11), ('next',)],
             helpers=[dict(width=5, constant=0, linear=2, edges=[(0, 1), (0, 2), (1, 2), (1, 3), (2, 3)])],
             decoder=dict(width=6, constant=0, linear=46, edges=[(1, 3), (1, 5), (3, 4), (4, 5)]), ands=2),
    14: dict(parents=[('v', 7), ('v', 8), ('v', 9), ('v', 10), ('v', 11), ('next',)],
             helpers=[dict(width=6, constant=0, linear=0, edges=[(1, 3)]),
                      dict(width=6, constant=0, linear=16, edges=[(0, 1), (0, 2), (0, 4), (1, 4), (1, 5), (2, 4), (2, 5), (4, 5)])],
             decoder=dict(width=8, constant=0, linear=186, edges=[(0, 2), (0, 3), (0, 4), (0, 5), (0, 7), (1, 2), (1, 4), (1, 6), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (3, 4), (3, 5), (3, 6), (4, 5), (4, 7), (5, 7), (6, 7)]), ands=4),
}
EXTRA = Path('@FG_ROOT@/agents/divider/build_base/extra_formulas.json')
if EXTRA.exists():
    import json
    for k, f in json.loads(EXTRA.read_text()).items():
        FORMULAS[int(k)] = dict(parents=[tuple(p) for p in f['parents']], helpers=f['helpers'], decoder=f['decoder'],
                                ands=f['ands'], nested=f.get('nested', False))
RETIRE = tuple(int(x) for x in os.environ.get('DIVIDER_RETIRE', '13,14').split(','))
if os.environ.get('DIVIDER_PLACEHOLDER'):   # ANALYSIS ONLY (wrong circuit): zero-AND placeholder rebuilds
    for _k in RETIRE:
        FORMULAS.setdefault(_k, dict(parents=[('v', 0)], helpers=[], decoder=dict(width=1, constant=0, linear=1, edges=[]), ands=0))
FORCE = int(os.environ.get('DIVIDER_FORCE_CAP', '0'))


import json as _json
_SAT = {}
assert __import__('hashlib').sha256(Path('@FG_ROOT@/agents/composer/p/hret_s15k7a_s15.json').read_bytes()).hexdigest() == 'a742f55004f9fec20d1b5de31f87255a99fd7830f35bc9eb645fa94b0fee588e'
_SAT[15] = _json.loads(Path('@FG_ROOT@/agents/composer/p/hret_s15k7a_s15.json').read_text()); assert _SAT[15]['status'] == 'SAT'
_ROLES = dict(x.split('=') for x in 'q16=v6,q17=v7,q18=v8,q19=v9,q20=v10,q42=v11,q30=next'.split(','))
_ROLES.update({'v%d' % i: 'v%d' % i for i in range(12)}); _ROLES.update({'s%d' % (k + 1): 'next' for k in _SAT})
if _SAT:
    RETIRE = tuple(sorted(set(RETIRE) | set(_SAT)))


def _pair_forms(b, SA, SB):
    SA = list(dict.fromkeys(SA)); SB = list(dict.fromkeys(SB))
    ops = []
    a = SA[0]
    for w in SA[1:]:
        b.cx(w, a); ops.append((w, a))
    if a in SB:
        SBc = (set(SA) - {a}) ^ (set(SB) - {a}); SBc.add(a)
    else:
        SBc = set(SB)
    cands = [w for w in SB if w in SBc and w != a] + [w for w in SA if w in SBc and w != a] + [w for w in SBc if w != a]
    assert cands, 'degenerate AND'
    bp = cands[0]
    for w in [x for x in SB + SA + [a] if x in SBc and x != bp]:
        if (w, bp) in ops:
            continue
        b.cx(w, bp); ops.append((w, bp))
    return a, bp, ops


def _undo(b, ops):
    for c, t in reversed(ops):
        b.cx(c, t)


def _emit_sat(b, form, wires, target):
    n = len(form['inputs']); gates = form['gates']; vals = list(wires)
    used_later = [any(n + i in g2['left'] or n + i in g2['right'] for g2 in gates[i + 1:]) for i in range(len(gates))]
    out_terms = set(form['output']['terms']); helpers = []
    for j in out_terms:
        if j < n:
            b.cx(vals[j], target)
    if form['output']['constant']:
        b.x(target)
    for i, g in enumerate(gates):
        lw = [vals[j] for j in g['left']]; rw = [vals[j] for j in g['right']]
        h = b.alloc_qubits(1)[0] if used_later[i] else target
        wa, wb, ops = _pair_forms(b, lw, rw); b.ccx(wa, wb, h); _undo(b, ops)
        if used_later[i]:
            vals.append(h); helpers.append((h, lw, rw))
            if n + i in out_terms:
                b.cx(h, target)
        else:
            assert n + i in out_terms
            vals.append(None)
    for h, lw, rw in reversed(helpers):
        m = b.alloc_bits(1)[0]; b.hmr(h, m); b.free(h)
        wa, wb, ops = _pair_forms(b, lw, rw)
        b.push_condition(m); b.cz(wa, wb); b.pop_condition(); _undo(b, ops)
        b.free(m)


def restore_sat(d, b, token, k, outcome):
    form = _SAT[k]; v = token.v
    wires = []
    for name in form['inputs']:
        role = _ROLES[name]
        wires.append(token.u[-1] if role == 'next' else v[int(role[1:])])
    s = b.alloc_qubits(1)[0]
    _emit_sat(b, form, wires, s)
    b.push_condition(outcome); b.z(s); b.pop_condition(); b.free(outcome)
    token.history[k] = s
    initial = list(token.initial_u); initial[25 - k] = s; token.initial_u = tuple(initial)
    return s


def _kernel(b):
    if b.max_qubits >= 48:
        return sys.modules['top12_kernel']
    name = 'divider_top12_kernel_relaxed'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, _RELAXED)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def _plan(d, p):
    return d.cb.factor_polynomial(p['width'], bool(p['constant']), p['linear'], set(map(tuple, p['edges'])))


def restore(d, b, token, k, outcome):
    f = FORMULAS[k]; v = token.v
    base = [v[x[1]] if x[0] == 'v' else token.u[-1] for x in f['parents']]
    helpers, hplans, hvars = [], [], []
    for h in f['helpers']:
        # nested helpers may use earlier helpers as variables (width says how many)
        variables = base + helpers[:h['width'] - len(base)]
        p = _plan(d, h)
        g = b.alloc_qubits(1)[0]; d.cb.emit_xor(b, variables, g, p)
        helpers.append(g); hplans.append(p); hvars.append(variables)
    dplan = _plan(d, f['decoder'])
    assert sum(p.and_count for p in hplans) + dplan.and_count == f['ands'], (k, [p.and_count for p in hplans], dplan.and_count)
    s = b.alloc_qubits(1)[0]
    d.cb.emit_xor(b, base + helpers, s, dplan)
    b.push_condition(outcome); b.z(s); b.pop_condition(); b.free(outcome)
    for g, p, variables in reversed(list(zip(helpers, hplans, hvars))):
        d._erase(b, g, variables, p)
    token.history[k] = s
    initial = list(token.initial_u); initial[25 - k] = s; token.initial_u = tuple(initial)
    return s


def _feed_row(d, b, token, j):
    v = token.v; u = token.u
    low = u[0]; target = u[1:]; sign = token.history[j]; cur = token.P[23 - j] if j < 24 else None
    debt = token._debt
    carry = d._feed_carry(b, v, low, cur, sign)
    d._frame(b, sign, target); d._leading_offset(b, target, inverse=True)
    released = d.inverse_add(b, v[1:], target, debt, carry_in=carry, dirty_wires=d._dirty(token),
                             carry_lifecycle=(lambda value: d._feed_erase(b, value, v, low, cur, sign),
                                              lambda: d._feed_carry(b, v, low, cur, sign)))
    d._frame(b, sign, target)
    if not released:
        d._feed_erase(b, carry, v, low, cur, sign)
    if cur is not None: b.cx(cur, low)
    b.cx(sign, low); b.cx(v[0], low)
    token.P[24 - j] = low; token.u = target + [sign]; del token.history[j]


def cleanup_divider(d, b, token):
    original_cap = b.max_qubits
    if FORCE:
        b.set_max_qubits(FORCE)
    try:
        return _cleanup(d, b, token)
    finally:
        if FORCE:
            b.set_max_qubits(original_cap)


def _cleanup(d, b, token):
    assert b.max_qubits >= 46 and b.num_allocated_qubits == 43
    assert not token.consumed and len(token.rows) == 24
    assert sorted(token.history) == list(range(12, 25))
    token.consumed = True; v = token.v
    old_sign = token.history.pop(12); next_sign = token.history[13]
    outcome = b.alloc_bits(1)[0]; b.hmr(old_sign, outcome); b.free(old_sign)
    b.push_condition(outcome); b.z(v[11]); b.z(v[10]); b.cz(v[10], next_sign); b.pop_condition()
    b.free(outcome)
    outcomes = {}
    for k in RETIRE:
        w = token.history.pop(k); o = b.alloc_bits(1)[0]; b.hmr(w, o); b.free(w); outcomes[k] = o
    data = 42 - len(RETIRE)
    assert b.num_allocated_qubits == data
    for j, k, debt in reversed(token.rows):
        if j in outcomes:
            if j in _SAT:
                restore_sat(d, b, token, j, outcomes.pop(j))
            else:
                restore(d, b, token, j, outcomes.pop(j))
            data += 1
            assert b.num_allocated_qubits == data
        if j == 12:
            assert not token.history and not outcomes
            rebuilt = b.alloc_qubits(1)[0]
            b.cx(v[11], rebuilt); b.cx(v[10], rebuilt); b.ccx(v[10], token.u[-1], rebuilt)
            token.history[12] = rebuilt
            initial = list(token.initial_u); assert initial[13] == old_sign
            initial[13] = rebuilt; token.initial_u = tuple(initial)
            if b.max_qubits >= 47:
                result = _kernel(b).last_feed_and_initial(d, b, token, debt)
            else:
                token._debt = debt
                _feed_row(d, b, token, 12)
                assert debt.consumed and not debt.measurements
                assert tuple(token.u) == token.initial_u and not token.history
                token.P = d.cleanup_u12(b, v, token.P, token.u)
                result = list(token.P)
            assert all(x.consumed and not x.measurements for _, _, x in token.rows)
            assert b.num_allocated_qubits == 31
            return result
        u = token.u
        if j <= 24:
            token._debt = debt
            _feed_row(d, b, token, j)
        else:
            b.cx(v[0], u[0]); sign = u[0]; target = u[k + 1:]
            d._frame(b, sign, target); d._leading_offset(b, target, inverse=True)
            d.inverse_add(b, v[k + 1:], target, debt, carry_in=v[k], dirty_wires=d._dirty(token))
            d._frame(b, sign, target); token.u = u[1:] + u[:1]
        assert debt.consumed and not debt.measurements and b.num_allocated_qubits == data, (j, b.num_allocated_qubits)
    raise AssertionError('The final feed was not reached')


def apply(ctx):
    divider = ctx.old.divider
    def bound(b, token):
        return cleanup_divider(divider, b, token)
    divider.cleanup_divider = bound
