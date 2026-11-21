# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Small exact Boolean replay and GF(2) utilities for owned native circuits.

Input bits are bitsets of original input witnesses. Dictionary keys are formal
HMR monomials. Nothing here qualifies a circuit: a positive still needs the
unchanged official full-domain/all-HMR checker and a byte-identical rebuild.
"""
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import hashlib
import shlex
import numpy as np

NOTICE = ('Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: '
          'Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, '
          'Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude '
          'Science supporting the research.')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bits(value):
    while value:
        low = value & -value
        yield low.bit_length() - 1
        value ^= low


def xor(*polys):
    out = {}
    for poly in polys:
        for monomial, value in poly.items():
            out[monomial] = out.get(monomial, 0) ^ value
    return {k: v for k, v in out.items() if v}


def mul(a, b):
    out = {}
    for ka, va in a.items():
        for kb, vb in b.items():
            monomial = ka | kb
            out[monomial] = out.get(monomial, 0) ^ (va & vb)
    return {k: v for k, v in out.items() if v}


@dataclass(frozen=True)
class Op:
    kind: str
    arguments: tuple
    condition: str | None
    event: int | None
    line: int
    half_turns: Fraction | None = None


class Program:
    def __init__(self, text):
        self.operations = []
        self.registers = {}
        registers = {}
        self.wires = set()
        self.measurements = 0
        for line, literal in enumerate(text.splitlines(), 1):
            tokens = shlex.split(literal, comments=True)
            if not tokens:
                continue
            kind, *args = tokens
            if kind == 'APPEND_TO_REGISTER':
                q, register = args
                registers.setdefault(register, []).append(q)
                self.wires.add(q)
                continue
            if kind == 'REGISTER':
                register, name = args
                self.registers[name] = tuple(registers[register])
                continue
            if kind in ('INFO_TAG', 'DEBUG_PRINT'):
                continue
            condition = None
            if 'if' in args:
                where = args.index('if')
                assert len(args) == where + 2
                condition = args[-1]
                args = args[:where]
                self.wires.add(condition)
            event = None
            angle = None
            if kind == 'Z_POW':
                angle = Fraction(args[-1])
                args = args[:-1]
            if kind == 'HMR':
                event = self.measurements
                self.measurements += 1
            for q in args:
                if q.startswith(('q', 'b')) and q[1:].isdigit():
                    self.wires.add(q)
            self.operations.append(Op(kind, tuple(args), condition, event, line, angle))


def initial_state(program, xs):
    xs = np.asarray(xs, dtype=np.uint64)
    full = (1 << len(xs)) - 1
    one = {0: full}
    state = {q: {} for q in program.wires}
    state.update({'0': {}, 'False': {}, '1': one, 'True': one})
    for bit, q in enumerate(program.registers['x']):
        value = int.from_bytes(np.packbits((xs >> bit & 1).astype(np.uint8),
                                           bitorder='little').tobytes(), 'little')
        state[q] = {0: value} if value else {}
    return state, one


def advance(state, op, guard, one, formal=True):
    """Advance computational values; return binary phase and rotation read."""
    k, a = op.kind, op.arguments
    phase = {}
    rotation = None
    if not guard:
        return phase, rotation
    if k in ('X', 'BIT_INVERT'):
        state[a[0]] = xor(state[a[0]], guard)
    elif k == 'CX':
        state[a[1]] = xor(state[a[1]], mul(guard, state[a[0]]))
    elif k == 'CCX':
        state[a[2]] = xor(state[a[2]], mul(guard, mul(state[a[0]], state[a[1]])))
    elif k in ('SWAP', 'CSWAP'):
        u, v = a[-2:]
        delta = mul(guard, xor(state[u], state[v]))
        if k == 'CSWAP':
            delta = mul(delta, state[a[0]])
        state[u], state[v] = xor(state[u], delta), xor(state[v], delta)
    elif k == 'HMR':
        outcome = {1 << op.event: one[0]} if formal else {}
        phase = mul(guard, mul(outcome, state[a[0]]))
        state[a[0]] = xor(state[a[0]], mul(guard, state[a[0]]))
        state[a[1]] = xor(state[a[1]], mul(guard, xor(state[a[1]], outcome)))
    elif k in ('BIT_STORE0', 'BIT_STORE1'):
        desired = one if k == 'BIT_STORE1' else {}
        state[a[0]] = xor(state[a[0]], mul(guard, xor(state[a[0]], desired)))
    elif k in ('Z', 'CZ', 'CCZ', 'NEG'):
        value = one
        for q in a:
            value = mul(value, state[q])
        phase = mul(guard, value)
    elif k == 'Z_POW':
        rotation = (op.half_turns, mul(guard, state[a[0]]))
    elif k == 'R':
        assert not mul(guard, state[a[0]])
    else:
        raise AssertionError((k, a))
    return phase, rotation


def captures(program, requested_cuts, xs, formal=True, include_classical=False):
    state, one = initial_state(program, xs)
    stack = [one]
    requested_cuts = set(requested_cuts)
    answer = {}
    last = max(requested_cuts)
    for index in range(last + 1):
        if index in requested_cuts:
            answer[index] = {q: dict(value) for q, value in state.items()
                             if include_classical or q.startswith('q')}
        if index == last:
            break
        op = program.operations[index]
        guard = stack[-1] if op.condition is None else mul(stack[-1], state[op.condition])
        if op.kind == 'PUSH_CONDITION':
            stack.append(guard)
        elif op.kind == 'POP_CONDITION':
            assert len(stack) > 1
            stack.pop()
        else:
            advance(state, op, guard, one, formal)
    return answer


class Span:
    def __init__(self):
        self.rows = {}
        self.columns = []
        self.descriptors = []

    def reduce(self, value):
        coefficients = 0
        while value:
            p = value.bit_length() - 1
            if p not in self.rows:
                break
            row, mask = self.rows[p]
            value ^= row
            coefficients ^= mask
        return value, coefficients

    def normal(self, value):
        for p, (row, _) in sorted(self.rows.items(), reverse=True):
            if value >> p & 1:
                value ^= row
        return value

    def add(self, value, descriptor=None):
        residual, coefficients = self.reduce(value)
        if not residual:
            return False
        index = len(self.columns)
        self.rows[residual.bit_length() - 1] = (residual, coefficients ^ (1 << index))
        self.columns.append(value)
        self.descriptors.append(descriptor)
        return True

    def solve(self, value):
        residual, coefficients = self.reduce(value)
        return None if residual else coefficients

    def copy(self):
        out = Span()
        out.rows = dict(self.rows)
        out.columns = list(self.columns)
        out.descriptors = list(self.descriptors)
        return out


def comb(columns, coefficients):
    value = 0
    for i in bits(coefficients):
        value ^= columns[i]
    return value


def separating_dual(columns, target):
    space = Span()
    for column in columns:
        space.add(column)
    residual = space.normal(target)
    assert residual
    dual = 1 << (residual.bit_length() - 1)
    for p, (row, _) in sorted(space.rows.items()):
        if (dual & row).bit_count() & 1:
            dual ^= 1 << p
    assert (dual & target).bit_count() & 1
    assert all(not ((dual & column).bit_count() & 1) for column in columns)
    return dual


def affine_preimage(columns, target):
    space = Span()
    kernel = []
    original = []
    for i, value in enumerate(columns):
        residual, coefficient = space.reduce(value)
        if residual:
            translated = 1 << i
            for j in bits(coefficient):
                translated ^= original[j]
            space.rows[residual.bit_length() - 1] = (residual, 1 << len(original))
            space.columns.append(residual)
            original.append(translated)
        else:
            relation = 1 << i
            for j in bits(coefficient):
                relation ^= original[j]
            kernel.append(relation)
    residual, coefficient = space.reduce(target)
    point = None
    if not residual:
        point = 0
        for j in bits(coefficient):
            point ^= original[j]
    return point, kernel, len(original)
