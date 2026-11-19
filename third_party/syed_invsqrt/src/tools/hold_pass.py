#!/usr/bin/env python3
# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Hold a recomputed AND product on a spare wire instead of paying its Toffoli again.

Input: a kmx text and chains of unconditional CCX gates [g0, g1, ..., gk] (op indices) whose
AND products are the same function of the input on the whole official domain (found and
verified exactly by tools/audit_pairs.py), with a spare wire available between them.

  g0   CCX a b t   ->  CCX a b S ; CX S t          (S: identically-zero wire nobody references)
  gi   CCX a b t   ->  CX S t
  gk   CCX a b t   ->  CX S t ; HMR S m ; CZ a b if m   (S returns to zero; kickback repaid)

Whenever the original circuit is about to reference the current holder, the value hops to
another free wire (CX S S2 ; CX S2 S), always outside classically conditioned blocks.
The result is a candidate only: the exact50 native proof decides.
"""
import bisect, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import kmsim


def analyse(text):
    ops, registers = kmsim.parse(text)
    qw = kmsim.quantum_wires(ops)
    depth, block_start, stack = [], [], []
    for i, (kind, a, cond, angle, line) in enumerate(ops):
        if kind == 'PUSH_CONDITION':
            depth.append(len(stack)); block_start.append(stack[0] if stack else i); stack.append(i)
        elif kind == 'POP_CONDITION':
            stack.pop(); depth.append(len(stack)); block_start.append(stack[0] if stack else i)
        else:
            depth.append(len(stack)); block_start.append(stack[0] if stack else i)
    # Effective reference index: an op inside a conditioned block counts at the block's first op.
    refs = {w: [] for w in qw}
    for i, (kind, a, cond, angle, line) in enumerate(ops):
        for w in a:
            if w in refs:
                e = block_start[i]
                if not refs[w] or refs[w][-1] != e:
                    refs[w].append(e)
    sim = kmsim.Sim(ops, registers['x'])
    nonzero = {w: bool(sim.get(w).any()) for w in qw}
    transitions = {w: [(-1, nonzero[w])] for w in qw}

    def after(index, s):
        for w in ops[index][1]:
            if w in nonzero:
                now = bool(s.get(w).any())
                if now != nonzero[w]:
                    nonzero[w] = now
                    transitions[w].append((index, now))
    sim.run(after=after)

    def zero_before(w, t):
        """Wire identically zero just before op t (after op t-1)."""
        tr = transitions[w]
        k = bisect.bisect_right([x[0] for x in tr], t - 1) - 1
        return not tr[k][1]

    def next_ref(w, t):
        r = refs[w]
        k = bisect.bisect_left(r, t)
        return r[k] if k < len(r) else 10 ** 9

    return ops, qw, depth, zero_before, next_ref


def plan_chain(ops, qw, depth, zero_before, next_ref, chain):
    g0, gk = chain[0], chain[-1]
    for g in chain:
        assert ops[g][0] == 'CCX' and depth[g] == 0 and ops[g][2] is None, (g, ops[g])
    used = set()
    for g in chain:
        used.update(ops[g][1])

    def pick(t, exclude):
        best = None
        for w in qw:
            if w in exclude or w in used or not zero_before(w, t):
                continue
            r = next_ref(w, t)
            if r <= t:
                continue
            if best is None or r > best[0]:
                best = (r, w)
        return best

    hops, holder_at = [], {}
    choice = pick(g0, set())
    assert choice is not None, 'no free wire at chain start'
    until, holder = choice
    start_holder = holder
    t = g0
    schedule = [(g0, holder)]
    while until <= gk:
        assert depth[until] == 0
        nxt = pick(until, {holder})
        assert nxt is not None and nxt[0] > until, ('no free wire to hop to', until)
        hops.append((until, holder, nxt[1]))
        until, holder = nxt
        schedule.append((hops[-1][0], holder))

    def holder_for(g):
        current = schedule[0][1]
        for when, w in schedule[1:]:
            if when <= g:
                current = w
        return current
    return dict(chain=chain, hops=hops, holders={g: holder_for(g) for g in chain})


def apply_chains(text, chains):
    """Apply chains one at a time, latest first (edits never shift earlier op indices)."""
    report = []
    for chain in sorted(chains, key=lambda c: -c[0]):
        ops, qw, depth, zero_before, next_ref = analyse(text)
        plan = plan_chain(ops, qw, depth, zero_before, next_ref, chain)
        lines = text.split('\n')
        used_bits = {int(tok[1:]) for line in lines for tok in line.split() if tok.startswith('b') and tok[1:].isdigit()}
        bit = f'b{max(used_bits) + 1 if used_bits else 0}'
        insert_before, replace = {}, {}
        for when, old, new in plan['hops']:
            insert_before.setdefault(when, []).extend([f'CX {old} {new}', f'CX {new} {old}'])
        for n, g in enumerate(chain):
            a, b, t = ops[g][1]
            S = plan['holders'][g]
            if n == 0:
                new = [f'CCX {a} {b} {S}', f'CX {S} {t}']
            elif n < len(chain) - 1:
                new = [f'CX {S} {t}']
            else:
                new = [f'CX {S} {t}', f'HMR {S} {bit}', f'CZ {a} {b} if {bit}']
            replace[g] = new
        for index in sorted(set(insert_before) | set(replace), reverse=True):
            line_no = ops[index][4] - 1
            new_lines = insert_before.get(index, []) + replace.get(index, [lines[line_no]])
            lines[line_no:line_no + 1] = new_lines
        text = '\n'.join(lines)
        report.append(dict(chain=chain, gates=[' '.join((ops[g][0],) + ops[g][1]) for g in chain],
                           hops=len(plan['hops']), holders=sorted(set(plan['holders'].values())),
                           expected_toffoli_saving=len(chain) - 1))
    return text, report


def chains_from_pairs(pairs, Q=48):
    """Link exact-equality pairs with a spare wire (max live between < Q) into chains."""
    link = {}
    for r in pairs:
        if r['relation_wires'] or r['relation_constant'] or r['later'][0] != 'CCX' or r['earlier'][0] != 'CCX':
            continue
        if r['max_live_between'] is None or r['max_live_between'] >= Q:
            continue
        link[r['later_op']] = r['earlier_op']
    chains, seen = [], set()
    for later in sorted(link, reverse=True):
        if later in seen:
            continue
        chain = [later]
        while chain[-1] in link:
            chain.append(link[chain[-1]])
        seen.update(chain)
        chains.append(sorted(chain))
    return chains


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('kmx', type=Path); ap.add_argument('pairs', type=Path)
    ap.add_argument('--out', type=Path, required=True); ap.add_argument('--Q', type=int, default=48)
    args = ap.parse_args()
    chains = chains_from_pairs(json.loads(args.pairs.read_text())['rows'], args.Q)
    text, report = apply_chains(args.kmx.read_text(), chains)
    args.out.write_text(text)
    args.out.with_suffix('.hold.json').write_text(json.dumps(report, indent=1) + '\n')
    print(json.dumps(report, indent=1))
