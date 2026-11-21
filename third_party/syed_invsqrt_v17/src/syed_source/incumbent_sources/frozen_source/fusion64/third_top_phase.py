# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Own phase identities for measuring a third high target in inverse row12.

Proposed emitters; qualification requires the unchanged whole-domain proof.
Caller supplies measurement guards, current raw roots and actual I10.
"""
from pathlib import Path
from itertools import product
import hashlib
import json

NOTICE = 'Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.'


def phase_i11(builder, v, t):
    w, a, r, z = v[8], v[10], v[9], v[11]
    for q in (z, r, w):
        builder.z(q)
    builder.cx(t, w)
    builder.cx(t, a)
    builder.cz(w, a)
    builder.cx(t, a)
    builder.cx(t, w)


def phase_main_with_carry10(builder, v, initializer10, sign, carry10):
    """Phase I12 XOR (sign XOR I11)*C11 XOR 1 using two products.

Here C11=MAJ(v11, I10 XOR 1 XOR sign, C10). One clean helper is used.
The constant-one phase is omitted. Its outer mB phase cancels the explicit
mB constant from the raw high-bit equation, exactly as in jointv1.
"""
    w, a, r, z, t, s, c = v[8], v[10], v[9], v[11], initializer10, sign, carry10
    assert len({w, a, r, z, t, s, c}) == 7
    h = builder.alloc_qubits(1)[0]
    for q in (s, z, r, w):
        builder.cx(q, h)
    builder.cx(t, w)
    builder.cx(t, a)
    builder.ccx(w, a, h)
    builder.cx(t, a)
    builder.cx(t, w)
    # h = sign XOR I11. Free part excludes its constant one.
    for q in (a, r, s):
        builder.z(q)
    for left, right in ((r, z), (r, s), (z, s)):
        builder.cz(left, right)
    for q in (r, z, t, s):
        builder.cz(h, q)
    for q in (z, c):
        builder.cx(t, q)
        builder.cx(s, q)
        builder.x(q)
    builder.ccz(h, z, c)
    for q in (c, z):
        builder.x(q)
        builder.cx(s, q)
        builder.cx(t, q)
    outcome = builder.alloc_bits(1)[0]
    builder.hmr(h, outcome)
    builder.free(h)
    builder.push_condition(outcome)
    builder.z(s)
    phase_i11(builder, v, t)
    builder.pop_condition()
    builder.free(outcome)


def phase_carry11_from_final_sum(builder, source10, final_sum9, incoming9,
                                source11, initializer10, sign):
    """Phase C11 with one CCZ and no clean owner.

Call after the one-bit inverse terminal but before its global X/frame
completion: C10=MAJ(source10, NOT final_sum9, incoming9). The caller uses
guard (old_debt11 XOR mA) AND NOT mB. No constant phase is omitted here.
"""
    a, B, c, z, t, s = source10, final_sum9, incoming9, source11, initializer10, sign
    assert len({a, B, c, z, t, s}) == 6
    for q in (z, c):
        builder.z(q)
    for left, right in ((z, t), (z, s), (z, c), (t, c), (s, c)):
        builder.cz(left, right)
    builder.cx(c, a)
    builder.x(B)
    builder.cx(c, B)
    builder.cx(t, z)
    builder.cx(s, z)
    builder.x(z)
    builder.ccz(a, B, z)
    builder.x(z)
    builder.cx(s, z)
    builder.cx(t, z)
    builder.cx(c, B)
    builder.x(B)
    builder.cx(c, a)


def majority(a, b, c):
    return (a & b) ^ (a & c) ^ (b & c)


def check():
    main_fail = direct_fail = high_fail = 0
    for w, a, r, z, t, s, c10 in product((0, 1), repeat=7):
        i11 = z ^ r ^ w ^ ((w ^ t) & (a ^ t))
        i12 = 1 ^ a ^ r ^ (r & z) ^ (i11 & (1 ^ r ^ z))
        h = s ^ i11
        c11 = majority(z, t ^ 1 ^ s, c10)
        lhs = i12 ^ (h & c11)
        rhs = 1 ^ a ^ r ^ s ^ majority(r, z, s)
        rhs ^= h & (r ^ z ^ t ^ s)
        rhs ^= h & (z ^ 1 ^ t ^ s) & (c10 ^ 1 ^ t ^ s)
        main_fail += lhs != rhs
    for a, final, c9, z, t, s in product((0, 1), repeat=6):
        b = t ^ 1 ^ s
        c10 = majority(a, 1 ^ final, c9)
        lhs = majority(z, b, c10)
        rhs = (z & b) ^ ((z ^ b) & c9)
        rhs ^= (a ^ c9) & (1 ^ final ^ c9) & (z ^ b)
        direct_fail += lhs != rhs
    for s, i10, i11, i12, c10, z, ma, mb, mc, d10, d11 in product((0, 1), repeat=11):
        c11 = majority(z, i10 ^ 1 ^ s, c10)
        raw11 = i10 ^ z ^ c10
        raw12 = 1 ^ i11 ^ c11
        raw13 = 1 ^ s ^ i12 ^ i11 ^ ((s ^ i11) & c11)
        lhs = (ma & raw12) ^ (mb & raw13) ^ (mc & raw11) ^ (d10 & c10) ^ (d11 & c11)
        rhs = ma ^ mb ^ (mb & s) ^ ((ma ^ mb) & i11)
        rhs ^= (mb & (i12 ^ ((s ^ i11) & c11))) ^ ((d11 ^ ma) & c11)
        rhs ^= ((d10 ^ mc) & c10) ^ (mc & i10) ^ (mc & z)
        high_fail += lhs != rhs
    assert main_fail == direct_fail == high_fail == 0
    record = dict(notice=NOTICE, status='ROOT_EXACT_BOOLEAN_IDENTITIES_ONLY_NOT_NATIVE_PROOF',
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        main_phase_cases=128, direct_carry_cases=64, full_high_debt_cases=2048,
        main_mismatches=main_fail, direct_carry_mismatches=direct_fail, high_debt_mismatches=high_fail,
        modelled_extra_expected_Toffoli='2',
        modelled_breakdown=dict(C10_capture_inside_mB='1/2', main_phase_inside_mB='1',
            C9_recreation_inside_mB_and_bank_outcome='1/4', q_only_carry11_phase='1/4'),
        modelled_complete_row12_scope='39/2', modelled_saving_vs_joint='1',
        owner_obligation='C9 must be measured and freed before main helper allocation; recreate it only for C10 bank HMR feedback. All other boundary debts remain due.',
        constant_obligation='Main emitter omits constant1, cancelling the explicit mB constant in the full high-debt equation. Direct-carry emitter omits no constant.',
        full_domain_all_branch_proof=False, two_native_builds=False)
    Path(__file__).with_suffix('.algebra.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    check()
