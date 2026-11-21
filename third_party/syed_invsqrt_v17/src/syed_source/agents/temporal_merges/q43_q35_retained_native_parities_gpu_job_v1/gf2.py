# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Owned exact GF(2) spans, coefficient fibers, and literal characters."""
from itertools import combinations

NOTICE = ('Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: '
    'Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, '
    'Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude '
    'Science supporting the research.')

def bits(v):
    while v:
        z = v & -v
        yield z.bit_length()-1
        v ^= z


def combine(columns, mask):
    v = 0
    for j in bits(mask):
        v ^= columns[j]
    return v


class Span:
    def __init__(self):
        self.rows = {}
        self.columns = []

    def reduce(self, value):
        coefficients = 0
        while value:
            p = value.bit_length()-1
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

    def add(self, value):
        residual, coefficients = self.reduce(value)
        if not residual:
            return False
        self.rows[residual.bit_length()-1] = (residual, coefficients ^ (1 << len(self.columns)))
        self.columns.append(value)
        return True

    def solve(self, value):
        residual, coefficients = self.reduce(value)
        return None if residual else coefficients


def affine_preimage(columns, target):
    space = Span()
    original = []
    kernel = []
    for i, value in enumerate(columns):
        residual, coefficient = space.reduce(value)
        translated = (1 << i) ^ combine(original, coefficient)
        if residual:
            space.rows[residual.bit_length()-1] = (residual, 1 << len(original))
            space.columns.append(residual)
            original.append(translated)
        else:
            kernel.append(translated)
    residual, coefficient = space.reduce(target)
    return (None if residual else combine(original, coefficient)), kernel, len(original)


def separating_dual(columns, target):
    s = Span()
    for v in columns:
        s.add(v)
    residual = s.normal(target)
    assert residual
    dual = 1 << (residual.bit_length()-1)
    for p, (row, _) in sorted(s.rows.items()):
        if (dual & row).bit_count() & 1:
            dual ^= 1 << p
    assert (dual & target).bit_count() & 1
    assert all(not ((dual & v).bit_count() & 1) for v in columns)
    return dual


def functional_character(space, coefficient_mask, annihilate):
    character = 0
    for p, (row, tag) in sorted(space.rows.items()):
        if ((character & row).bit_count() & 1) != ((coefficient_mask & tag).bit_count() & 1):
            character ^= 1 << p
    for p, (row, _) in sorted(annihilate.rows.items()):
        if (character & row).bit_count() & 1:
            character ^= 1 << p
    assert all(((character & v).bit_count() & 1)==(coefficient_mask >> i & 1)
        for i,v in enumerate(space.columns))
    assert all(not ((character & v).bit_count() & 1) for v in annihilate.columns)
    return character


