# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Agent width (FIRST LOADER ONLY variant, for Q47 builds where the second loader is Pro 2 second90): transplant candidate11r2's first60 / second78 loaders (Pro 2 port03) by native-text replay.

The donor loaders differ from candidate10's first61 / second79 only in their final segment (measured, rename-aware
diff). Their gate text is replayed from the donor kmx through our builder (plans/L1_first60.json,
plans/L2_second78.json made by scripts/make_replay_plan.py on the full domain): scratch owners are allocated at first
touch and freed when the donor wire is identically zero; every donor HMR is re-emitted as TableDebts.erase with the
measured 128-row truth of the raw table address, so OUR shared table cleanup (universal flush) repays it.
Replaces only tables07.load_joint16 (per variant; env WIDTH_DONOR_L1 / WIDTH_DONOR_L2, default both on).
"""
import json, os
from pathlib import Path

HERE = Path('@FG_ROOT@/agents/width')
USE = dict(first=True, second=False)
PLAN_FILES = dict(first=HERE / 'plans/L1_first60.json', second=HERE / 'plans/L2_second78.json')
EXPECT = dict(first=dict(ccx=60, hmr=42), second=dict(ccx=78, hmr=63))
REPORT = {}


def _plan(which):
    data = json.loads(PLAN_FILES[which].read_text())
    assert data['ccx'] == EXPECT[which]['ccx'] and data['hmr'] == EXPECT[which]['hmr']
    return data


def replay(builder, data, address7, debts):
    owner = data['entry_owner']
    v_wires = {}
    for w, (role, i) in owner.items():
        if role == 'v':
            v_wires[i] = w
    h = {}
    for i in range(7):
        h[v_wires[5 + i]] = address7[i]
    entry = set(h)
    assert set(data['touched_entry']) <= entry, 'donor block touches an entry wire we did not map'
    ccx = hmr = 0
    for item in data['plan']:
        kind = item[0]
        if kind == 'ALLOC':
            continue
        if kind == 'ZERO':
            w = item[1]
            if w in h:
                builder.free(h.pop(w))
            continue
        wires = item[1]
        for w in wires:
            if w not in h:   # scratch first touch, or a consumed entry wire reused after it was zero and released
                h[w] = builder.alloc_qubits(1)[0]
        q = [h[w] for w in wires]
        if kind == 'X':
            builder.x(q[0])
        elif kind == 'CX':
            builder.cx(q[0], q[1])
        elif kind == 'CCX':
            builder.ccx(q[0], q[1], q[2]); ccx += 1
        elif kind == 'SWAP':
            builder.swap(q[0], q[1])
        elif kind == 'HMR':
            debts.erase(builder, q[0], int(item[2], 16)); hmr += 1
        else:
            raise AssertionError(kind)
    D = [h[w] for w in data['outputs']['D']]
    H = [h[w] for w in data['outputs']['H']]
    assert len(D) == 13 and len(H) == 3
    return D, H, dict(ccx=ccx, hmr=hmr)


def apply(ctx):
    tables = ctx.tables
    original = tables.load_joint16

    def load_joint16(builder, address7, *, variant, debts):
        if not USE.get(variant):
            return original(builder, address7, variant=variant, debts=debts)
        assert isinstance(debts, tables.TableDebts)
        before = debts.total_recorded
        D, H, counts = replay(builder, _plan(variant), list(address7), debts)
        assert debts.total_recorded - before == EXPECT[variant]['hmr']
        REPORT[variant] = counts
        return D, H
    tables.load_joint16 = load_joint16
