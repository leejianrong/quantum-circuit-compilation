#!/usr/bin/env python3
# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""kmx-level rewrites of Toffoli-like gates whose AND product is affine in live wires.

A rewrite record (from tools/audit_affine.py) names one gate by its text line and
gives the full-domain relation  product = XOR(relation_wires) xor relation_constant
that holds just before the gate on every reachable state where the gate is active.

  CCX a b t, t not in relation:   CX w t (each w), X t if constant.
  CCX a b t, t in relation:       t currently equals ab xor affine(L). Clear the affine
                                  part with CX/X, HMR t (kickback (-1)^(m ab)), repay
                                  with CZ a b if m, then write affine(L) back with CX/X.
  CSWAP c x y:                    CX y x ; CCX c x y ; CX y x, with the middle gate
                                  rewritten as above (x replaced by x xor y in the relation).
  CCZ a b c, product 'ab' etc.:   CZ w third (Z third when w is third), Z third if constant.

Every replacement is Clifford plus measurement. Records are checked against the
text (kind and arguments must match) and each needs a fresh classical bit at most.
The result is only a candidate: the exact50 native proof decides.
"""
import json


def _ccx(a, b, t, wires, constant, fresh_bit):
    wires = list(wires)
    if t not in wires:
        out = [f'CX {w} {t}' for w in wires]
        if constant:
            out.append(f'X {t}')
        return out, False
    rest = [w for w in wires if w != t]
    affine = [f'CX {w} {t}' for w in rest] + ([f'X {t}'] if constant else [])
    return affine + [f'HMR {t} {fresh_bit}', f'CZ {a} {b} if {fresh_bit}'] + affine, True


def apply_rewrites(text, records):
    lines = text.split('\n')
    used = set()
    for line in lines:
        for token in line.split():
            if token.startswith('b') and token[1:].isdigit():
                used.add(int(token[1:]))
    next_bit = max(used) + 1 if used else 0
    applied = []
    for record in sorted(records, key=lambda r: r['line']):
        index = record['line'] - 1
        tokens = lines[index].split()
        kind, arguments = tokens[0], tokens[1:]
        assert kind == record['kind'] and arguments == list(record['args']), (record, lines[index])
        wires, constant = list(record['relation_wires']), int(record['relation_constant'])
        fresh = f'b{next_bit}'
        if kind == 'CCX':
            a, b, t = arguments
            assert record['product'] == 'ab'
            new, used_bit = _ccx(a, b, t, wires, constant, fresh)
        elif kind == 'CSWAP':
            c, x, y = arguments
            assert record['product'] == 'c(x^y)'
            moved = set(wires)
            if x in moved:  # pre-gate x equals (x after CX y x) xor y
                moved ^= {y}
            ordered = [w for w in wires if w in moved] + sorted(moved - set(wires))
            middle, used_bit = _ccx(c, x, y, ordered, constant, fresh)
            new = [f'CX {y} {x}'] + middle + [f'CX {y} {x}']
        elif kind == 'CCZ':
            pair = record['product']
            names = dict(zip('abc', arguments))
            third = names[({'a', 'b', 'c'} - set(pair)).pop()]
            new = [(f'Z {third}' if w == third else f'CZ {w} {third}') for w in wires]
            if constant:
                new.append(f'Z {third}')
            used_bit = False
        else:
            raise AssertionError(kind)
        if used_bit:
            next_bit += 1
        lines[index] = '\n'.join(new) if new else '# removed ' + lines[index]
        applied.append(dict(line=record['line'], op=record.get('op'), old=' '.join(tokens), new=new,
                            stage=record.get('stage'), active=record.get('active', 1.0)))
    out = '\n'.join(line for line in lines if not line.startswith('# removed '))
    return out, dict(applied=len(applied), expected_toffoli_saving=sum(a['active'] for a in applied),
                     rewrites=applied)


if __name__ == '__main__':
    import argparse, sys
    from pathlib import Path
    ap = argparse.ArgumentParser()
    ap.add_argument('kmx', type=Path); ap.add_argument('records', type=Path); ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    records = json.loads(args.records.read_text())
    records = records['findings'] if isinstance(records, dict) else records
    text, report = apply_rewrites(args.kmx.read_text(), records)
    args.out.write_text(text)
    print(json.dumps({k: v for k, v in report.items() if k != 'rewrites'}))
