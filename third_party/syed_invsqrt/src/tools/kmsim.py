#!/usr/bin/env python3
# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Own bit-sliced full-domain simulator for kickmix text (.kmx) circuits.

Every one of the 3,133,452 official inputs is one bit position of a uint64
vector per wire, so one pass over the 36k native operations takes seconds.
HMR outcomes are drawn independently per input. Phase is not tracked here:
this tool only FINDS candidate rewrites; a rewrite counts only after the
unchanged exact50 native prover and the official verifier accept the circuit.
"""
from __future__ import annotations
import numpy as np

MAX_X = 3133452
TOFFOLI_LIKE = ('CCX', 'CCZ', 'CSWAP')


def parse(text):
    """Return (ops, registers). op = (kind, args, condition, angle, line_number)."""
    ops, registers, register_ids = [], {}, {}
    for number, line in enumerate(text.splitlines(), 1):
        tokens = line.split()
        if not tokens or tokens[0].startswith('#'):
            continue
        kind, arguments = tokens[0], tokens[1:]
        if kind in ('INFO_TAG', 'DEBUG_PRINT'):
            continue
        if kind == 'APPEND_TO_REGISTER':
            register_ids.setdefault(arguments[1], []).append(arguments[0])
            continue
        if kind == 'REGISTER':
            registers[arguments[1].strip('"')] = register_ids[arguments[0]]
            continue
        condition = None
        if 'if' in arguments:
            index = arguments.index('if')
            assert index == len(arguments) - 2, line
            condition = arguments[-1]
            arguments = arguments[:index]
        angle = None
        if kind == 'Z_POW':
            angle = arguments[-1]
            arguments = arguments[:-1]
        ops.append((kind, tuple(arguments), condition, angle, number))
    return ops, registers


def pack_bits(bits):
    """bool/uint8 vector -> little-endian uint64 words."""
    raw = np.packbits(np.asarray(bits, dtype=np.uint8), bitorder='little')
    pad = (-len(raw)) % 8
    if pad:
        raw = np.concatenate([raw, np.zeros(pad, dtype=np.uint8)])
    return raw.view('<u8').copy()


class Sim:
    """Bit-sliced execution. state[wire] is uint64[W]; absent wires are zero."""

    def __init__(self, ops, xreg, xs=None, seed=0):
        self.ops = ops
        self.xs = np.arange(1, MAX_X + 1, dtype=np.uint64) if xs is None else np.asarray(xs, dtype=np.uint64)
        self.n = len(self.xs)
        self.W = (self.n + 63) // 64
        self.ones = pack_bits(np.ones(self.n, dtype=np.uint8))
        if len(self.ones) < self.W:
            self.ones = np.concatenate([self.ones, np.zeros(self.W - len(self.ones), dtype=np.uint64)])
        self.zero = np.zeros(self.W, dtype=np.uint64)
        self.rng = np.random.default_rng(seed)
        self.state = {}
        for i, wire in enumerate(xreg):
            self.state[wire] = pack_bits((self.xs >> np.uint64(i)) & np.uint64(1))
        self.stack = [None]
        self.toffoli_executed = 0  # summed over inputs
        self.toffoli_static = 0

    def get(self, wire):
        value = self.state.get(wire)
        return self.zero if value is None else value

    def active_mask(self, condition):
        mask = self.stack[-1]
        if condition is not None:
            bit = self.get(condition)
            mask = bit if mask is None else (mask & bit)
        return mask

    def step(self, index):
        kind, a, condition, angle, _ = self.ops[index]
        if kind == 'PUSH_CONDITION':
            self.stack.append(self.active_mask(condition))
            return
        if kind == 'POP_CONDITION':
            self.stack.pop()
            return
        mask = self.active_mask(condition)
        full = mask is None
        s = self.state
        if kind in TOFFOLI_LIKE:
            self.toffoli_static += 1
            self.toffoli_executed += self.n if full else int(np.bitwise_count(mask).sum())
        if kind == 'X':
            s[a[0]] = self.get(a[0]) ^ (self.ones if full else mask)
        elif kind == 'CX':
            c = self.get(a[0])
            s[a[1]] = self.get(a[1]) ^ (c if full else (c & mask))
        elif kind == 'CCX':
            p = self.get(a[0]) & self.get(a[1])
            s[a[2]] = self.get(a[2]) ^ (p if full else (p & mask))
        elif kind == 'SWAP':
            x, y = self.get(a[0]), self.get(a[1])
            if full:
                s[a[0]], s[a[1]] = y, x
            else:
                d = (x ^ y) & mask
                s[a[0]], s[a[1]] = x ^ d, y ^ d
        elif kind == 'CSWAP':
            x, y = self.get(a[1]), self.get(a[2])
            d = (x ^ y) & self.get(a[0])
            if not full:
                d = d & mask
            s[a[1]], s[a[2]] = x ^ d, y ^ d
        elif kind in ('Z', 'CZ', 'CCZ', 'NEG', 'Z_POW'):
            pass
        elif kind == 'HMR':
            outcome = self.rng.integers(0, 1 << 64, self.W, dtype=np.uint64) & self.ones
            if full:
                s[a[0]] = self.zero
                s[a[1]] = outcome
            else:
                s[a[0]] = self.get(a[0]) & ~mask
                s[a[1]] = (self.get(a[1]) & ~mask) | (outcome & mask)
        elif kind == 'R':
            value = self.get(a[0])
            if (value if full else (value & mask)).any():
                raise AssertionError(f'Reset of nonzero {a[0]} at op {index}')
        elif kind == 'BIT_STORE0':
            s[a[0]] = self.zero if full else (self.get(a[0]) & ~mask)
        elif kind == 'BIT_STORE1':
            s[a[0]] = self.ones.copy() if full else (self.get(a[0]) | mask)
        elif kind == 'BIT_INVERT':
            s[a[0]] = self.get(a[0]) ^ (self.ones if full else mask)
        else:
            raise AssertionError(kind)

    def run(self, before=None, after=None, start=0, stop=None):
        stop = len(self.ops) if stop is None else stop
        for index in range(start, stop):
            if before is not None:
                before(index, self)
            self.step(index)
            if after is not None:
                after(index, self)
        return self

    def value(self, wires):
        """Integer value per input of a little-endian wire list (None = 0)."""
        out = np.zeros(self.n, dtype=np.uint64)
        for i, wire in enumerate(wires):
            if wire is None:
                continue
            bits = np.unpackbits(self.get(wire).view(np.uint8), bitorder='little')[:self.n]
            out |= bits.astype(np.uint64) << np.uint64(i)
        return out


def quantum_wires(ops):
    names = set()
    for kind, a, condition, angle, _ in ops:
        for w in a:
            if w.startswith('q'):
                names.add(w)
    return sorted(names, key=lambda w: int(w[1:]))


class Sampler:
    """Refinable sample of input positions for GF(2) span pre-filtering."""

    def __init__(self, sim, count=4096, seed=1):
        rng = np.random.default_rng(seed)
        picks = set(int(v) for v in rng.integers(0, sim.n, count))
        xs = sim.xs
        if len(xs) == MAX_X:  # boundary inputs of the official domain
            for i in range(22):
                for v in ((1 << i) - 1, 1 << i, (1 << i) + 1):
                    if 1 <= v <= MAX_X:
                        picks.add(v - 1)
            picks.update((0, MAX_X - 1))
        self.positions = sorted(picks)
        self._index()

    def _index(self):
        p = np.array(self.positions, dtype=np.int64)
        self.word = p >> 6
        self.bit = (p & 63).astype(np.uint64)

    def add(self, position):
        self.positions.append(int(position))
        self._index()

    def take(self, vector):
        bits = ((vector[self.word] >> self.bit) & np.uint64(1)).astype(np.uint8)
        return int.from_bytes(np.packbits(bits, bitorder='little').tobytes(), 'little')


def solve_span(vectors, target):
    """Subset mask of `vectors` (python ints) whose XOR equals target, else None."""
    basis = {}
    for index, v in enumerate(vectors):
        combo = 1 << index
        while v:
            pivot = v.bit_length() - 1
            hit = basis.get(pivot)
            if hit is None:
                basis[pivot] = (v, combo)
                break
            v ^= hit[0]
            combo ^= hit[1]
    v, combo = target, 0
    while v:
        hit = basis.get(v.bit_length() - 1)
        if hit is None:
            return None
        v ^= hit[0]
        combo ^= hit[1]
    return combo


def first_set(vector):
    words = np.flatnonzero(vector)
    if not len(words):
        return None
    w = int(words[0])
    value = int(vector[w])
    return w * 64 + ((value & -value).bit_length() - 1)


def affine_relation(sim, sampler, target, names, mask=None, max_refine=64):
    """Exact: is `target` (uint64 vector) = XOR of a subset of names (+const) on the domain?

    Returns (list_of_wire_names, constant_bit) or None. With a mask, equality is
    only required on masked inputs. Sample solve + exact check + counterexample
    refinement, so a returned relation holds on every simulated input.
    """
    def restrict(v):
        return v if mask is None else (v & mask)
    ones = sim.ones if mask is None else mask
    t_full = restrict(target)
    for _ in range(max_refine):
        vectors = [sampler.take(restrict(sim.get(w))) for w in names] + [sampler.take(ones)]
        combo = solve_span(vectors, sampler.take(t_full))
        if combo is None:
            return None
        acc = t_full.copy()
        chosen = []
        for i, w in enumerate(names):
            if combo >> i & 1:
                acc ^= restrict(sim.get(w))
                chosen.append(w)
        constant = combo >> len(names) & 1
        if constant:
            acc ^= ones
        bad = first_set(acc)
        if bad is None:
            return chosen, constant
        sampler.add(bad)
    return None
