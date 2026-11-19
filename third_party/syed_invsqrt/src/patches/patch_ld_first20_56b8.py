# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
# LOADER2 PIN (pinfirst.sh): this copy loads @FG_ROOT@/agents/loader2/certs/first_cap20_56b8.json (sha f09657772c5fdba988c5dae5e599c003e635cc000d4aa53093362d0846332ec9, work cap 20); the docstring below describes the template.
"""Agent loader2 copy of agents/loader/patch_ld_first21.py at WORK CAP 20 (raw address, all 7 slots fixed): 26 other owners
+ 20 = 46, so a Q46 body does not need the h0 pack for the first-loader peak. Certificate
agents/loader2/certs/first_cap20_58_tailc_330000.json (58 Toffolis; tail re-synthesis of sweep s11 seed330000 (60) at
outputs 13-14; replay_loader_v2.py PASS, 42 HMR debts, work peak 20). Only the certificate and the cap assert differ.

Serves both lines (Q48: 26 other owners; Q47: 25 once h0 is packed by patch_w47_body.py; the loader itself is the
same). The certificate (mode first_raw, schema of the frozen loader16_first61_Q48.json, independent replay
replay_loader_v2.py PASS) is emitted with a line-for-line copy of candidate07 tables07.load_joint16 for variant
'first' (every discarded truth -> shared TableDebts.erase; the universal table cleanup repays it). Replaces ONLY
variant='first' of tables.load_joint16: put it AFTER patch_donor_loaders.py / patch_donor_first60.py.
Env LD_FIRST_JSON overrides the certificate path (its sha is recorded in REPORT, not pinned).
"""
import hashlib, json, os
from pathlib import Path

DEFAULT = Path('@FG_ROOT@/agents/loader2/certs/first_cap20_56b8.json')
DEFAULT_SHA = 'f09657772c5fdba988c5dae5e599c003e635cc000d4aa53093362d0846332ec9'
MODEL_SHA = '24fff823faa911afe93d02afc3ded0bbd156a210a85f1265c989a087f8fd1219'
REPORT = {}


def _certificate():
    path = Path(os.environ.get('LD_FIRST_JSON', str(DEFAULT)))
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if path == DEFAULT and DEFAULT_SHA:
        assert sha == DEFAULT_SHA, 'pinned certificate changed'
    data = json.loads(raw)
    assert data['status'] == 'COMPLETE_MATHEMATICAL_LOADER_NOT_NATIVE'
    assert data['model_sha256'] == MODEL_SHA and data['mode'] == 'first_raw'
    assert data['fixed_address_slots'] == list(range(7)) and data['reusable_input_slots'] == []
    assert data['work_cap'] == data['work_peak'] == 20
    hmr = sum(len(st['discarded_truths']) for st in data['steps'] if st['kind'] == 'Clifford_frame_then_HMR')
    REPORT.update(path=str(path), sha256=sha, Toffolis=data['Toffolis'], HMR_debts=hmr)
    return data, hmr


def apply(ctx):
    tables = ctx.tables
    original = tables.load_joint16
    km, cb = tables.km, tables.cb
    data, hmr_expected = _certificate()

    def load_joint16(builder, address7, *, variant, debts):
        if variant != 'first':
            return original(builder, address7, variant=variant, debts=debts)
        address = list(address7)
        if len(address) != 7 or len(set(address)) != 7 or not all(isinstance(q, km.q) for q in address):
            raise ValueError('Expected seven current, distinct quantum address owners.')
        if not isinstance(debts, tables.TableDebts):
            raise TypeError('Expected the shared pinned TableDebts owner.')
        entry = builder.num_allocated_qubits
        before_debts = debts.total_recorded
        fixed = list(address)
        work = []
        cap = data['work_cap']
        available = list(builder.alloc_qubits(cap))
        offset = 1 + len(fixed)
        count = 0
        for item in data['steps']:
            kind = item['kind']
            if kind in ('bank', 'CCX_new_coordinate'):
                target = available.pop(0)
                plan = tables.plan_from_json(item['plan'])
                cb.emit_xor(builder, fixed + work, target, plan)
                work.append(target)
                count += plan.and_count
            elif kind == 'Clifford_zero_dependent_coordinate':
                index = item['index']
                target = work[index]
                tables._BASE._affine_xor(builder, fixed, work[:index], target, item['expression'])
                work.pop(index)
                available.append(target)
            elif kind == 'Clifford_frame_then_HMR':
                assert item['affine_fixed_offset'] == offset
                tables.emit_affine_frame(builder, fixed, work, item['full_affine_rows'])
                kept = item['retained_count']
                discard = work[kept:]
                assert len(discard) == len(item['discarded_truths'])
                for wire, truth in zip(discard, item['discarded_truths']):
                    debts.erase(builder, wire, int(truth, 16))
                    available.append(wire)
                work = work[:kept]
            elif kind == 'virtual_affine_product':
                pass
            elif kind == 'XOR_product_existing_coordinate':
                assert item['target_index'] == 0
                plan = tables.plan_from_json(item['plan'])
                cb.emit_xor(builder, fixed + work[1:], work[0], plan)
                count += plan.and_count
            elif kind == 'final_output_Clifford_frame':
                tables.emit_affine_frame(builder, fixed, work, [int(row) << offset for row in item['matrix_rows']])
            else:
                raise AssertionError(('Unknown loader operation', kind))
            assert len(work) + len(available) == cap and len(set(work + available)) == cap
            assert not set(fixed) & set(work + available)
        assert len(work) == 16 and count == data['Toffolis']
        assert debts.total_recorded - before_debts == hmr_expected
        if available:
            builder.free(tables.array(available))
        assert builder.num_allocated_qubits == entry + 16
        REPORT['emitted'] = dict(Toffolis=count, HMR=hmr_expected)
        return list(work[:13]), list(work[13:])
    tables.load_joint16 = load_joint16
