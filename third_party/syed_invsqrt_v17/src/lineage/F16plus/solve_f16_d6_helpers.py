# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Exact 64-state GF(2) phase-helper synthesizer for F16 lines 33471..35509 on D6 = [10, 26, 27, 35, 40, 41]."""

from __future__ import annotations
import time
import numpy as np
from pathlib import Path

D6 = [10, 26, 27, 35, 40, 41]
D7 = [10, 26, 27, 35, 39, 40, 41]


def extract_d6_truths(lines):
    z = np.arange(64, dtype=np.uint8)

    def sim_segment(start_ln: int, end_ln: int) -> int:
        state = {q: ((z >> i) & 1).copy() for i, q in enumerate(D6)}
        state[39] = np.zeros(64, dtype=np.uint8)  # check independence of q39!
        for q in [0, 7, 17, 18, 19]:
            state[q] = np.zeros(64, dtype=np.uint8)
        phase = np.zeros(64, dtype=np.uint8)
        for ln_no in range(start_ln, end_ln + 1):
            toks = lines[ln_no - 1].split()
            op = toks[0]
            if op == "CX":
                a, b = int(toks[1][1:]), int(toks[2][1:])
                state[b] ^= state[a]
            elif op == "X":
                a = int(toks[1][1:])
                state[a] ^= 1
            elif op == "CCX":
                a, b, c = int(toks[1][1:]), int(toks[2][1:]), int(toks[3][1:])
                state[c] ^= (state[a] & state[b])
            elif op == "Z":
                a = int(toks[1][1:])
                phase ^= state[a]
            elif op == "CZ":
                a, b = int(toks[1][1:]), int(toks[2][1:])
                phase ^= (state[a] & state[b])
            elif op == "NEG":
                phase ^= 1
            elif op == "HMR":
                break
        # Also verify with q39 = 1 that phase is identical!
        state1 = {q: ((z >> i) & 1).copy() for i, q in enumerate(D6)}
        state1[39] = np.ones(64, dtype=np.uint8)
        for q in [0, 7, 17, 18, 19]:
            state1[q] = np.zeros(64, dtype=np.uint8)
        phase1 = np.zeros(64, dtype=np.uint8)
        for ln_no in range(start_ln, end_ln + 1):
            toks = lines[ln_no - 1].split()
            op = toks[0]
            if op == "CX":
                a, b = int(toks[1][1:]), int(toks[2][1:])
                state1[b] ^= state1[a]
            elif op == "X":
                a = int(toks[1][1:])
                state1[a] ^= 1
            elif op == "CCX":
                a, b, c = int(toks[1][1:]), int(toks[2][1:]), int(toks[3][1:])
                state1[c] ^= (state1[a] & state1[b])
            elif op == "Z":
                a = int(toks[1][1:])
                phase1 ^= state1[a]
            elif op == "CZ":
                a, b = int(toks[1][1:]), int(toks[2][1:])
                phase1 ^= (state1[a] & state1[b])
            elif op == "NEG":
                phase1 ^= 1
            elif op == "HMR":
                break
        assert np.array_equal(phase, phase1), f"Depends on q39 in {start_ln}..{end_ln}!"
        val = 0
        for i in range(64):
            if phase[i]:
                val |= (1 << i)
        return val

    pA = sim_segment(34638, 34766)
    pB = sim_segment(34896, 34997)
    pC = sim_segment(35096, 35207)
    pD = sim_segment(35313, 35414)
    assert pB == pD and (pA ^ pB) == pC
    return pA, pB, pC


def build_basis_span(vecs: list[int]) -> list[int]:
    """Gaussian elimination basis (sorted descending by MSB) for 64-bit ints."""
    basis: list[int] = []
    for v in vecs:
        x = v
        for b in basis:
            if (x ^ b) < x:
                x ^= b
        if x:
            basis.append(x)
            basis.sort(reverse=True)
    return basis


def reduce_by(x: int, basis: list[int]) -> int:
    for b in basis:
        if (x ^ b) < x:
            x ^= b
    return x


def phase_span_of_wires(wire_truths: list[int]) -> list[int]:
    """Free phase span (constant 1, Z_i, CZ_{i,j}) on live wires with given 64-bit truth tables."""
    full = (1 << 64) - 1
    vecs = [full]
    n = len(wire_truths)
    for i in range(n):
        vecs.append(wire_truths[i])
        for j in range(i + 1, n):
            vecs.append(wire_truths[i] & wire_truths[j])
    return build_basis_span(vecs)


