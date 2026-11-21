"""Apply the owner’s Stack-4 angle fit at the F16 quotient-to-phase interface."""
from fractions import Fraction
import json
from pathlib import Path


def half_turn(value):
    value %= 2
    n = value.denominator.bit_length()-1
    if value.denominator != 1 << n:
        raise ValueError('rotation angle is outside the binary lattice')
    if not n:
        return str(value.numerator)
    s = str(value.numerator * 5**n).zfill(n+1)
    return (s[:-n]+'.'+s[-n:]).rstrip('0').rstrip('.')

def port(text, previous, fit, site=None):
    indices = {Fraction(v, 1 << 49) % 2:i for i,v in enumerate(previous['new_angles_units50'][:34])}
    flipped = set(fit['gauge']['flipped_rotation_sites'])
    precision = fit.get('phase_precision', 50)
    coeff = fit.get('angles_units', fit.get('new_angles_units50'))
    exponent = 1 << (precision-1)
    newrot = fit.get('new_rotation')
    if bool(newrot) != bool(site):
        raise ValueError('relocated rotations require an identified native predicate')
    seen, out = set(), []
    angle_t, opt_depth = 0, 0
    ops = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#')]
    for index, line in enumerate(ops):
        if site and index == site['cut']:
            if opt_depth:
                raise ValueError('relocated predicate is inside a conditioned block')
            ws = site['wires']
            wire = 'q'+str(ws[0])
            prep = [f'CX q{q} {wire}' for q in ws[1:]]
            if site['inverted']:
                prep.append('X '+wire)
            angle = half_turn(Fraction(newrot['angle_units'], exponent))
            out.extend([*prep, f'Z_POW {wire} {angle}', *prep[::-1]])
        parts = line.split()
        if parts[0] == 'PUSH_CONDITION':
            opt_depth += 1
        elif parts[0] == 'POP_CONDITION':
            opt_depth -= 1
        if parts[0] != 'Z_POW' or len(parts) != 3 or opt_depth:
            out.append(line)
            continue
        wire, old = parts[1], Fraction(parts[2]) % 2
        if old == Fraction(1,4):
            angle_t += 1
            out.extend(['X '+wire, f'Z_POW {wire} 0.25', 'X '+wire, f'Z_POW {wire} 0.5'])
        elif old in indices:
            j = indices[old]
            if j in seen:
                raise ValueError(f'angle {j} occurs twice')
            seen.add(j)
            if newrot and j in newrot['dropped']:
                continue
            angle = half_turn(Fraction(-coeff[j] if j in flipped else coeff[j], exponent))
            if j in flipped:
                out.extend(['X '+wire, f'Z_POW {wire} {angle}', 'X '+wire])
            else:
                out.append(f'Z_POW {wire} {angle}')
        else:
            out.append(line)
    if len(seen) != 34 or angle_t != 1 or opt_depth:
        raise ValueError(f'phase interface changed: {len(seen)} rotation sites, {angle_t} T site(s)')
    return '\n'.join(out)+'\n'


def optimize(text, original_fit):
    tuned = Path(__file__).with_name('stack4_angle_fit.json')
    return port(text, json.loads(Path(original_fit).read_text()), json.loads(tuned.read_text()))
