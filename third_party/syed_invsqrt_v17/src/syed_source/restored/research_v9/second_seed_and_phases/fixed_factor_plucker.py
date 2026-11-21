# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Exact fixed-first-factor completion in a cubic quotient tensor.

For a fixed nonzero A, choose its least coordinate p and impose B_p=C_p=0.
Adding multiples of A achieves this gauge without changing A wedge B wedge C.
The linear tensor equation determines an affine space of alternating matrices
P=B wedge C.  All 4-coordinate Pluecker relations are necessary and sufficient
for P to have rank at most two.  An XOR of those relations equal to 1 is an
exact exclusion certificate, without restricting either B or C.

The quotient tensor must be formed from products before any projection.  A
negative is exact for its supplied correction span.  A positive remains a
projected witness, requiring an unprojected all-input/all-branch replay.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
from itertools import combinations
import hashlib
import json
from pathlib import Path
import time

NOTICE = ('Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. '
          'Credits: Syed Asad Ali, working with a team of AI agents '
          '(GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and '
          'Opus 5.5), with Claude Science supporting the research.')


def bits(value):
    while value:
        low = value & -value
        yield low.bit_length() - 1
        value ^= low


def xor_selected(values, mask):
    result = 0
    for i in bits(mask):
        result ^= values[i]
    return result


def affine_preimage(columns, target):
    """Return a particular coefficient vector and a complete kernel basis."""
    rows, kernel = {}, []
    for i, column in enumerate(columns):
        value, expression = column, 1 << i
        while value:
            p = value.bit_length() - 1
            if p not in rows:
                rows[p] = value, expression
                break
            other, expr = rows[p]
            value ^= other
            expression ^= expr
        else:
            kernel.append(expression)
    value, expression = target, 0
    while value:
        p = value.bit_length() - 1
        if p not in rows:
            return None, kernel, len(rows)
        other, expr = rows[p]
        value ^= other
        expression ^= expr
    assert xor_selected(columns, expression) == target
    assert all(xor_selected(columns, k) == 0 for k in kernel)
    return expression, kernel, len(rows)


def affine_forms(particular, kernel, count):
    forms = [(particular >> i) & 1 for i in range(count)]
    for j, vector in enumerate(kernel, 1):
        for i in bits(vector):
            forms[i] ^= 1 << j
    return forms


def quadratic_algebra(dimension):
    """Square-free GF(2) quadratic polynomials, represented by bit masks."""
    lookup = [[0] * (dimension + 1) for _ in range(dimension + 1)]
    for i in range(dimension + 1):
        lookup[0][i] = lookup[i][0] = lookup[i][i] = 1 << i
    offset = dimension + 1
    for i, j in combinations(range(1, dimension + 1), 2):
        lookup[i][j] = lookup[j][i] = 1 << offset
        offset += 1

    @lru_cache(maxsize=500000)
    def multiply(a, b):
        result = 0
        for i in bits(a):
            row = lookup[i]
            for j in bits(b):
                result ^= row[j]
        return result

    return lookup, multiply


def plucker_screen(size, forms, dimension):
    """Gaussian closure of every quadratic Pluecker equation, with proofs."""
    assert len(forms) == size * (size - 1) // 2
    entries = [[0] * size for _ in range(size)]
    for (i, j), form in zip(combinations(range(size), 2), forms):
        entries[i][j] = entries[j][i] = form
    _, multiply = quadratic_algebra(dimension)

    def mul(a, b):
        return multiply(*((a, b) if a <= b else (b, a)))

    rows, sources = {}, []
    tested, nonzero = 0, 0
    for i, j, k, l in combinations(range(size), 4):
        tested += 1
        original = (mul(entries[i][j], entries[k][l]) ^
                    mul(entries[i][k], entries[j][l]) ^
                    mul(entries[i][l], entries[j][k]))
        if not original:
            continue
        nonzero += 1
        value, expression = original, 0
        while value > 1:
            p = value.bit_length() - 1
            if p not in rows:
                expression ^= 1 << len(sources)
                sources.append(((i, j, k, l), original))
                rows[p] = value, expression
                break
            other, expr = rows[p]
            value ^= other
            expression ^= expr
        else:
            if value == 1:
                proof = [sources[t] for t in bits(expression)] + [((i, j, k, l), original)]
                check = 0
                for _, poly in proof:
                    check ^= poly
                assert check == 1
                return dict(status='PLUCKER_XOR_CONTRADICTION',
                            equations_tested=tested, nonzero_equations=nonzero,
                            quadratic_rank=len(rows),
                            contradiction_quadruples=[list(q) for q, _ in proof],
                            contradiction_polynomials_hex=[hex(v) for _, v in proof]), []
    linear = [v for p, (v, _) in rows.items() if p <= dimension]
    return dict(status='PLUCKER_LINEARIZED_CONSISTENT', equations_tested=tested,
                nonzero_equations=nonzero, quadratic_rank=len(rows),
                linear_consequence_rank=len(linear)), [v for v, _ in rows.values()]


