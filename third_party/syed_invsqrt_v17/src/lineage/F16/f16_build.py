# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# f16_build.py: F16 = F15 with the three 12-carry reverse-division chains re-sequenced to the optimal carry-erasure
# order (builds/t4 erasure game, w = 5 carry ancillas): 3.5 / 3.25 / 3.25 -> 3.0 / 3.0 / 3.0 conditional Toffolis.
# Each chain is regenerated from its parameters (base carry wire, operand pairs, top bit, forward-debt bits, ancilla pool)
# and checked locally against the original chain on random states (qubits + phase parity, random HMR outcomes) before it is
# spliced into a copy of kit/F15/candidate.kmx.  New classical bits are allocated above F15's maximum (b13043).
# Usage: python3.13 f16_build.py OUT.kmx
import re, sys, numpy as np
from f16_sched import solve

import os
KMX = os.environ['F15_KMX']
lines = open(KMX).read().split('\n')
if lines and lines[-1] == '': lines = lines[:-1]
# op index (kmxsim numbering: non-comment, non-blank lines, 0-based) -> line index
opline = [i for i, l in enumerate(lines) if l.split('#')[0].strip()]
ops = [lines[i].split('#')[0].strip() for i in opline]
assert len(ops) == 37252
NEXTBIT = [13044]
def newbit():
    b = NEXTBIT[0]; NEXTBIT[0] += 1; return b

POOL = ['q8', 'q34', 'q36', 'q26', 'q19']
# (chain start op, chain end op inclusive, base carry, operand pairs j=1..11, top b-wire, top target, fwd-debt bits j=1..11)
CHAINS = [
    (10736, 10961, 'q10',
     [('q11', 'q27'), ('q12', 'q9'), ('q13', 'q40'), ('q14', 'q41'), ('q15', 'q39'), ('q16', 'q38'), ('q17', 'q37'),
      ('q18', 'q42'), ('q0', 'q1'), ('q21', 'q2'), ('q29', 'q3')], 'q4', 'q5', list(range(303, 314))),
    (11043, 11285, 'q10',
     [('q11', 'q9'), ('q12', 'q40'), ('q13', 'q41'), ('q14', 'q39'), ('q15', 'q38'), ('q16', 'q37'), ('q17', 'q42'),
      ('q18', 'q1'), ('q0', 'q2'), ('q21', 'q3'), ('q29', 'q4')], 'q5', 'q6', list(range(292, 303))),
    (11370, 11612, 'q10',
     [('q11', 'q40'), ('q12', 'q41'), ('q13', 'q39'), ('q14', 'q38'), ('q15', 'q37'), ('q16', 'q42'), ('q17', 'q1'),
      ('q18', 'q2'), ('q0', 'q3'), ('q21', 'q4'), ('q29', 'q5')], 'q6', 'q27', list(range(281, 292))),
]

