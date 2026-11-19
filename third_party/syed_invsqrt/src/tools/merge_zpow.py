#!/usr/bin/env python3
# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Merge Z_POW gates that act on the same Boolean feature.

A Z_POW of angle a on a wire holding the bit f(x) contributes a*f(x) half-turns. Two unconditioned
Z_POW gates whose wires hold the SAME function of the input (checked on all 3,133,452 official
inputs, at the moment each gate acts) can be replaced by one gate with the summed angle, wherever
they sit in the circuit. A T-type angle folded into a generic rotation removes a T gate; two
T-type angles on one feature become a free Clifford angle. (Idea first proved on one adjacent
pair by the normroot audit agent; this pass finds every such group by full-domain equality.)

The phase function is unchanged, so the exact50 proof against the frozen oracle still applies.
Usage: merge_zpow.py IN.kmx --out OUT.kmx
"""
import argparse, hashlib, json, sys
from fractions import Fraction
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import kmsim


def dyadic(fr):
    """Exact decimal string of a non-negative dyadic rational."""
    fr = fr % 2
    if fr == 0:
        return '0'
    num, den = fr.numerator, fr.denominator
    assert den & (den - 1) == 0
    k = den.bit_length() - 1
    digits = str(num * 5 ** k).rjust(k + 1, '0')
    whole, frac = digits[:-k] if k else digits, digits[-k:] if k else ''
    frac = frac.rstrip('0')
    return whole + ('.' + frac if frac else '')


def kind_of(angle):
    if angle % Fraction(1, 2) == 0:
        return 'clifford'
    if angle % Fraction(1, 4) == 0:
        return 't'
    return 'rotation'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('kmx', type=Path); ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    text = args.kmx.read_text()
    ops, registers = kmsim.parse(text)
    sim = kmsim.Sim(ops, registers['x'])
    gates = []

    def before(index, s):
        kind, a, cond, angle, line = ops[index]
        if kind == 'Z_POW' and cond is None and len(s.stack) == 1:
            vector = s.get(a[0])
            gates.append(dict(op=index, line=line, wire=a[0], angle=Fraction(angle),
                              key=hashlib.sha256(vector.tobytes()).hexdigest(), nonzero=bool(vector.any())))
    sim.run(before=before)
    groups = {}
    for g in gates:
        groups.setdefault(g['key'], []).append(g)
    lines = text.split('\n')
    delete, report = set(), []
    for key, members in groups.items():
        if len(members) < 2 or not members[0]['nonzero']:
            continue
        if all(kind_of(m['angle']) == 'clifford' for m in members):
            continue
        total = sum(m['angle'] for m in members) % 2
        keep = members[0]
        before_kinds = [kind_of(m['angle']) for m in members]
        if total == 0:
            delete.update(m['line'] - 1 for m in members)
        else:
            lines[keep['line'] - 1] = f"Z_POW {keep['wire']} {dyadic(total)}"
            delete.update(m['line'] - 1 for m in members[1:])
        report.append(dict(lines=[m['line'] for m in members], wires=[m['wire'] for m in members],
                           angles=[str(m['angle']) for m in members], before=before_kinds,
                           merged=str(total), after=kind_of(total) if total else 'removed'))
    out = '\n'.join(line for i, line in enumerate(lines) if i not in delete)
    args.out.write_text(out)
    count = lambda ks, name: sum(1 for k in ks if k == name)
    all_before = [kind_of(g['angle']) for g in gates]
    summary = dict(z_pow_gates=len(gates), groups_merged=len(report),
                   t_before=count(all_before, 't'), rotations_before=count(all_before, 'rotation'), merges=report)
    args.out.with_suffix('.zpow.json').write_text(json.dumps(summary, indent=1) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'merges'}),
          [(r['before'], r['after']) for r in report])


if __name__ == '__main__':
    main()