def substitute_linear(forms, equations, dimension):
    """Parameterize every affine linear consequence, preserving completeness."""
    rows = {}
    for value in equations:
        if value.bit_length() > dimension + 1:
            continue
        while value > 1:
            p = value.bit_length() - 1
            if p not in rows:
                rows[p] = value
                break
            value ^= rows[p]
        assert value != 1
    if not rows:
        return forms, dimension, []
    free = [i for i in range(1, dimension + 1) if i not in rows]
    replacements = {0: 1}
    replacements.update({p: 1 << (i + 1) for i, p in enumerate(free)})
    for p in sorted(rows):
        replacements[p] = xor_selected([replacements.get(i, 0) for i in range(dimension + 1)], rows[p] ^ (1 << p))
    updated = [xor_selected([replacements[i] for i in range(dimension + 1)], form) for form in forms]
    return updated, len(free), [hex(v) for v in rows.values()]


def rank_two_factors(size, value):
    """Return B,C for a nonzero alternating rank-two matrix, else None."""
    pairs = list(combinations(range(size), 2))
    if not value:
        return 0, 0
    matrix = [0] * size
    for k in bits(value):
        i, j = pairs[k]
        matrix[i] |= 1 << j
        matrix[j] |= 1 << i
    i, j = pairs[(value & -value).bit_length() - 1]
    b, c = matrix[j], matrix[i]
    for u, v in pairs:
        if (((b >> u & 1) & (c >> v & 1)) ^
            ((b >> v & 1) & (c >> u & 1))) != (matrix[u] >> v & 1):
            return None
    return b, c


def evaluate_forms(forms, assignment):
    mask = (assignment << 1) | 1
    return sum(((form & mask).bit_count() & 1) << i for i, form in enumerate(forms))


def exhaustive_quadratics(equations, dimension):
    """Complete Gray-code evaluation of an exact necessary equation system."""
    linear = [0] * dimension
    quadratic = [[0] * dimension for _ in range(dimension)]
    value = 0
    for k, eq in enumerate(equations):
        flag = 1 << k
        if eq & 1:
            value ^= flag
        for i in range(dimension):
            if eq >> (i + 1) & 1:
                linear[i] ^= flag
        offset = dimension + 1
        for i, j in combinations(range(dimension), 2):
            if eq >> offset & 1:
                quadratic[i][j] ^= flag
                quadratic[j][i] ^= flag
            offset += 1
    derivative = list(linear)
    for t in range(1 << dimension):
        if value == 0:
            return t ^ (t >> 1), t + 1
        if t + 1 == 1 << dimension:
            break
        flip = ((t + 1) & -(t + 1)).bit_length() - 1
        value ^= derivative[flip]
        for j in range(dimension):
            derivative[j] ^= quadratic[flip][j]
    return None, 1 << dimension


def complete_bivector(size, forms, dimension, max_enumerate=24):
    stages = []
    original_forms = list(forms)
    while True:
        candidate = evaluate_forms(forms, 0)
        factor = rank_two_factors(size, candidate)
        if factor is not None:
            return dict(status='DECOMPOSABLE_WITNESS', stages=stages,
                        bivector_hex=hex(candidate), factor_masks=list(factor))
        result, equations = plucker_screen(size, forms, dimension)
        result['parameter_dimension'] = dimension
        stages.append(result)
        if result['status'] == 'PLUCKER_XOR_CONTRADICTION':
            result['affine_entry_forms_hex'] = [hex(f) for f in forms]
            return dict(status='COMPLETE_NEGATIVE_FIXED_FACTOR', stages=stages)
        updated, new_dimension, linear_equations = substitute_linear(forms, equations, dimension)
        if new_dimension < dimension:
            result['linear_substitution_equations_hex'] = linear_equations
            forms, dimension = updated, new_dimension
            continue
        if dimension > max_enumerate:
            return dict(status='OPEN_LINEARIZED_CONSISTENT', stages=stages,
                        remaining_parameter_dimension=dimension,
                        affine_entry_forms_hex=[hex(f) for f in forms],
                        equations_hex=[hex(v) for v in equations])
        assignment, count = exhaustive_quadratics(equations, dimension)
        result['exhaustive_assignments'] = count
        result['affine_entry_forms_hex'] = [hex(f) for f in forms]
        result['equations_hex'] = [hex(v) for v in equations]
        if assignment is None:
            return dict(status='COMPLETE_NEGATIVE_FIXED_FACTOR', stages=stages)
        candidate = evaluate_forms(forms, assignment)
        factor = rank_two_factors(size, candidate)
        assert factor is not None
        return dict(status='DECOMPOSABLE_WITNESS', stages=stages,
                    bivector_hex=hex(candidate), factor_masks=list(factor),
                    last_assignment=assignment)