def gen_chain(c0, P, b12, tgt, fwd, sched):
    n = len(P) + 1                       # carries c1..c_{n-1} on ancillas, c_n in place
    out = []; pool = list(POOL)
    st = {j: 'fresh' for j in range(1, n)}
    cw = {0: c0}                         # live carry wires
    A = {j: P[j - 1][0] for j in range(1, n)}; B = {j: P[j - 1][1] for j in range(1, n)}
    def compute(j):
        C = cw[j - 1]; T = pool.pop(0)
        out.extend([f'CX {C} {A[j]}', f'CX {C} {B[j]}', f'CCX {A[j]} {B[j]} {T}', f'CX {C} {T}', f'Z {T} if b{fwd[j - 1]}'])
        st[j] = 'computed'; cw[j] = T
    def top():
        C = cw[n - 1]; out.extend([f'CCX {C} {b12} {tgt}', f'CX {C} {b12}'])
    def maj_phase(x, j, cond):
        # phase (-1)^{MAJ(x, a_j, NOT s_j)} (the value of c_j), each CZ under 'cond' (None = current block mask)
        sfx = f' if b{cond}' if cond is not None else ''
        out.extend([f'X {B[j]}', f'CZ {x} {A[j]}{sfx}', f'CZ {A[j]} {B[j]}{sfx}', f'CZ {x} {B[j]}{sfx}', f'X {B[j]}'])
    def erase(j):
        T = cw[j]
        if j + 1 < n and st[j + 1] == 'computed':
            out.extend([f'CX {T} {A[j + 1]}', f'CX {A[j + 1]} {B[j + 1]}']); st[j + 1] = 'summed'
        if st[j] == 'computed':
            C = cw[j - 1]; out.extend([f'CX {C} {A[j]}', f'CX {A[j]} {B[j]}']); st[j] = 'summed'
        r = newbit(); out.append(f'HMR {T} b{r}'); del cw[j]; pool.append(T)
        if (j - 1) in cw:
            maj_phase(cw[j - 1], j, r); return 0
        i = max(k for k in cw if k < j)
        out.append(f'PUSH_CONDITION if b{r}')
        U = {i: cw[i]}
        for k in range(i + 1, j):
            u = pool.pop(0); C = U[k - 1]
            out.extend([f'X {B[k]}', f'CX {C} {A[k]}', f'CX {C} {B[k]}', f'CCX {A[k]} {B[k]} {u}', f'CX {C} {u}'])
            U[k] = u
        maj_phase(U[j - 1], j, None)
        for k in range(j - 1, i, -1):
            u = U[k]; C = U[k - 1]
            out.extend([f'CX {C} {u}', f'HMR {u} b1', f'CZ {A[k]} {B[k]} if b1', f'CX {C} {A[k]}', f'CX {C} {B[k]}', f'X {B[k]}'])
            pool.append(u)
        out.append('POP_CONDITION')
        return j - 1 - i
    gaps = 0
    for lab in sched:
        m = re.match(r'compute c(\d+)( in place)?', lab)
        if m:
            if m.group(2): top()
            else: compute(int(m.group(1)))
            continue
        m = re.match(r'erase c(\d+)', lab)
        if m: gaps += erase(int(m.group(1))); continue
        raise ValueError(lab)
    assert not [k for k in cw if k > 0] and sorted(pool) == sorted(POOL)
    assert all(st[j] == 'summed' for j in range(1, n))
    return out, gaps

# ---------------- local equivalence check (random states, phase parity) ----------------
def qi(s): return int(s[1:])
def run_local(oplist, q0, b0, seed):
    q = q0.copy(); b = b0.copy(); n = q.shape[1]; ph = np.zeros(n, dtype=bool)
    rng = np.random.default_rng(seed); stack = []; mask = np.ones(n, dtype=bool); tof = 0.0
    for s in oplist:
        t = s.split(); m = mask
        if 'if' in t:
            i = t.index('if'); m = mask & b[qi(t[i + 1])]; t = t[:i]
        o = t[0]; a = t[1:]
        if o == 'X': q[qi(a[0])] ^= m
        elif o == 'CX': q[qi(a[1])] ^= m & q[qi(a[0])]
        elif o == 'CCX': q[qi(a[2])] ^= m & q[qi(a[0])] & q[qi(a[1])]; tof += m.mean()
        elif o == 'CCZ': ph ^= m & q[qi(a[0])] & q[qi(a[1])] & q[qi(a[2])]; tof += m.mean()
        elif o == 'CZ': ph ^= m & q[qi(a[0])] & q[qi(a[1])]
        elif o == 'Z': ph ^= m & q[qi(a[0])]
        elif o == 'NEG': ph ^= m
        elif o == 'HMR':
            r = rng.random(n) < 0.5; w = qi(a[0]); ph ^= m & r & q[w]; b[qi(a[1])] = np.where(m, r, b[qi(a[1])]); q[w] &= ~m
        elif o == 'PUSH_CONDITION': stack.append(mask); mask = m
        elif o == 'POP_CONDITION': mask = stack.pop()
        elif o == 'BIT_STORE0': b[qi(a[0])] &= ~m
        elif o == 'BIT_STORE1': b[qi(a[0])] |= m
        elif o == 'BIT_INVERT': b[qi(a[0])] ^= m
        else: raise ValueError(s)
    return q, ph, tof

