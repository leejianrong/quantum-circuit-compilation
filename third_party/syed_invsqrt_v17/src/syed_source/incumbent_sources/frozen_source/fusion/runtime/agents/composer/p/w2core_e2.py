# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""width2 COPY of the phase agent's walk8 core with one more retired root bit (v9) across the endpoint
(RETIRE_V9 = form dict from tools/minand_sat.py over named inputs; set by the wrapper patch before make_endpoint).
At entry v9 is X-measured with NO fix (deferred repayment, as v10); at exit, before the v10 rebuild, v9 is rebuilt
exactly into its own (spare, zero) wire from the SAT straight-line program and Z(v9) is applied on the stored outcome.
Original docstring: Phase-agent patch: endpoint walk8 = walk7 with deferred repayment of the v[10] retirement:
HMR at entry with NO fix; at exit v10 is rebuilt exactly (2 CCX) and Z(v10) is applied on the
stored outcome, which repays (-1)^(m*v10) exactly (trick read from the divider agent's HRET
patch). Removes the outcome-conditioned CCZ (0.5 expected).
walk7 = walk6 with the p-free decomposition (2,6,24,0,25):
no stage control uses p, so p is computed once (one CCX) just before walk step 8 for the
features, instead of being computed at entry, retired and rebuilt.
walk6 = walk5 plus root bit v[10] retired across the endpoint
(cubic identity v10 = s13^v8^v9^s14^h^(v8^s14^h)(v9^s14), h=v8*s15, measured on all inputs at
entry): HMR + Clifford fix + one outcome-conditioned CCZ (0.5 expected) at entry, rebuilt with
2 CCX into the same wire at exit; its wire is a second spare (more R2 holds; Q47 twin holds
all 25 R3/R4 edges).
walk5 = walk4 plus p retired during walk steps 0-7 (no control
there uses p; HMR + Clifford fix CZ(f1,f2)CZ(f1,f3)), recomputed with one CCX before step 8.
The extra lane holds two more path-local R2 edges (four in all).
walk4 = walk3 with the route decomposition
(0,4,24,0,25) (stage 2 path-local along the R3/R4 walk: two R2 edges held instead of one).
walk3 = walk2 (v[11] spare, R2 edge (9,11) held) plus
single-helper boundary-class feature encodings.

Measured fact: in class k = j+1 the routed slot j holds the constant-one ring position, so
a feature phase theta_j*thr_{j+1}*s_j may be realised by any quadratic E_j(f0..f3,p,s_j)
that equals thr_{j+1}*s_j on every class k != j+1 and equals 1 at k = j+1 (s_j=1 there).
Encodings (ANF checked on the 11 measured classes at build time):
  j0: (f1^f2^f3^p)(s^f0) ^ f0     1 product (was 2: thr1 + AND), 1 helper (was 2)
  j2: f0(f1^p) ^ (f2^f3)s          2 products, 1 helper (was 2)
  j6: f0 p ^ f3 s                  2 products, 1 helper (was 2)
  j1, j3, j7: affine threshold AND s (unchanged); j4, j5, j8: unchanged.
