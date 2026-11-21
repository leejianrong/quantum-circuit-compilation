#!/usr/bin/env python3
# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Full-domain mechanical audit of a kickmix text circuit.

For every Toffoli-like gate, on ALL 3,133,452 official inputs (random HMR
outcomes), test whether its AND product lies in the affine GF(2) span of the
48 wire values just before the gate. If it does, the gate can be replaced by
CX/X gates (product independent of the target) or by measurement-based
uncomputation HMR + CZ (product = target xor affine), i.e. zero Toffolis.
Also records the live-wire profile (wires not identically zero) per operation.

Findings are candidates only: acceptance needs the exact50 native proof.
"""
import argparse, json, sys, time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import kmsim


def stage_of(cuts, index):
    for cut in cuts:
        if index < cut['instruction_cut']:
            return cut['name']
    return 'final_layout'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('kmx', type=Path)
    ap.add_argument('--build', type=Path)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--seed', type=int, default=0)
    args = ap.parse_args()
    began = time.monotonic()
    ops, registers = kmsim.parse(args.kmx.read_text())
    xreg = registers['x']
    qwires = kmsim.quantum_wires(ops)
    cuts = json.loads(args.build.read_text())['cuts'] if args.build else []
    sim = kmsim.Sim(ops, xreg, seed=args.seed)
    sampler = kmsim.Sampler(sim)
    findings, gates = [], []
    nonzero = {w: bool(sim.get(w).any()) for w in qwires}
    live_profile = np.zeros(len(ops), dtype=np.int16)
    stats = dict(tested=0)

    def before(index, s):
        kind, a, condition, angle, line = ops[index]
        if kind not in kmsim.TOFFOLI_LIKE:
            return
        mask = s.active_mask(condition)
        active = 1.0 if mask is None else float(np.bitwise_count(mask).sum()) / s.n
        if kind == 'CCX':
            products = [('ab', s.get(a[0]) & s.get(a[1]))]
        elif kind == 'CSWAP':
            products = [('c(x^y)', s.get(a[0]) & (s.get(a[1]) ^ s.get(a[2])))]
        else:
            products = [('ab', s.get(a[0]) & s.get(a[1])), ('ac', s.get(a[0]) & s.get(a[2])),
                        ('bc', s.get(a[1]) & s.get(a[2]))]
        record = dict(op=index, line=line, kind=kind, args=list(a), condition=condition,
                      depth=len(s.stack) - 1, active=active, stage=stage_of(cuts, index))
        gates.append(record)
        if active == 0.0:
            record['never_active'] = True
            return
        for label, product in products:
            stats['tested'] += 1
            relation = kmsim.affine_relation(s, sampler, product, qwires, mask)
            if relation is not None:
                wires, constant = relation
                found = dict(record, product=label, relation_wires=wires, relation_constant=int(constant),
                             product_identically_zero=not wires and not constant)
                findings.append(found)
                print(json.dumps(found), flush=True)
                break

    def after(index, s):
        kind, a, condition, angle, line = ops[index]
        for w in a:
            if w in nonzero:
                nonzero[w] = bool(s.get(w).any())
        live_profile[index] = sum(nonzero.values())

    sim.run(before=before, after=after)
    final = {w: bool(sim.get(w).any()) for w in qwires}
    restored = np.array_equal(sim.value(xreg), sim.xs)
    scratch_zero = not any(final[w] for w in qwires if w not in xreg)
    peak = int(live_profile.max())
    peak_ops = np.flatnonzero(live_profile == peak)
    runs, start = [], None
    for i in peak_ops.tolist():
        if start is None:
            start = prev = i
        elif i == prev + 1:
            prev = i
        else:
            runs.append((start, prev)); start = prev = i
    if start is not None:
        runs.append((start, prev))
    result = dict(status='AUDIT_CANDIDATES_ONLY_NOT_PROVED', kmx=str(args.kmx), inputs=sim.n, seed=args.seed,
                  operations=len(ops), toffoli_like_static=sim.toffoli_static,
                  toffoli_like_mean=sim.toffoli_executed / sim.n,
                  input_restored=bool(restored), scratch_zero=bool(scratch_zero),
                  products_tested=stats['tested'], findings=findings,
                  expected_saving=sum(f['active'] for f in findings),
                  live_peak=peak, live_peak_runs=[dict(first=a, last=b, stage=stage_of(cuts, a)) for a, b in runs],
                  sample_size=len(sampler.positions), seconds=time.monotonic() - began)
    args.out.write_text(json.dumps(result, indent=1) + '\n')
    np.save(args.out.with_suffix('.live.npy'), live_profile)
    args.out.with_suffix('.gates.json').write_text(json.dumps(gates) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('findings', 'live_peak_runs')}, indent=1))
    print('peak runs:', len(runs), [(r['first'], r['last'], r['stage']) for r in result['live_peak_runs']][:40])


if __name__ == '__main__':
    main()