def check(orig, new, N=1 << 15):
    rng = np.random.default_rng(1)
    q0 = rng.random((43, N)) < 0.5
    for w in POOL: q0[qi(w)] = False
    b0 = rng.random((NEXTBIT[0] + 8, N)) < 0.5
    qa, pa, ta = run_local(orig, q0, b0, 11); qa2, pa2, _ = run_local(orig, q0, b0, 12)
    qb, pb, tb = run_local(new, q0, b0, 13); qb2, pb2, _ = run_local(new, q0, b0, 14)
    ok = (qa == qa2).all() and (pa == pa2).all() and (qa == qb).all() and (pa == pb).all() and (qb == qb2).all() and (pb == pb2).all()
    return ok, ta, tb, bool((qa == qa2).all() and (pa == pa2).all())


# ---------------- last reverse-division step (w = 4): c0 gadget + c1..c10 + top c11 into q7 ----------------
# c'1 = c0 = q10 ^ q4 ^ q10 q4 ^ q10 q3 ^ q3 q4 ^ q4 q34 ^ q3 q34 (already on q8 when the chain starts, F15 op 15201);
# c'2..c'11 = c1..c10 on the pool {q26, q36, q19} + q8; c'12 = top: q7 ^= c11 = MAJ(c10, q29, q30), with the phase
# CZ(c11, q7) under b360 (rest of the gadget debt b968) applied before q7 is updated.
LAST = dict(cs=15244, ce=15585, test_from=15192,
            P=[('q11', 'q5'), ('q12', 'q6'), ('q13', 'q27'), ('q14', 'q9'), ('q15', 'q20'), ('q16', 'q31'), ('q17', 'q33'),
               ('q18', 'q35'), ('q0', 'q28'), ('q21', 'q32'), ('q29', 'q30')],
            fwd=list(range(171, 182)), tgt='q7', bflag=360, n=12, G=('q10', 'q4', 'q3', 'q34'),
            pool=['q26', 'q36', 'q19'], allpool=['q8', 'q26', 'q36', 'q19'], b12=None)
# transition step [14561,15081): c'1 = c0 gadget on (q10, q3, q2, q26) (F15 ops 14723-14732, on q8), c1..c11, top
# q7 ^= c11 AND q30 (b-only top, as in the 12-chains), w = 4 (q8, q19, q34, q36).  F15: 5.0 conditional Toffolis.
TRANS = dict(cs=14774, ce=15080, test_from=14723,
             P=[('q11', 'q4'), ('q12', 'q5'), ('q13', 'q6'), ('q14', 'q27'), ('q15', 'q9'), ('q16', 'q20'), ('q17', 'q31'),
                ('q18', 'q33'), ('q0', 'q35'), ('q21', 'q28'), ('q29', 'q32')],
             fwd=list(range(182, 193)), tgt='q7', bflag=None, n=13, G=('q10', 'q3', 'q2', 'q26'),
             pool=['q19', 'q34', 'q36'], allpool=['q8', 'q19', 'q34', 'q36'], b12='q30')
CUR = [LAST]
def gadget_compute(T):
    x, y, z, w = CUR[0]['G']
    return [f'CX {x} {T}', f'CX {y} {T}', f'CX {z} {T}', f'CX {z} {x}', f'CX {w} {x}', f'CX {z} {y}', f'CCX {x} {y} {T}',
            f'CX {z} {y}', f'CX {w} {x}', f'CX {z} {x}']
def gadget_fix(sfx):
    x, y, z, w = CUR[0]['G']
    return [f'Z {x}{sfx}', f'Z {y}{sfx}', f'CZ {x} {y}{sfx}', f'CZ {x} {z}{sfx}', f'CZ {y} {z}{sfx}', f'CZ {y} {w}{sfx}',
            f'CZ {z} {w}{sfx}']