Each E_j is computed into one fresh helper with xor_polynomial (rank-minimal), rotated,
and erased with _erase_polynomial (exact Clifford repayment). With at most one feature
helper outside step 12, all 25 R3/R4 edges hold their difference.
(Idea for the boundary encodings read from Pro 2's candidate11r2 kmx; derivation and
schedule here are own work.) Replaces only divider.phase_endpoint.
"""
from fractions import Fraction

MODULUS = 1 << 50
CENTRES = (2, 6, 24, 0, 25)              # measured decomposition: same 11 class rotations, stage 2 path-local
CONTROLS = ((0, 4), (8,), (0, 2, 4, 8), (0, 1, 2), (0, 1))   # affine in f0..f3 only (no p)
THR = {1: (1, 2, 4, 8, 16, 3, 5, 9, 17), 2: (2, 4, 8, 16), 3: (4, 8, 3, 17), 4: (4, 8),
       5: (5, 17, 6, 18, 8, 16),        # (f0^f1)(f2^p)^f3^p  == [k>=5] on the 11 classes
       6: (6, 8),                        # f1 f2 ^ f3          == [k>=6] on the 11 classes
       7: (8, 17), 8: (8,), 9: (9, 10)}
E_HOLD = set(range(1, 13))
F_HOLD = set(range(13))
R2_HOLDS = {(11, 13): (0, 2), (10, 14): (0, 3), (9, 15): (1, 4), (7, 17): (3, 6), (6, 18): (4, 7),
            (5, 19): (5, 8), (1, 23): (9, 12)}   # three lanes in steps 0-7, one in 8-12
P_RETIRED_STEPS = (0, 7)
MAX_EXTRA = 7
QMAX = 48                                  # real allocation cap inside the endpoint


def _anf(fn):
    """ANF monomials (bitmasks over [f0,f1,f2,f3,p,s]) of a Boolean function of 6 bits."""
    table = [fn(*[(x >> i) & 1 for i in range(6)]) & 1 for x in range(64)]
    coeff = list(table)
    for i in range(6):
        for x in range(64):
            if x >> i & 1:
                coeff[x] ^= coeff[x ^ (1 << i)]
    terms = tuple(x for x in range(64) if coeff[x])
    assert all(bin(t).count('1') <= 2 for t in terms)
    return terms


ENC_FN = {
    0: lambda f0, f1, f2, f3, p, s: ((f1 ^ f2 ^ f3 ^ p) & (s ^ f0)) ^ f0,
    1: lambda f0, f1, f2, f3, p, s: (f1 ^ f2 ^ f3 ^ p) & s,
    2: lambda f0, f1, f2, f3, p, s: (f0 & (f1 ^ p)) ^ ((f2 ^ f3) & s),
    3: lambda f0, f1, f2, f3, p, s: (f2 ^ f3) & s,
    6: lambda f0, f1, f2, f3, p, s: (f0 & p) ^ (f3 & s),
    7: lambda f0, f1, f2, f3, p, s: f3 & s,
}
ENC = {j: _anf(fn) for j, fn in ENC_FN.items()}


def _check_domain():
    flags = {k: k for k in range(11)}
    flags[10] = 0b1010
    for j, fn in ENC_FN.items():
        for k in range(11):
            f = [(flags[k] >> i) & 1 for i in range(4)]
            p = f[1] & (f[2] ^ f[3])
            for s in ((1,) if k == j + 1 else (0, 1)):
                assert fn(*f, p, s) == (int(k >= j + 1) & s), (j, k, s)


_check_domain()


def pairs(stage):
    centre = CENTRES[stage]
    return [(i, (centre - i) % 26) for i in range(26) if i < (centre - i) % 26]


class SpareProxy:
    """Delegate to the builder; single-qubit allocations take the spare wires first."""

    def __init__(self, builder, base_count):
        self._b = builder
        self.spare = []
        self.lent = set()
        self.base = base_count
        self.extra = 0
        self.max_extra = 0

    def __getattr__(self, name):
        return getattr(self._b, name)

    def alloc_qubits(self, count):
        if count == 1 and self.spare:
            q = self.spare.pop()
            out = [q]
        else:
            out = list(self._b.alloc_qubits(count))
        self.extra += count
        self.max_extra = max(self.max_extra, self.extra)
        assert self.extra <= self.limit, ('too many extra wires', self.extra)
        assert self._b.num_allocated_qubits <= QMAX, ('endpoint width', self._b.num_allocated_qubits)
        return out

    def free(self, target):
        if self._is_qubit(target) and any(target == s for s in self.lent):
            self.spare.append(target)
            self.extra -= 1
            return
        self._b.free(target)
        if self._is_qubit(target):
            self.extra -= 1

    def _is_qubit(self, target):
        return type(target).__name__ == 'q'


V10_FROM_G1 = False   # width2: rebuild v10 from gate g1 of the v9 program (valid only for v9_form sha c9b1ab28...)
RETIRE_V9 = None   # width2: SAT form {'inputs': [role names like v8, s13], 'gates': [...], 'output': {...}}


def _pair_forms(b, SA, SB):
    """Make two distinct wires hold the XORs of the wire sets SA and SB, in place (CX conjugation, no new wire).
    Returns (wa, wb, ops); undo with _undo(b, ops)."""
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
    assert cands, 'degenerate AND: both factors equal'
    bp = cands[0]
    for w in [x for x in SB + SA + [a] if x in SBc and x != bp]:
        if (w, bp) in ops:
            continue
        b.cx(w, bp); ops.append((w, bp))
    return a, bp, ops


def _undo(b, ops):
    for c, t in reversed(ops):
        b.cx(c, t)


def _erase_helpers(b, helpers):
    for h, lw, rw in reversed(helpers):
        m = b.alloc_bits(1)[0]; b.hmr(h, m); b.free(h)
        wa, wb, ops = _pair_forms(b, lw, rw)
        b.push_condition(m); b.cz(wa, wb); b.pop_condition()
        _undo(b, ops)
        b.free(m)


def _emit_form(b, form, named, target, keep=False):
    """XOR the straight-line AND program `form` (tools/minand_sat.py schema) into the zero wire `target`.
    Factors are formed in place (CX conjugation); gates read by later gates get their own helper wire (erased at
    the end by X-measurement + CZ on the factors); gates read only by the output are computed into the target."""
    names = list(form['inputs']); n = len(names); gates = form['gates']
    vals = [named[x] for x in names]
    used_later = [any(n + i in g2['left'] or n + i in g2['right'] for g2 in gates[i + 1:]) for i in range(len(gates))]
    out_terms = set(form['output']['terms'])
    helpers = []
    for j in out_terms:
        if j < n:
            b.cx(vals[j], target)
    if form['output']['constant']:
        b.x(target)
    for i, g in enumerate(gates):
        lw = [vals[j] for j in g['left']]; rw = [vals[j] for j in g['right']]
        h = b.alloc_qubits(1)[0] if used_later[i] else target
        wa, wb, ops = _pair_forms(b, lw, rw)
        b.ccx(wa, wb, h)
        _undo(b, ops)
        if used_later[i]:
            vals.append(h); helpers.append((h, lw, rw))
            if n + i in out_terms:
                b.cx(h, target)
        else:
            assert n + i in out_terms
            vals.append(None)
    if keep:
        return vals, helpers
    _erase_helpers(b, helpers)
    return vals, []


def make_endpoint(phase07, e_hold=E_HOLD, f_hold=F_HOLD, r2_holds=R2_HOLDS, retire_v11=True, retire_v10=True):

    def raw_endpoint(real, token):
        B = phase07.BINDING
        d = B.divider
        v, u, flags = token.v, token.u, token.flags
        assert (len(v), len(u), len(flags)) == (12, 14, 4) and real.num_allocated_qubits == 43
        h12, h13, v10, v11 = token.history[12], token.history[13], v[10], v[11]
        h14, h15, v8, v9 = token.history[14], token.history[15], v[8], v[9]
        builder = SpareProxy(real, 43)
        builder.limit = MAX_EXTRA if retire_v11 else MAX_EXTRA - 1
        if retire_v11:
            m = real.alloc_bits(1)[0]
            real.hmr(v11, m)
            real.push_condition(m)
            real.z(h12)
            real.z(v10)
            real.cz(v10, h13)
            real.pop_condition()
            real.free(m)
            builder.spare.append(v11)
            builder.lent.add(v11)
        d._sigma25_frame(real, v, u)
        for q in u[:9]:
            real.cx(v[0], q)
        real.cx(v[1], u[9])
        if retire_v10:
            assert retire_v11
            m10 = real.alloc_bits(1)[0]
            real.hmr(v10, m10)               # deferred repayment: Z(v10) on m10 after the exact rebuild
            builder.spare.append(v10)
            builder.lent.add(v10)
        if RETIRE_V9 is not None:
            v9w = v[9]
            m9 = real.alloc_bits(1)[0]
            real.hmr(v9w, m9)                # width2: deferred repayment Z(v9) on m9 after the exact rebuild
            builder.spare.append(v9w)
            builder.lent.add(v9w)
        signs = {**token.history, 25: u[10], 26: u[9], 36: u[13]}
        signs.update({j: u[35 - j] for j in range(27, 36)})
        assert sorted(signs) == list(range(12, 37))
        for q in signs.values():
            real.x(q)
        one = real.alloc_qubits(1)[0]
        real.x(one)
        word = [signs[36 - i] for i in range(25)] + [one]
        assert len(set(word)) == 26 and u[11] not in word and u[12] not in word
        variables = flags + [None]               # p is created before walk step 8
        assert real.num_allocated_qubits == 44
        slots = [word[i] for i in B.slots]
        pos_slot = {B.slots[k]: k for k in range(26)}
        rotated, featured = set(), set()

        def rotate(pos):
            assert pos not in rotated
            real.z_pow(word[pos], Fraction(2 * B.angles[pos_slot[pos]], MODULUS))
            rotated.add(pos)

        def cswap(stage, i, j):
            with d._affine_control(real, variables, CONTROLS[stage]) as ctl:
                real.cswap(ctl, word[i], word[j])

        def cswap_stage(stage, plist):
            with d._affine_control(real, variables, CONTROLS[stage]) as ctl:
                for i, j in plist:
                    real.cswap(ctl, word[i], word[j])

        def hold(stage, i, j):
            a, b = word[i], word[j]
            anc = builder.alloc_qubits(1)[0]
            with d._affine_control(real, variables, CONTROLS[stage]) as ctl:
                real.cx(a, b)
                real.ccx(ctl, b, anc)
                real.cx(a, b)
            real.cx(anc, a)
            real.cx(anc, b)
            return anc

        def release(stage, i, j, anc):
            a, b = word[i], word[j]
            real.cx(anc, a)
            real.cx(anc, b)
            m = real.alloc_bits(1)[0]
            real.hmr(anc, m)
            with d._affine_control(real, variables, CONTROLS[stage]) as ctl:
                real.push_condition(m)
                real.cz(ctl, a)
                real.cz(ctl, b)
                real.pop_condition()
            real.free(m)
            builder.free(anc)

        def threshold(t):
            terms = THR[t]
            if max(x.bit_count() for x in terms) <= 1:
                return d._affine_control(real, variables, terms)
            return _quadratic(builder, real, d, variables, terms)

        def feature(j):
            assert j not in featured and 0 <= j <= 8
            featured.add(j)
            if j in ENC:
                terms = ENC[j]
                vars6 = variables + [slots[j]]
                h = builder.alloc_qubits(1)[0]
                d.xor_polynomial(real, vars6, h, terms)
                turns = Fraction(B.angles[26 + j], MODULUS) if j <= 6 else Fraction(1, 8)
                real.z_pow(h, 2 * turns)
                d._erase_polynomial(builder, h, vars6, terms)
                return
            with threshold(j + 1) as control:
                if j <= 6:
                    d._feature(builder, control, slots[j], Fraction(B.angles[26 + j], MODULUS))
                else:
                    d._feature(builder, control, slots[j], Fraction(1, 8) if j == 7 else Fraction(1, 4))

        def visit(pos):
            rotate(pos)
            k = pos_slot[pos]
            if k <= 8:
                feature(k)

        held_r2 = {}
        late2 = [pr for pr in pairs(2) if pr not in r2_holds]
        cswap_stage(0, pairs(0))
        cswap_stage(1, pairs(1))
        cswap_stage(2, late2)
        e = {k: (13 - k, 13 + k) for k in range(1, 13)}
        f = {k: (13 + k, (12 - k) % 26) for k in range(0, 13)}
        held = {}

        def e_forward(k):
            if k in e_hold:
                held[k] = hold(3, *e[k])
            else:
                cswap(3, *e[k])

        def e_undo(k):
            if k in e_hold:
                release(3, *e[k], held.pop(k))
            else:
                cswap(3, *e[k])

        def f_round_trip(k):
            i, j = f[k]
            if k in f_hold:
                anc = hold(4, i, j)
                visit(i)
                visit(j)
                release(4, i, j, anc)
            else:
                cswap(4, i, j)
                visit(i)
                visit(j)
                cswap(4, i, j)

        def r2_open(step):
            for pr, (first, last) in r2_holds.items():
                if first == step:
                    held_r2[pr] = hold(2, *pr)

        def r2_close(step):
            for pr, (first, last) in r2_holds.items():
                if last == step:
                    release(2, *pr, held_r2.pop(pr))

        r2_open(0)
        e_forward(1)
        f_round_trip(0)
        r2_close(0)
        for k in range(1, 13):
            if k == P_RETIRED_STEPS[1] + 1:
                pw = real.alloc_qubits(1)[0]
                assert real.num_allocated_qubits <= QMAX, ('endpoint width at p rebuild', real.num_allocated_qubits)
                d.xor_polynomial(real, flags, pw, (6, 10))
                variables[4] = pw
            r2_open(k)
            if k + 1 <= 12:
                e_forward(k + 1)
            f_round_trip(k)
            e_undo(k)
            r2_close(k)
        assert not held and not held_r2 and rotated == set(range(26)) and featured == set(range(9))
        real.cz(flags[1], flags[3])        # overflow_j9: Z(c) with c = f1 f3, exactly
        cswap_stage(2, late2)
        cswap_stage(1, pairs(1))
        cswap_stage(0, pairs(0))
        assert B.angles[33] == 0
        d._erase_polynomial(real, variables[4], flags, (6, 10))
        real.x(one)
        real.free(one)
        for q in signs.values():
            real.x(q)
        real.cx(v[1], u[9])
        for q in u[:9]:
            real.cx(v[0], q)
        if RETIRE_V9 is not None:
            assert v9w in builder.spare
            named = {'v%d' % i: v[i] for i in range(12)}
            named.update({'s%d' % k: token.history[k] for k in token.history})
            gvals, kept = _emit_form(real, RETIRE_V9, named, v9w, keep=V10_FROM_G1)
            real.push_condition(m9)
            real.z(v9w)
            real.pop_condition()
            real.free(m9)
            builder.spare.remove(v9w)
        if RETIRE_V9 is not None and V10_FROM_G1:
            # width2: v10 = v9 ^ g1 ^ (s13 ^ g1)(v9 ^ s14) on the full domain (g1 = gate 1 of the v9 program): 1 AND
            assert retire_v10 and v10 in builder.spare
            g1 = gvals[len(RETIRE_V9['inputs']) + 1]
            real.cx(v9w, v10); real.cx(g1, v10)
            wa, wb, ops = _pair_forms(real, [h13, g1], [v9w, h14])
            real.ccx(wa, wb, v10)
            _undo(real, ops)
            _erase_helpers(real, kept)
            real.push_condition(m10)
            real.z(v10)
            real.pop_condition()
            real.free(m10)
            builder.spare.remove(v10)
        elif retire_v10:
            assert v10 in builder.spare
            hh = real.alloc_qubits(1)[0]
            real.ccx(v8, h15, hh)                  # h = v8*s15
            for q in (h13, v8, v9, h14, hh):
                real.cx(q, v10)
            real.cx(h14, v8)
            real.cx(hh, v8)
            real.cx(h14, v9)
            real.ccx(v8, v9, v10)                   # (v8^s14^h)(v9^s14)
            real.cx(h14, v9)
            real.cx(hh, v8)
            real.cx(h14, v8)
            mm = real.alloc_bits(1)[0]
            real.hmr(hh, mm)
            real.push_condition(mm)
            real.cz(v8, h15)
            real.pop_condition()
            real.free(mm)
            real.free(hh)
            real.push_condition(m10)
            real.z(v10)
            real.pop_condition()
            real.free(m10)
            builder.spare.remove(v10)
        d._sigma25_frame(real, v, u, inverse=True)
        if retire_v11:
            assert builder.spare == [v11]
            real.cx(h12, v11)
            real.cx(v10, v11)
            real.ccx(v10, h13, v11)
        assert real.num_allocated_qubits == 43
        RESULT.update(max_extra=builder.max_extra)

    return raw_endpoint


class _quadratic:
    def __init__(self, builder, real, d, variables, terms):
        self.args = builder, real, d, variables, terms

    def __enter__(self):
        builder, real, d, variables, terms = self.args
        self.q = builder.alloc_qubits(1)[0]
        d.xor_polynomial(real, variables, self.q, terms)
        return self.q

    def __exit__(self, *exc):
        builder, real, d, variables, terms = self.args
        d._erase_polynomial(builder, self.q, variables, terms)
        return False


RESULT = {}


def apply(ctx):
    divider = ctx.phase.BINDING.divider
    assert divider is ctx.old.divider
    divider.phase_endpoint = make_endpoint(ctx.phase)