def all_1product_helpers(wire_truths: list[int]) -> list[tuple[int, int, int]]:
    """All distinct 1-AND helpers (L_a & L_b) modulo linear combinations of wire_truths, or exact (ma, mb, truth)?
    Wait: since Z(h) and CZ(h, w_i) are applied, adding a linear combination of wire_truths to h DOES NOT change
    the phase span of wire_truths + [h] (since (h ^ L) * w_i = h*w_i ^ L*w_i, and L*w_i is ALREADY in phase_span(wire_truths),
    and (h ^ L1)*(h' ^ L2) = h*h' ^ h*L2 ^ h'*L1 ^ L1*L2 is ALSO invariant!).
    Wait: what about adding constant 1 to L_a or L_b? (L_a ^ 1) & L_b = (L_a & L_b) ^ L_b, which differs only by linear L_b!
    So without loss of generality, h = L_a & L_b with NO constant terms in L_a, L_b, and distinct up to linear span of wire_truths!
    """
    n = len(wire_truths)
    lin = [0] * (1 << n)
    for m in range(1, 1 << n):
        lsb = m & -m
        bit = lsb.bit_length() - 1
        lin[m] = lin[m ^ lsb] ^ wire_truths[bit]

    lin_basis = build_basis_span(wire_truths)
    seen = {}
    for ma in range(1, 1 << n):
        ta = lin[ma]
        for mb in range(ma + 1, 1 << n):
            tb = lin[mb]
            prod = ta & tb
            canon = reduce_by(prod, lin_basis)
            if canon and canon not in seen:
                seen[canon] = (ma, mb, prod)
    return list(seen.values())