def gen_last(sched, top_mode, cfg=None):
    cfg = cfg or LAST; CUR[0] = cfg
    n = cfg['n']; out = []
    pool = list(cfg['pool'])
    P = cfg['P']; fwd = cfg['fwd']; tgt = cfg['tgt']; bf = cfg['bflag']
    J = range(2, len(P) + 2)
    A = {j: P[j - 2][0] for j in J}; B = {j: P[j - 2][1] for j in J}
    F = {j: fwd[j - 2] for j in J}
    st = {j: 'fresh' for j in J}
    cw = {1: 'q8'}
    def maj_phase(x, j, cond):
        sfx = f' if b{cond}' if cond is not None else ''
        out.extend([f'X {B[j]}', f'CZ {x} {A[j]}{sfx}', f'CZ {A[j]} {B[j]}{sfx}', f'CZ {x} {B[j]}{sfx}', f'X {B[j]}'])
    def compute(j):
        C = cw[j - 1]; T = pool.pop(0)
        out.extend([f'CX {C} {A[j]}', f'CX {C} {B[j]}', f'CCX {A[j]} {B[j]} {T}', f'CX {C} {T}', f'Z {T} if b{F[j]}'])
        st[j] = 'computed'; cw[j] = T
    def top():
        C = cw[n - 1]
        if top_mode == 'b':                            # b-only top: tgt ^= c_{n-1} AND b12; b12 ^= c_{n-1}
            out.extend([f'CCX {C} {cfg["b12"]} {tgt}', f'CX {C} {cfg["b12"]}']); return
        a, b = A[n], B[n]
        if top_mode == 'slot':
            U = pool.pop(0); r = newbit()
            out.extend([f'CX {C} {a}', f'CX {C} {b}', f'CCX {a} {b} {U}', f'CX {C} {U}', f'Z {U} if b{F[n]}',
                        f'CX {C} {a}', f'CX {a} {b}', f'CZ {U} {tgt} if b{bf}', f'CX {U} {tgt}', f'HMR {U} b{r}'])
            maj_phase(C, n, r); pool.append(U)
        elif top_mode == 'plain':                      # used only under NOT b360: no CZ(c11, q7) phase needed
            out.extend([f'CX {C} {a}', f'CX {C} {b}', f'CZ {a} {b} if b{F[n]}', f'Z {C} if b{F[n]}',
                        f'CCX {a} {b} {tgt}', f'CX {C} {tgt}', f'CX {C} {a}', f'CX {a} {b}'])
        else:
            out.extend([f'CX {C} {a}', f'CX {C} {b}', f'CCZ {a} {b} {tgt} if b{bf}', f'CZ {C} {tgt} if b{bf}',
                        f'CZ {a} {b} if b{F[n]}', f'Z {C} if b{F[n]}', f'CCX {a} {b} {tgt}', f'CX {C} {tgt}',
                        f'CX {C} {a}', f'CX {a} {b}'])
        st[n] = 'summed'
    def erase(j):
        T = cw[j]
        if j + 1 < n and st[j + 1] == 'computed':
            out.extend([f'CX {T} {A[j + 1]}', f'CX {A[j + 1]} {B[j + 1]}']); st[j + 1] = 'summed'
        if j >= 2 and st[j] == 'computed':
            C = cw[j - 1]; out.extend([f'CX {C} {A[j]}', f'CX {A[j]} {B[j]}']); st[j] = 'summed'
        r = newbit(); out.append(f'HMR {T} b{r}'); del cw[j]; pool.append(T)
        if j == 1:
            out.extend(gadget_fix(f' if b{r}')); return 0
        if (j - 1) in cw:
            maj_phase(cw[j - 1], j, r); return 0
        below = [k for k in cw if k < j]; i = max(below) if below else 0
        out.append(f'PUSH_CONDITION if b{r}')
        U = {}
        if i > 0: U[i] = cw[i]
        for k in range(i + 1, j):
            u = pool.pop(0)
            if k == 1: out.extend(gadget_compute(u))
            else:
                C = U[k - 1]
                out.extend([f'X {B[k]}', f'CX {C} {A[k]}', f'CX {C} {B[k]}', f'CCX {A[k]} {B[k]} {u}', f'CX {C} {u}'])
            U[k] = u
        maj_phase(U[j - 1], j, None)
        for k in range(j - 1, i, -1):
            u = U[k]
            if k == 1: out.extend([f'HMR {u} b1'] + gadget_fix(' if b1'))
            else:
                C = U[k - 1]
                out.extend([f'CX {C} {u}', f'HMR {u} b1', f'CZ {A[k]} {B[k]} if b1', f'CX {C} {A[k]}', f'CX {C} {B[k]}', f'X {B[k]}'])
            pool.append(u)
        out.append('POP_CONDITION')
        return j - 1 - i
    debts = []
    def erase_defer(j):
        T = cw[j]
        if j + 1 < n and st[j + 1] == 'computed':
            out.extend([f'CX {T} {A[j + 1]}', f'CX {A[j + 1]} {B[j + 1]}']); st[j + 1] = 'summed'
        if j >= 2 and st[j] == 'computed':
            C = cw[j - 1]; out.extend([f'CX {C} {A[j]}', f'CX {A[j]} {B[j]}']); st[j] = 'summed'
        r = newbit(); out.append(f'HMR {T} b{r}'); del cw[j]; pool.append(T)
        return r
    def recompute(k, U):
        u = pool.pop(0)
        if k == 1: out.extend(gadget_compute(u))
        else:
            C = U[k - 1]
            out.extend([f'X {B[k]}', f'CX {C} {A[k]}', f'CX {C} {B[k]}', f'CCX {A[k]} {B[k]} {u}', f'CX {C} {u}'])
        U[k] = u
    def unrecompute(k, U):
        u = U[k]
        if k == 1: out.extend([f'HMR {u} b1'] + gadget_fix(' if b1'))
        else:
            C = U[k - 1]
            out.extend([f'CX {C} {u}', f'HMR {u} b1', f'CZ {A[k]} {B[k]} if b1', f'CX {C} {A[k]}', f'CX {C} {B[k]}', f'X {B[k]}'])
        pool.append(u); del U[k]
    def pay(b0, mine):
        # merged block: level l recomputes c_{j_{l-1}} .. c_{j_l - 1} under OR(r_l..r_k), then pays debt j_l under r_l
        assert b0 == 0 or b0 in cw
        ors = []
        for l in range(len(mine)):
            o = newbit(); ors.append(o); out.append(f'BIT_STORE0 b{o}')
            for j, r in mine[l:]: out.append(f'BIT_STORE1 b{o} if b{r}')
        U = {}
        if b0 > 0: U[b0] = cw[b0]
        lo = b0 + 1; levels = []
        for l, (j, r) in enumerate(mine):
            out.append(f'PUSH_CONDITION if b{ors[l]}')
            ks = list(range(lo, j))
            for k in ks: recompute(k, U)
            maj_phase(U[j - 1], j, r)
            levels.append(ks); lo = j
        for ks in reversed(levels):
            for k in reversed(ks): unrecompute(k, U)
            out.append('POP_CONDITION')
    gaps = 0
    for lab in sched:
        m = re.match(r'compute c(\d+)( in place)?', lab)
        if m:
            if m.group(2): top()
            else: compute(int(m.group(1)))
            continue
        m = re.match(r'erase c(\d+) defer base c(\d+)', lab)
        if m: debts.append((int(m.group(2)), int(m.group(1)), erase_defer(int(m.group(1))))); continue
        m = re.match(r'pay base c(\d+) debts', lab)
        if m:
            bb = int(m.group(1)); mine = sorted([(j, r) for b_, j, r in debts if b_ == bb])
            debts[:] = [x for x in debts if x[0] != bb]; pay(bb, mine); continue
        m = re.match(r'erase c(\d+)', lab)
        if m: gaps += erase(int(m.group(1))); continue
        raise ValueError(lab)
    assert not debts
    assert not cw and sorted(pool) == sorted(cfg['allpool']), (cw, pool)
    return out, gaps

