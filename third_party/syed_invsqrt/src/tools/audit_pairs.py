#!/usr/bin/env python3
# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Recomputed-value scan: pairs of Toffoli-like gates (i earlier, j later) whose AND
products differ only by an affine function of the wires live just before gate j:

    p_j = p_i xor affine(wires at j)        on every official input.

If p_i were still held on a spare qubit at j, gate j would cost CX only. The scan
reports each such pair, the live-wire maximum between the two gates (a spare qubit
exists when it is below Q) and verifies the relation exactly on the full domain.
Candidates only; a rewrite counts after the exact50 proof.
"""
import argparse, json, sys, time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import kmsim


def reduce(basis, v):
    while v:
        hit = basis.get(v.bit_length() - 1)
        if hit is None:
            return v
        v ^= hit
    return 0


def products_of(s, kind, a):
    if kind == 'CCX':
        return s.get(a[0]) & s.get(a[1])
    if kind == 'CSWAP':
        return s.get(a[0]) & (s.get(a[1]) ^ s.get(a[2]))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('kmx', type=Path); ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--live', type=Path, help='.live.npy from audit_affine'); ap.add_argument('--build', type=Path)
    args = ap.parse_args(); began = time.monotonic()
    ops, registers = kmsim.parse(args.kmx.read_text()); xreg = registers['x']; qw = kmsim.quantum_wires(ops)
    live = np.load(args.live) if args.live else None
    cuts = json.loads(args.build.read_text())['cuts'] if args.build else []

    def stage_of(i):
        for c in cuts:
            if i < c['instruction_cut']:
                return c['name']
        return 'final_layout'

    # Pass 1: sampled.
    sim = kmsim.Sim(ops, xreg); sampler = kmsim.Sampler(sim, count=4096)
    earlier = []  # (op, sampled product)
    hits = {}     # j -> list of i
    def before(index, s):
        kind, a, cond, angle, line = ops[index]
        if kind not in ('CCX', 'CSWAP') or len(s.stack) > 1 or cond is not None:
            return
        p = sampler.take(products_of(s, kind, a))
        basis = {}
        for w in qw:
            v = reduce(basis, sampler.take(s.get(w)))
            if v:
                basis[v.bit_length() - 1] = v
        v = reduce(basis, sampler.take(s.ones))
        if v:
            basis[v.bit_length() - 1] = v
        rj = reduce(basis, p)
        if rj:
            for i, pi in earlier:
                if reduce(basis, pi ^ p) == 0:
                    hits.setdefault(index, []).append(i)
        earlier.append((index, p))
    sim.run(before=before)
    print('sampled pair hits:', sum(len(v) for v in hits.values()), 'gates with a hit:', len(hits),
          'seconds %.1f' % (time.monotonic() - began), flush=True)

    # Pass 2: exact verification of the closest earlier partner(s) of every hit gate.
    wanted = sorted({i for j, ii in hits.items() for i in ii[-3:]})
    stored = {}
    sim = kmsim.Sim(ops, xreg); sampler2 = kmsim.Sampler(sim, count=4096)
    rows = []
    def before2(index, s):
        kind, a, cond, angle, line = ops[index]
        if kind not in ('CCX', 'CSWAP'):
            return
        if index in hits:
            p = products_of(s, kind, a)
            for i in reversed(hits[index][-3:]):
                rel = kmsim.affine_relation(s, sampler2, p ^ stored[i], qw)
                if rel is not None:
                    span_max = int(live[i:index].max()) if live is not None else None
                    rows.append(dict(later_op=index, later_line=line, later=[kind] + list(a), earlier_op=i,
                                     earlier_line=ops[i][4], earlier=[ops[i][0]] + list(ops[i][1]),
                                     distance=index - i, max_live_between=span_max, stage=stage_of(index),
                                     relation_wires=rel[0], relation_constant=int(rel[1])))
                    break
        if index in wanted:
            stored[index] = products_of(s, kind, a).copy()
    sim.run(before=before2)
    rows.sort(key=lambda r: (r['max_live_between'] if r['max_live_between'] is not None else 0, r['distance']))
    args.out.write_text(json.dumps(dict(rows=rows, seconds=time.monotonic() - began), indent=1) + '\n')
    print('exact recomputed pairs:', len(rows))
    by = {}
    for r in rows:
        key = (r['stage'], r['max_live_between'])
        by[key] = by.get(key, 0) + 1
    for k, n in sorted(by.items(), key=lambda kv: (kv[0][1] or 0, kv[0][0])):
        print(n, k)
    for r in rows[:40]:
        print(r['later_op'], r['later'], '<-', r['earlier_op'], r['earlier'], 'dist', r['distance'], 'maxlive',
              r['max_live_between'], r['stage'], r['relation_wires'], r['relation_constant'])


if __name__ == '__main__':
    main()
