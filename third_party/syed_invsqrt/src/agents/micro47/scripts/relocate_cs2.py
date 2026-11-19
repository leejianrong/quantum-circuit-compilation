#!/usr/bin/env python3
# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""micro47 PHASE RELOCATION v2 of the endpoint's small-x CS correction: Clifford-only replacement (text pass).

The endpoint block (walk8 family)
    Z_POW qR (0.25 + e) ; CX q23 q22 ; CCX q22 q25 qT ; CX q23 q22 ; Z_POW qT 0.25 ; CX qT qR ; Z_POW qR 1.75 ;
    CX qT qR ; HMR qT b ; if b: CZ q22 q25, CZ q23 q25
applies e*f45 plus i^(f7*f45) with f7 = [x<=15]. Measured on all inputs: f7*f45 = [x<=15] - [x<4] + [x=1].
In the normalization forward, at the CCX q36 q1 q21 (q36 = [x<4], q35 = [x<=15], q36*q1 = [x=1], q21 = 1 there):
    S on q35, S^-1 on q36, and S before / S^-1 after that CCX on q21 (which gives i^[x=1])
apply exactly i^([x<=15] - [x<4] + [x=1]): four Clifford phases, no T, no Toffoli. The endpoint keeps only the
rotation e*f45. Net: -1 Toffoli and -2 T (= -1.5 per shot). All facts are checked on the full domain first.
Usage: relocate_cs2.py IN.kmx OUT.kmx"""
import sys
sys.path.insert(0, '@FG_ROOT@/tools')
import numpy as np, kmsim
from fractions import Fraction
src, dst = sys.argv[1], sys.argv[2]
text = open(src).read()
lines = text.split('\n')
head = 0
while lines[head].split()[0] in ('APPEND_TO_REGISTER', 'REGISTER'):
    head += 1
ops, regs = kmsim.parse(text)
L = lambda i: lines[head + i].strip()
cs = None
for i in range(len(ops) - 13):
    if not (L(i + 1) == 'CX q23 q22' and L(i + 2).startswith('CCX q22 q25 ') and L(i + 3) == 'CX q23 q22'):
        continue
    tq = L(i + 2).split()[3]
    if (L(i + 4) == 'Z_POW %s 0.25' % tq and L(i + 5).startswith('CX %s ' % tq) and L(i + 6).endswith(' 1.75')
            and L(i + 7) == L(i + 5) and L(i + 8).startswith('HMR %s ' % tq) and L(i + 10) == 'CZ q22 q25'
            and L(i + 11) == 'CZ q23 q25' and L(i + 12) == 'POP_CONDITION'):
        r = L(i + 5).split()[2]
        assert L(i).startswith('Z_POW %s ' % r) and L(i + 6) == 'Z_POW %s 1.75' % r, (L(i), L(i + 6))
        b = L(i + 8).split()[2]
        assert L(i + 9) == 'PUSH_CONDITION if %s' % b
        cs = (i, r, tq); break
assert cs, 'CS block not found'
k, R, TQ = cs
angle = Fraction(L(k).split()[2])
assert Fraction(1, 4) < angle < Fraction(1, 4) + Fraction(1, 10**6), angle
newangle = angle - Fraction(1, 4)
site = None
for i in range(min(2000, len(ops))):
    if L(i) == 'CCX q36 q1 q21':
        site = i; break
assert site is not None, 'normalization CCX q36 q1 q21 not found'
sim = kmsim.Sim(ops, regs['x'])
X = np.arange(1, sim.n + 1)
def bits(v): return np.unpackbits(v.view(np.uint8), bitorder='little')[:sim.n].astype(np.int64)
sim.run(stop=site)
lt4, le15, q1, q21 = bits(sim.get('q36')), bits(sim.get('q35')), bits(sim.get('q1')), bits(sim.get('q21'))
assert np.array_equal(lt4, (X < 4).astype(np.int64)), 'q36 != [x<4]'
assert np.array_equal(le15, (X <= 15).astype(np.int64)), 'q35 != [x<=15]'
p = lt4 & q1
q21new = q21 ^ p
inserted = (le15 - lt4 + (q21 - q21new)) % 4          # exponent of i applied by the four Clifford gates
sim2 = kmsim.Sim(ops, regs['x']); sim2.run(stop=k + 2)
f45 = bits(sim2.get(R))
sim2.run(start=k + 2, stop=k + 4)
f7 = bits(sim2.get(TQ))
assert np.array_equal(f7, (X <= 15).astype(np.int64)), 'endpoint temp != [x<=15]'
need = (f7 & f45) % 4
assert np.array_equal(inserted, need), 'inserted Clifford phase != endpoint CS phase'
print('verified on', sim.n, 'inputs: endpoint CS at op', k, '(rotation', R, angle, '->', newangle, '); Clifford site at op', site,
      '; [x=1] count', int(p.sum()))
def dyadic(fr):
    num, den = fr.numerator, fr.denominator
    kk = den.bit_length() - 1
    digits = str(num * 5 ** kk).rjust(kk + 1, '0')
    whole, frac = digits[:-kk], digits[-kk:].rstrip('0')
    return (whole or '0') + ('.' + frac if frac else '')
assert Fraction(dyadic(newangle)) == newangle
out = lines[:head]
for i in range(len(lines) - head):
    if i == site:
        out += ['Z_POW q35 0.5', 'Z_POW q36 1.5', 'Z_POW q21 0.5', lines[head + i], 'Z_POW q21 1.5']
        continue
    if k + 1 <= i <= k + 12:
        continue
    if i == k:
        out.append('Z_POW %s %s' % (R, dyadic(newangle))); continue
    out.append(lines[head + i])
open(dst, 'w').write('\n'.join(out))
print('wrote', dst)