def check_last(orig, new, N=1 << 15, zero=('q8', 'q26', 'q36', 'q19')):
    rng = np.random.default_rng(2)
    q0 = rng.random((43, N)) < 0.5
    for w in zero: q0[qi(w)] = False
    b0 = rng.random((NEXTBIT[0] + 8, N)) < 0.5
    qa, pa, ta = run_local(orig, q0, b0, 21); qa2, pa2, _ = run_local(orig, q0, b0, 22)
    qb, pb, tb = run_local(new, q0, b0, 23); qb2, pb2, _ = run_local(new, q0, b0, 24)
    self_ok = bool((qa == qa2).all() and (pa == pa2).all())
    ok = self_ok and (qa == qb).all() and (pa == pb).all() and (qb == qb2).all() and (pb == pb2).all()
    return bool(ok), ta, tb, self_ok, int((qa != qb).any(axis=1).sum()), float((pa != pb).mean())

def prefix_state(stop, N=20000, seed=5):
    """Run F15 ops[0:stop] on real inputs (x = 1..4096 + uniform), phases ignored; returns (q, b) for chain checks."""
    rng = np.random.default_rng(seed)
    xs = np.concatenate([np.arange(1, 4097), rng.integers(4097, 3133453, size=N - 4096)]).astype(np.int64)
    q = np.zeros((43, N), dtype=bool); b = np.zeros((NEXTBIT[0] + 64, N), dtype=bool)
    for i in range(22): q[i] = ((xs >> i) & 1).astype(bool)
    stack = []; mask = np.ones(N, dtype=bool)
    for s_ in ops[:stop]:
        t = s_.split(); m = mask
        if 'if' in t:
            i = t.index('if'); m = mask & b[qi(t[i + 1])]; t = t[:i]
        o = t[0]; a = t[1:]
        if o in ('APPEND_TO_REGISTER', 'REGISTER', 'INFO_TAG', 'Z', 'CZ', 'CCZ', 'NEG', 'Z_POW'): continue
        if o == 'X': q[qi(a[0])] ^= m
        elif o == 'CX': q[qi(a[1])] ^= m & q[qi(a[0])]
        elif o == 'CCX': q[qi(a[2])] ^= m & q[qi(a[0])] & q[qi(a[1])]
        elif o == 'CSWAP':
            c = m & q[qi(a[0])]; d = (q[qi(a[1])] ^ q[qi(a[2])]) & c; q[qi(a[1])] ^= d; q[qi(a[2])] ^= d
        elif o == 'SWAP':
            d = (q[qi(a[0])] ^ q[qi(a[1])]) & m; q[qi(a[0])] ^= d; q[qi(a[1])] ^= d
        elif o == 'HMR':
            r = rng.random(N) < 0.5; w = qi(a[0]); b[qi(a[1])] = np.where(m, r, b[qi(a[1])]); q[w] &= ~m
        elif o == 'R': q[qi(a[0])] &= ~m
        elif o == 'PUSH_CONDITION': stack.append(mask); mask = m
        elif o == 'POP_CONDITION': mask = stack.pop()
        elif o == 'BIT_STORE0': b[qi(a[0])] &= ~m
        elif o == 'BIT_STORE1': b[qi(a[0])] |= m
        elif o == 'BIT_INVERT': b[qi(a[0])] ^= m
        else: raise ValueError(s_)
    return q, b

