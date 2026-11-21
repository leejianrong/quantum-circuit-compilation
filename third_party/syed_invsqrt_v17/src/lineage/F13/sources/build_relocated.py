# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Relocate one rotation on a native p62 phase walk and reproduce its jointly fitted angle gauge."""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path

import kickmix
from build_angles import decimal, NOTICE


def main():
    parser = argparse.ArgumentParser()
    for name in ('parent', 'parent_fit', 'fit', 'out'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    old = json.loads(args.parent_fit.read_text())
    fit = json.loads(args.fit.read_text())
    assert hashlib.sha256(args.parent.read_bytes()).hexdigest() == fit['parent_native_text_sha256']
    assert hashlib.sha256(args.parent_fit.read_bytes()).hexdigest() == fit['parent_fit_sha256']
    precision = old['phase_precision']
    assert precision == fit['phase_precision'] == 62
    flipped = set(old['gauge']['flipped_rotation_sites'])
    assert flipped == set(fit['gauge']['flipped_rotation_sites'])
    den = 1 << (precision - 1)
    old_angles = {Fraction(-angle if i in flipped else angle, den) % 2: i
                  for i, angle in enumerate(old['angles_units'][:-1])}
    assert len(old_angles) == 34
    angles = fit['angles_units']
    assert angles[-1] == ((1 << (precision - 3)) - sum(angles[i] for i in flipped)) % (2 * den)
    changed = fit['new_rotation']
    ops = [line.split('#', 1)[0].strip() for line in args.parent.read_text().splitlines()]
    lines = ['# ' + NOTICE]
    visited = set()
    depth = 0
    placed = False
    for index, op in enumerate(filter(None, ops)):
        if index == changed['cut']:
            assert depth == 0
            wires = changed['wires']
            target = wires[-1]
            parity = [f'CX q{w} q{target}' for w in wires[:-1]]
            if changed['invert']:
                parity.append(f'X q{target}')
            angle = decimal(Fraction(changed['angle_units'], den))
            lines.extend([*parity, f'Z_POW q{target} {angle}', *reversed(parity)])
            placed = True
        fields = op.split()
        if fields[0] == 'Z_POW' and len(fields) == 3:
            key = Fraction(fields[2]) % 2
            if key in old_angles:
                i = old_angles[key]
                assert depth == 0 and i not in visited
                visited.add(i)
                if i in changed['dropped']:
                    assert angles[i] == 0
                    continue
                angle = -angles[i] if i in flipped else angles[i]
                op = f'Z_POW {fields[1]} {decimal(Fraction(angle, den))}'
        depth += int(fields[0] == 'PUSH_CONDITION') - int(fields[0] == 'POP_CONDITION')
        lines.append(op)
    assert placed and depth == 0 and len(visited) == 34
    text = '\n'.join(lines) + '\n'
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'candidate.kmx').write_text(text)
    binary = args.out / 'invsqrt.kmb'
    kickmix.Circuit(text).to_file(str(binary), format='kmb')
    print('SHA256', hashlib.sha256(binary.read_bytes()).hexdigest(), flush=True)


if __name__ == '__main__':
    main()