def main():
    t0 = time.time()
    pA, pB, pC = extract_d6_truths()
    print(f"Extracted D6 64-bit truths: pA=0x{pA:016x}, pB=0x{pB:016x}, pC=0x{pC:016x}")

    raw = [0] * 6
    for i in range(6):
        v = 0
        for z in range(64):
            if (z >> i) & 1:
                v |= (1 << z)
        raw[i] = v

    # h0 at L33486: q26 & (q10 ^ q27 ^ q41) -> D6 indices: 10->0, 26->1, 27->2, 35->3, 40->4, 41->5
    h0 = raw[1] & (raw[0] ^ raw[2] ^ raw[5])
    # h1 at L34460: (q35 ^ q40) & (q26 ^ q27 ^ q41) -> (3 ^ 4) & (1 ^ 2 ^ 5)
    h1 = (raw[3] ^ raw[4]) & (raw[1] ^ raw[2] ^ raw[5])
    print(f"h0 (L33486 q7)  = 0x{h0:016x}")
    print(f"h1 (L34460 q18) = 0x{h1:016x}")

    # 1. Check minimum helpers (1 or 2, allowing cascade!) for pA, pB, pC from scratch on D6:
    base_span = phase_span_of_wires(raw)
    print(f"Base D6 free phase span dim: {len(base_span)} / 64")
    cands1 = all_1product_helpers(raw)
    print(f"Unique 1-AND helpers on D6: {len(cands1)} ({time.time()-t0:.2f}s)")

    for name, target in [("pA", pA), ("pB", pB), ("pC", pC)]:
        hits1 = [c for c in cands1 if reduce_by(target, phase_span_of_wires(raw + [c[2]])) == 0]
        print(f"  {name} with 1 helper: {len(hits1)} hits")

    # Check 2 helpers (both parallel and cascade!) for pA, pB, pC:
    # Fast check: for a fixed first helper g1, wires7 = raw + [g1].
    # Any 2nd helper g2 (even cascade using g1!) adds Z(g2) and CZ(g2, w) for w in wires7:
    # wait: g2 = L_a(wires7) & L_b(wires7), and the phase terms using g2 are L_c(wires7) & g2 (plus g2 = 1 & g2)!
    # Notice L_c(wires7) & L_a(wires7) & L_b(wires7) is a SINGLE CUBIC PRODUCT on wires7, EXCEPT if CZ(g2, w) has multiple edges?
    # Wait: sum_i (w_i & g2) = (sum_i w_i) & g2 = L_c(wires7) & L_a(wires7) & L_b(wires7)!!
    # WAIT A SECOND! Because g2 is the LAST helper (not multiplied by any h3), EVERY combination of Z(g2) and CZ(g2, w)
    # for w in wires7 collapses to (c0 ^ L_c(wires7)) * g2 = L_tilde(wires7) * L_a(wires7) * L_b(wires7)!!
    # Let's verify that identity! Over {0,1}, x ^ y == (x + y) mod 2 ONLY IN F_2!
    # WAIT NO!! Phase gates Z and CZ add in Z_2 ONLY WHEN exponents are pi (i.e. (-1)^{...})!!
    # YES!! Z, CZ, NEG ALL HAVE EXPONENT pi ((-1)^f)!! IN (-1)^f, PHASE ADDITION IS EXACTLY XOR IN F_2!!
    # WAIT A SECOND!! CHECK THAT!!
    # (-1)^{g2 & w_1} * (-1)^{g2 & w_2} == (-1)^{g2 & (w_1 ^ w_2)}!!
    # YES!! BECAUSE ALL GATES IN 33471..35509 ARE Z, CZ, NEG, CCZ (SIGN GATES (-1)^f, EXPONENT MOD 2)!!
    # Let's double check! Are there ANY S or T gates in 33471..35509?! ZERO! ONLY Z, CZ, NEG, CCX, CCZ, CX, X, HMR!
    # Therefore, a final helper g_last = L_a & L_b followed by Z/CZ on (wires + [g_last]) contributes
    # (-1)^{g_last & L_c} == (-1)^{L_a & L_b & L_c}, which is IDENTICAL TO A SINGLE AFFINE CCZ(L_a, L_b, L_c)!!

    # Let's check 2-helper solutions for pA, pB, pC, AND for pB given h0 (q7), AND given (h0, h1)!
    def count_2helper_solutions(start_wires: list[int], target: int, label: str, max_hits: int = 5):
        # Need 2 extra helpers g1, g2 on start_wires:
        # Wait: g1 is added to start_wires -> wires1 = start_wires + [g1].
        # Then g2 (last helper, or affine CCZ!) adds ONE product L_a(wires1) & L_b(wires1) & L_c(wires1) modulo phase_span(wires1)!
        # Let's test if target (reduced mod phase_span(wires1)) is a product of 2 or 3 affine forms on wires1!
        # Even simpler: enumerate g1 in all_1product_helpers(start_wires), compute r = reduce_by(target, phase_span_of_wires(wires1)),
        # and check if r == 0 (1 helper!) or if r is spanned by g2 & L_c for some g2 in all_1product_helpers(wires1)!
        t_start = time.time()
        c1_list = all_1product_helpers(start_wires)
        hits_1 = []
        for ma, mb, g1 in c1_list:
            sp1 = phase_span_of_wires(start_wires + [g1])
            if reduce_by(target, sp1) == 0:
                hits_1.append((ma, mb, g1))
        if hits_1:
            print(f"  [{label}] 1-EXTRA-HELPER HITS: {len(hits_1)}! ({time.time()-t_start:.2f}s)")
            return hits_1

        # To check if r is of the form reduce_by(L_a & L_b & L_c, sp1) (where L_a, L_b, L_c can have constant 1 -> wait:
        # (L_a^1)&L_b&L_c = L_a&L_b&L_c ^ L_b&L_c, and L_b&L_c IS ALREADY IN sp1!!
        # SO WITHOUT LOSS OF GENERALITY, L_a, L_b, L_c ARE PURE LINEAR FORMS (NO CONSTANT 1) ON wires1!!)
        hits_2 = []
        n1 = len(start_wires) + 1
        for idx1, (ma, mb, g1) in enumerate(c1_list):
            wires1 = start_wires + [g1]
            sp1 = phase_span_of_wires(wires1)
            r = reduce_by(target, sp1)
            # Precompute all linear forms on wires1
            lin1 = [0] * (1 << n1)
            for m in range(1, 1 << n1):
                lsb = m & -m
                lin1[m] = lin1[m ^ lsb] ^ wires1[lsb.bit_length() - 1]
            # Wait: checking all triples (m1, m2, m3) on n1=7 (127^3/6 = 340k) would take slow loops if done 650 times,
            # EXCEPT: if r = reduce_by(L_1 & L_2 & L_3, sp1), notice on wires1 (7 or 8 vars):
            # What is the algebraic degree / rank test? Or even faster: precompute all 2-products P_{a,b} = lin1[a] & lin1[b]
            # Wait: instead of 650 * 340k in Python, do it in numpy uint64!
            lin_arr = np.array(lin1[1:], dtype=np.uint64)  # length 2^n1 - 1 (127 or 255)
            # Wait: for a fixed m1, r must agree with 0 mod sp1? No, sp1 kills all deg<=2 on wires1!
            # Wait: in the quotient V / sp1:
            # For n1=7 (start_wires=6 + g1): wires1 has 6 raw vars + 1 quadratic var g1(x).
            # Let's project lin_arr & lin_arr & lin_arr? No: if g2 = L_a & L_b and we apply Z/CZ, it's L_a & L_b & L_c.
            # How many basis vectors are OUTSIDE sp1? 64 - len(sp1)!
            # We can represent reduction mod sp1 as a linear map M : GF(2)^64 -> GF(2)^k (k = 64 - len(sp1))!
            # Wait: even simpler, only test if needed! Let's first test start_wires = raw + [h0] and raw + [h0, h1] first!
            if len(start_wires) >= 7:
                # Only do fast vectorized triple check when testing h0 / (h0, h1), or sample/full C-speed numpy!
                pass
        print(f"  [{label}] 1-extra-helper hits = 0 (checked {len(c1_list)} candidates in {time.time()-t_start:.2f}s)")
        return hits_2

    count_2helper_solutions(raw + [h0], pB, "pB given h0 (1 extra helper?)")
    count_2helper_solutions(raw + [h0, h1], pB, "pB given h0 + h1 (1 extra helper -> total 1 extra on prob 1/8!)")

    # Now do EXACT vectorized 1-AFFINE-CCZ (= 1 extra helper!) AND 2-AFFINE-CCZ (= 2 extra helpers!) check!
    def check_k_cubic_products(start_wires: list[int], target: int, label: str):
        t_s = time.time()
        sp = phase_span_of_wires(start_wires)
        rem = reduce_by(target, sp)
        if rem == 0:
            print(f"  [{label}] 0 extra products needed!")
            return
        n = len(start_wires)
        lin = [0] * (1 << n)
        for m in range(1, 1 << n):
            lsb = m & -m
            lin[m] = lin[m ^ lsb] ^ start_wires[lsb.bit_length() - 1]
        # Generate all reduced cubic products reduce_by(lin[a] & lin[b] & lin[c], sp)
        # Notice: to enumerate quickly in Python/NumPy:
        # First collect unique quadratic products mod linear span:
        quads = all_1product_helpers(start_wires)
        print(f"  [{label}] dim(sp)={len(sp)}, #unique_quads={len(quads)}, rem=0x{rem:016x}")
        cubics = {}
        for ma, mb, qv in quads:
            for mc in range(1, 1 << n):
                cv = qv & lin[mc]
                rc = reduce_by(cv, sp)
                if rc == rem:
                    print(f"  *** JACKPOT [{label}] SOLVED WITH 1 EXTRA CUBIC/HELPER: ({ma}, {mb}) & {mc}! ({time.time()-t_s:.2f}s) ***")
                    return (1, (ma, mb, mc))
                if rc and rc not in cubics:
                    cubics[rc] = (ma, mb, mc)
        print(f"  [{label}] #unique_cubics_mod_sp={len(cubics)} (1-cubic failed in {time.time()-t_s:.2f}s); checking 2-cubic XOR...")
        for rc, info1 in cubics.items():
            need = rem ^ rc
            if need in cubics:
                info2 = cubics[need]
                print(f"  *** JACKPOT [{label}] SOLVED WITH 2 EXTRA NON-CASCADE CUBICS/HELPERS: {info1} + {info2}! ({time.time()-t_s:.2f}s) ***")
                return (2, (info1, info2))
        print(f"  [{label}] 2 non-cascade cubics failed ({time.time()-t_s:.2f}s)")
        return None

    print("\n--- Testing 1 or 2 non-cascade helpers/CCZs ---")
    check_k_cubic_products(raw, pA, "pA from D6")
    check_k_cubic_products(raw, pB, "pB from D6")
    check_k_cubic_products(raw, pC, "pC from D6")
    check_k_cubic_products(raw + [h0], pB, "pB from D6 + h0(q7)")
    check_k_cubic_products(raw + [h1], pB, "pB from D6 + h1(q18)")
    check_k_cubic_products(raw + [h0, h1], pB, "pB from D6 + h0(q7) + h1(q18)")