def check_real(orig, new, q0, b0):
    qa, pa, ta = run_local(orig, q0, b0, 31); qa2, pa2, _ = run_local(orig, q0, b0, 32)
    qb, pb, tb = run_local(new, q0, b0, 33); qb2, pb2, _ = run_local(new, q0, b0, 34)
    self_ok = bool((qa == qa2).all() and (pa == pa2).all())
    ok = self_ok and bool((qa == qb).all() and (pa == pb).all() and (qb == qb2).all() and (pb == pb2).all())
    return ok, ta, tb, self_ok, int((qa != qb).any(axis=1).sum()), float((pa != pb).mean())

if __name__ == '__main__':
    out_path = sys.argv[1]
    d, sched = solve(12, 5)
    print(f'schedule (n=12, w=5): extra {d / 2} expected Toffolis')
    new_ops = list(ops); repl = {}
    for cs, ce, c0, P, b12, tgt, fwd in CHAINS:
        g, gaps = gen_chain(c0, P, b12, tgt, fwd, sched)
        orig = ops[cs:ce + 1]
        ok, ta, tb, self_ok = check(orig, g)
        print(f'chain [{cs},{ce}]: orig {len(orig)} ops, Toffolis {ta:.4f}; new {len(g)} ops, Toffolis {tb:.4f}; '
              f'conditional gap CCX {gaps}; original self-consistent {self_ok}; equivalent {ok}')
        assert ok
        repl[cs] = (ce, g)
    if '--last' in sys.argv:
        import f16_merge
        dA, pA = f16_merge.solve(12, 4, 1, (1,), top_slot=True)
        dB, pB = f16_merge.solve(12, 4, 1, (1,), top_slot=False)
        print(f'last step (merged-debt game, n=12 incl. c0 gadget, w=4, c0 live at start): b360 branch (free slot at top) '
              f'{dA:.4f}; NOT-b360 branch {dB:.4f}; expected overhead {(dA + dB) / 2:.4f} (F15 measured 4.375)')
        for lab in pA: print('   A', lab)
        for lab in pB: print('   B', lab)
        gA, _ = gen_last(pA, 'slot'); gB, _ = gen_last(pB, 'plain')
        nb = newbit()
        g = (['PUSH_CONDITION if b360'] + gA + ['POP_CONDITION', f'BIT_STORE1 b{nb}', f'BIT_INVERT b{nb} if b360',
             f'PUSH_CONDITION if b{nb}'] + gB + ['POP_CONDITION', f'BIT_STORE0 b{nb}'])
        gaps = -1; mode = 'branched'
        cs, ce, tf = LAST['cs'], LAST['ce'], LAST['test_from']
        ok, ta, tb, self_ok, nbadq, badph = check_last(ops[tf:ce + 1], ops[tf:cs] + g)
        print(f'last chain [{cs},{ce}] mode {mode}: orig Toffolis (from {tf}) {ta:.4f}; new {tb:.4f}; gap CCX {gaps}; '
              f'original self-consistent {self_ok}; equivalent {ok} (wires differing {nbadq}, phase mismatch {badph:.4f})')
        assert ok
        repl[cs] = (ce, g)
    if '--trans' in sys.argv:
        import f16_merge
        dT, pT = f16_merge.solve(13, 4, 1, (1,), top_slot=False)
        print(f'transition step (merged-debt game, n=13 incl. c0 gadget, w=4, c0 live at start): {dT:.4f} (F15 measured 5.0)')
        for lab in pT: print('   T', lab)
        g, _ = gen_last(pT, 'b', TRANS)
        cs, ce, tf = TRANS['cs'], TRANS['ce'], TRANS['test_from']
        ok, ta, tb, self_ok, nbadq, badph = check_last(ops[tf:ce + 1], ops[tf:cs] + g, zero=TRANS['allpool'])
        print(f'transition chain, random states: orig self-consistent {self_ok}, equivalent {ok}; checking on real states')
        q0, b0 = prefix_state(tf)
        ok, ta, tb, self_ok, nbadq, badph = check_real(ops[tf:ce + 1], ops[tf:cs] + g, q0, b0)
        print(f'transition chain [{cs},{ce}]: orig Toffolis (from {tf}) {ta:.4f}; new {tb:.4f}; '
              f'original self-consistent {self_ok}; equivalent {ok} (wires differing {nbadq}, phase mismatch {badph:.4f})')
        assert ok
        repl[cs] = (ce, g)
    # splice (op list), then write text keeping the copyright header line
    res = []; k = 0
    while k < len(ops):
        if k in repl:
            ce, g = repl[k]; res.extend(g); k = ce + 1
        else: res.append(ops[k]); k += 1
    hdr = [l for l in lines[:opline[0]]]
    open(out_path, 'w').write('\n'.join(hdr + res) + '\n')
    print('wrote', out_path, 'ops', len(res), 'new bits', 13044, '..', NEXTBIT[0] - 1)