def read_tensor(path):
    with Path(path).open() as f:
        n, words = map(int, f.readline().split())
        def coordinate(items):
            return sum(int(x) << (64 * j) for j, x in enumerate(items))
        target = coordinate(f.readline().split())
        tensor = {}
        for line in f:
            pieces = line.split()
            i, j, k = map(int, pieces[:3])
            assert len(pieces) == words + 3 and i < j < k < n
            tensor[i, j, k] = coordinate(pieces[3:])
    assert len(tensor) == n * (n - 1) * (n - 2) // 6
    return n, target, tensor


def scan_factor(n, target, tensor, first, physical, max_enumerate):
    pivot = (first & -first).bit_length() - 1
    complement = [i for i in range(n) if i != pivot]
    columns = []
    for j, k in combinations(complement, 2):
        value = 0
        for i in bits(first):
            if i != j and i != k:
                value ^= tensor[tuple(sorted((i, j, k)))]
        columns.append(value)
    particular, kernel, rank = affine_preimage(columns, target)
    report = dict(first_factor_mask=first, physical_mask=physical,
                  complement_coordinates=complement, image_rank=rank,
                  bivector_columns=len(columns), kernel_dimension=len(kernel))
    if particular is None:
        report['status'] = 'COMPLETE_NEGATIVE_LINEAR_IMAGE'
        return report
    forms = affine_forms(particular, kernel, len(columns))
    report['linear_particular_hex'] = hex(particular)
    report['linear_kernel_hex'] = [hex(k) for k in kernel]
    result = complete_bivector(n - 1, forms, len(kernel), max_enumerate)
    report.update(result)
    if result['status'] == 'DECOMPOSABLE_WITNESS':
        b, c = result['factor_masks']
        b = sum(1 << complement[i] for i in bits(b))
        c = sum(1 << complement[i] for i in bits(c))
        report['capture_factor_masks'] = [first, b, c]
        assert xor_selected(columns, int(result['bivector_hex'], 16)) == target
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tensor', type=Path)
    ap.add_argument('candidates', type=Path)
    ap.add_argument('output', type=Path)
    ap.add_argument('--physical-support', type=int, default=1)
    ap.add_argument('--max-enumerate', type=int, default=24)
    args = ap.parse_args()
    started = time.monotonic()
    args.output.mkdir(parents=True, exist_ok=False)
    n, target, tensor = read_tensor(args.tensor)
    candidates = [tuple(map(int, line.split())) for line in args.candidates.read_text().splitlines()]
    candidates = [(m, p) for m, p in candidates if p.bit_count() <= args.physical_support]
    reports = []
    for first, physical in candidates:
        result = scan_factor(n, target, tensor, first, physical, args.max_enumerate)
        result['notice'] = NOTICE
        path = args.output / f'factor_{physical}.json'
        path.write_text(json.dumps(result, indent=2) + '\n')
        reports.append({k: result[k] for k in ('first_factor_mask', 'physical_mask', 'status', 'image_rank', 'kernel_dimension')})
        print(json.dumps(dict(reports[-1], seconds=time.monotonic() - started)), flush=True)
    status = ('COMPLETE_NEGATIVE_DECLARED_FIXED_FACTOR_FAMILY'
              if all(r['status'].startswith('COMPLETE_NEGATIVE') for r in reports)
              else 'PROJECTED_WITNESS' if any(r['status'] == 'DECOMPOSABLE_WITNESS' for r in reports)
              else 'OPEN')
    report = dict(notice=NOTICE, status=status, inputs={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (args.tensor, args.candidates, Path(__file__))},
                  scope='One supplied physical factor of support at most the specified limit; the other two capture factors unrestricted in all tensor controls; exactly the correction quotient supplied by the tensor.',
                  physical_support=args.physical_support, controls=n, factors=reports,
                  qualified=False, current_measured_expected_Toffolis='11491/8',
                  positive_modelled_expected_Toffolis='11487/8',
                  seconds=time.monotonic() - started)
    (args.output / 'REPORT.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(status=status, factors=len(reports), seconds=report['seconds'])), flush=True)


if __name__ == '__main__':
    main()
