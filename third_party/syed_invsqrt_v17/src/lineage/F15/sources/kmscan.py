# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon,
# Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Own kickmix (.kmx) rewrite scanner core: parser, writer, ANF symbolic executor.

Semantics follow the published kickmix format/instruction documents:
  * qubits hold classical bits (no superposition is ever created);
  * the tracked phase is changed by Z/CZ/CCZ/NEG (sign) and Z_POW (angle in half turns);
  * HMR q b: b := m (fresh uniform bit), phase *= (-1)^(m*q), q := 0;
  * every instruction except PUSH/POP/metadata runs only if all pushed bits and its own
    `if` bit are ON. PUSH_CONDITION pushes the bit's current value.

Values are Boolean functions written in algebraic normal form (ANF): a polynomial is a
frozenset of monomials, a monomial is an int bitmask over variable ids (0 = constant 1).
Two ANF polynomials are equal as functions iff they are identical, so comparisons are exact.
"""
from __future__ import annotations

import re
from fractions import Fraction

ONE = frozenset([0])
ZERO = frozenset()

# --------------------------------------------------------------------------- parsing

_TOK = re.compile(r'"[^"]*"|\S+')


class Op:
    __slots__ = ('name', 'qs', 'bs', 'regs', 'exp', 'cond', 'text', 'line')

    def __init__(self, name, qs=(), bs=(), regs=(), exp=None, cond=None, text=None, line=''):
        self.name = name
        self.qs = tuple(qs)
        self.bs = tuple(bs)
        self.regs = tuple(regs)
        self.exp = exp
        self.cond = cond
        self.text = text
        self.line = line

    def __repr__(self):
        return self.line


def parse_line(line: str):
    s = line.split('#', 1)[0].strip()
    if not s:
        return None
    toks = _TOK.findall(s)
    name = toks[0]
    qs, bs, regs = [], [], []
    exp = None
    cond = None
    text = None
    i = 1
    while i < len(toks):
        t = toks[i]
        if t == 'if':
            cond = int(toks[i + 1][1:])
            i += 2
            continue
        if t[0] == 'q':
            qs.append(int(t[1:]))
        elif t[0] == 'b':
            bs.append(int(t[1:]))
        elif t[0] == 'r':
            regs.append(int(t[1:]))
        elif t[0] == '"':
            text = t
        else:
            exp = Fraction(t)
        i += 1
    return Op(name, qs, bs, regs, exp, cond, text, line=s)


def parse_kmx(path):
    ops = []
    with open(path) as f:
        for line in f:
            op = parse_line(line)
            if op is not None:
                ops.append(op)
    return ops


def write_kmx(ops, path):
    with open(path, 'w') as f:
        for op in ops:
            f.write(op.line + '\n')


def mk(name, qs=(), bs=(), cond=None):
    parts = [name] + ['q%d' % q for q in qs] + ['b%d' % b for b in bs]
    if cond is not None:
        parts += ['if', 'b%d' % cond]
    return Op(name, qs, bs, (), None, cond, None, ' '.join(parts))


TOFFOLI_LIKE = {'CCX', 'CCZ', 'CSWAP'}
META = {'REGISTER', 'APPEND_TO_REGISTER', 'INFO_TAG', 'DEBUG_PRINT'}

# --------------------------------------------------------------------------- ANF algebra


def pmul(a: frozenset, b: frozenset) -> frozenset:
    if not a or not b:
        return ZERO
    if a == ONE:
        return b
    if b == ONE:
        return a
    out = set()
    for x in a:
        for y in b:
            m = x | y
            if m in out:
                out.remove(m)
            else:
                out.add(m)
    return frozenset(out)


def pxor(a, b):
    return a ^ b


def pnot(a):
    return a ^ ONE


# --------------------------------------------------------------------------- symbolic executor


class SymState:
    """ANF symbolic state. Unknown qubits/bits get fresh variables on first read (lazy)."""

    def __init__(self, nvars_start=1, lazy=True, init_q=None, init_b=None, cut=None):
        self.next_var = nvars_start
        self.q = {} if init_q is None else dict(init_q)
        self.b = {} if init_b is None else dict(init_b)
        self.lazy = lazy
        self.stack = []  # condition polynomials
        self.sign = ZERO  # GF(2) sign polynomial (phase = (-1)^sign * exp(i pi sum zpow))
        self.zpow = {}  # poly -> Fraction (half turns, mod 2)
        self.mvars = []  # measurement variables in order
        self.var_names = {}
        self.cut = cut  # None or (max_terms, table)
        self.cut_defs = {}
        self.toffoli_cost = []  # list of condition polys of executed toffoli-like ops
        self.read_q = set()
        self.read_b = set()
        self.r_pre = []

    def fresh(self, name=None):
        v = self.next_var
        self.next_var += 1
        if name is not None:
            self.var_names[v] = name
        return frozenset([1 << v])

    def getq(self, i):
        p = self.q.get(i)
        if p is None:
            if not self.lazy:
                raise KeyError('q%d' % i)
            p = self.fresh('q%d' % i)
            self.q[i] = p
            self.read_q.add(i)
        return p

    def getb(self, i):
        p = self.b.get(i)
        if p is None:
            if not self.lazy:
                raise KeyError('b%d' % i)
            p = self.fresh('b%d' % i)
            self.b[i] = p
            self.read_b.add(i)
        return p

    def _canon(self, p):
        if self.cut is None or len(p) <= self.cut[0]:
            return p
        table = self.cut[1]
        v = table.get(p)
        if v is None:
            v = self.fresh('cut%d' % len(table))
            table[p] = v
            self.cut_defs[v] = p
        return v

    limit = None
    record_r = False
    mid = None  # optional shared {id(op): measurement variable} (couples HMRs across versions)

    def setq(self, i, p):
        if self.limit is not None and len(p) > self.limit:
            raise OverflowError('polynomial too large')
        self.q[i] = self._canon(p)

    def cond_poly(self, op):
        c = ONE
        for s in self.stack:
            c = pmul(c, s)
            if not c:
                return ZERO
        if op.cond is not None:
            c = pmul(c, self.getb(op.cond))
        return c

    def step(self, op):
        n = op.name
        if n in META:
            return
        if n == 'PUSH_CONDITION':
            self.stack.append(self.getb(op.cond))
            return
        if n == 'POP_CONDITION':
            if self.stack:
                self.stack.pop()
            return
        c = self.cond_poly(op)
        if not c:
            return
        if n == 'X':
            (t,) = op.qs
            self.setq(t, self.getq(t) ^ c)
        elif n == 'CX':
            a, t = op.qs
            self.setq(t, self.getq(t) ^ pmul(c, self.getq(a)))
        elif n == 'CCX':
            a, b, t = op.qs
            self.toffoli_cost.append(c)
            self.setq(t, self.getq(t) ^ pmul(c, pmul(self.getq(a), self.getq(b))))
        elif n == 'SWAP':
            a, b = op.qs
            d = pmul(c, self.getq(a) ^ self.getq(b))
            self.setq(a, self.getq(a) ^ d)
            self.setq(b, self.getq(b) ^ d)
        elif n == 'CSWAP':
            k, a, b = op.qs
            self.toffoli_cost.append(c)
            d = pmul(pmul(c, self.getq(k)), self.getq(a) ^ self.getq(b))
            self.setq(a, self.getq(a) ^ d)
            self.setq(b, self.getq(b) ^ d)
        elif n == 'Z':
            (a,) = op.qs
            self.sign ^= pmul(c, self.getq(a))
        elif n == 'CZ':
            a, b = op.qs
            self.sign ^= pmul(c, pmul(self.getq(a), self.getq(b)))
        elif n == 'CCZ':
            a, b, d = op.qs
            self.toffoli_cost.append(c)
            self.sign ^= pmul(c, pmul(self.getq(a), pmul(self.getq(b), self.getq(d))))
        elif n == 'NEG':
            self.sign ^= c
        elif n == 'Z_POW':
            (a,) = op.qs
            key = pmul(c, self.getq(a))
            if key:
                self.zpow[key] = (self.zpow.get(key, Fraction(0)) + op.exp) % 2
                if self.zpow[key] == 0:
                    del self.zpow[key]
        elif n == 'HMR':
            (a,) = op.qs
            (bb,) = op.bs
            if self.mid is not None:
                key = self.mid.get(id(op))
                if key is None:
                    m = self.fresh('m')
                    self.mid[id(op)] = m
                else:
                    m = key
            else:
                m = self.fresh('m')
            self.mvars.append(m)
            qa = self.getq(a)
            self.sign ^= pmul(c, pmul(m, qa))
            notc = c ^ ONE
            self.setq(a, pmul(notc, qa))
            self.b[bb] = pmul(notc, self.getb(bb)) ^ pmul(c, m)
        elif n == 'R':
            (a,) = op.qs
            qa = self.getq(a)
            if pmul(c, qa):
                if not self.record_r:
                    raise ValueError('R on a qubit that may be ON: unmodelled')
                # window mode: the reset value is recorded; both versions must reset the
                # same values in the same order (so any phase randomization is identical)
                self.r_pre.append(pmul(c, qa))
            self.setq(a, pmul(c ^ ONE, qa))
        elif n == 'BIT_INVERT':
            (bb,) = op.bs
            self.b[bb] = self.getb(bb) ^ c
        elif n == 'BIT_STORE0':
            (bb,) = op.bs
            self.b[bb] = pmul(c ^ ONE, self.getb(bb))
        elif n == 'BIT_STORE1':
            (bb,) = op.bs
            self.b[bb] = pmul(c ^ ONE, self.getb(bb)) ^ c
        else:
            raise ValueError('unknown op ' + n)

    def normalized_phase(self):
        """Fold Z_POW angle multiples of 1 half-turn into the sign polynomial."""
        sign = self.sign
        zp = {}
        for k, v in self.zpow.items():
            v = v % 2
            if v >= 1:
                sign ^= k
                v -= 1
            if v:
                zp[k] = v
        return sign, zp


def count_poly_prob(p):
    """Exact probability that ANF polynomial p (over independent uniform vars) is 1.
    Only used for small condition polynomials (conditions are products of measured bits)."""
    if not p:
        return Fraction(0)
    if p == ONE:
        return Fraction(1)
    vars_ = 0
    for m in p:
        vars_ |= m
    vs = [i for i in range(vars_.bit_length()) if vars_ >> i & 1 and i > 0]
    if len(vs) > 20:
        raise ValueError('condition too wide')
    cnt = 0
    for a in range(1 << len(vs)):
        mask = 0
        for j, v in enumerate(vs):
            if a >> j & 1:
                mask |= 1 << v
        val = 0
        for m in p:
            if m & ~mask & ~1 == 0:
                val ^= 1
        cnt += val
    return Fraction(cnt, 1 << len(vs))


# --------------------------------------------------------------------------- window equivalence


def run_window(ops, init_q=None, init_b=None, start_var=1, shared=None):
    st = SymState(nvars_start=start_var, lazy=True, init_q=init_q, init_b=init_b)
    if shared is not None:
        # share entry-variable assignment
        st.var_names = shared['names']
    for op in ops:
        st.step(op)
    return st


def window_equivalent(orig_ops, new_ops, extra_new_bits=(), entry_q=None, entry_b=None, limit=20000,
                      couple=None):
    """Exact check: for every entry state of the touched qubits/bits (free variables, or the
    given entry polynomials) and every measurement outcome, both op lists give the same final
    qubits, the same final classical bits (except bits listed in extra_new_bits, which must be
    unused fresh bits of the new list), the same sign polynomial and the same Z_POW terms.
    Returns (ok, info)."""
    qs = set()
    bs = set()
    for op in list(orig_ops) + list(new_ops):
        qs.update(op.qs)
        bs.update(op.bs)
        if op.cond is not None:
            bs.add(op.cond)
    # common entry variables
    nv = 1
    iq, ib = {}, {}
    names = {}
    for q in sorted(qs):
        if entry_q is not None and q in entry_q:
            iq[q] = entry_q[q]
        else:
            iq[q] = frozenset([1 << nv])
            names[nv] = 'q%d' % q
            nv += 1
    for b in sorted(bs):
        if entry_b is not None and b in entry_b:
            ib[b] = entry_b[b]
        else:
            ib[b] = frozenset([1 << nv])
            names[nv] = 'b%d' % b
            nv += 1
    if entry_q is not None or entry_b is not None:
        mx = 0
        for p in list(iq.values()) + list(ib.values()):
            for m in p:
                mx = max(mx, m.bit_length())
        nv = max(nv, mx + 1)
    s1 = SymState(nvars_start=nv, lazy=False, init_q=iq, init_b=ib)
    s1.limit = limit
    s1.record_r = True
    s2 = SymState(nvars_start=nv, lazy=False, init_q=iq, init_b=ib)
    s2.limit = limit
    s2.record_r = True
    if couple is not None:
        # measurement variables keyed by HMR instruction; `couple` lists (orig_op, new_op)
        # pairs that are the same uniform outcome. Variables are allocated from one counter.
        shared = {}
        s1.mid = shared
        s2.mid = shared
        for o_op, n_op in couple:
            v = frozenset([1 << nv])
            nv += 1
            shared[id(o_op)] = v
            shared[id(n_op)] = v
        s1.next_var = s2.next_var = nv
        s2.next_var = nv + 100000  # disjoint fresh ranges for uncoupled measurements
    try:
        for op in orig_ops:
            s1.step(op)
        for op in new_ops:
            s2.step(op)
    except OverflowError:
        return False, {'reason': 'too complex'}
    info = {}
    if couple is None and (len(s1.mvars) != len(s2.mvars) or s1.mvars != s2.mvars):
        return False, {'reason': 'measurement structure differs'}
    if s1.stack != s2.stack:
        return False, {'reason': 'condition stack differs'}
    if s1.r_pre != s2.r_pre:
        return False, {'reason': 'R reset values differ'}
    for q in qs:
        if s1.q[q] != s2.q[q]:
            return False, {'reason': 'qubit q%d differs' % q}
    for b in bs:
        if b in extra_new_bits:
            continue
        if s1.b[b] != s2.b[b]:
            return False, {'reason': 'bit b%d differs' % b}
    p1 = s1.normalized_phase()
    p2 = s2.normalized_phase()
    if p1[0] != p2[0]:
        return False, {'reason': 'sign polynomial differs', 'diff_terms': len(p1[0] ^ p2[0])}
    if p1[1] != p2[1]:
        return False, {'reason': 'Z_POW terms differ'}
    # expected toffoli-like counts (exact, over uniform measurement/entry bits)
    info['qubits'] = len(qs)
    info['bits'] = len(bs)
    info['meas'] = len(s1.mvars)
    info['toffoli_static_orig'] = len(s1.toffoli_cost)
    info['toffoli_static_new'] = len(s2.toffoli_cost)
    return True, info
