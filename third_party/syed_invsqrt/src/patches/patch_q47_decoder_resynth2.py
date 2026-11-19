# normroot agent, 2026-11-12. Q47 line only. SUPERSEDES patch_q47_decoder_resynth.py (use one, not both).
"""Two donor-tail decoder outputs re-synthesised 5 -> 4 ANDs each (T2 replay plan rewrite, -2 Toffolis).

Data file q47_t2_rewrite.json (made by scripts/derive_q47_t2.py on runs/q47c5/build/q47c5raw.kmx, where T2 sits
377 ops before the donor text; wire names translated to the donor's by full-domain value matching):
  * donor q38: 5 CCX -> 4-AND plan over the live address-function wires at its first reader (op 26954);
  * donor q36: 5 CCX -> 4-AND plan over the live address-function wires at op 26739 plus ONE captured product:
    the product of the donor CCX at op 26527 (q44*q27, framed values) is copied into a new owner 'qcap' by a CX pair
    around that CCX (d19-style snapshot), used as the extra variable, then erased right after q36's plan by
    X + HMR with a Clifford fix-up (it is a quadratic function of the live address wires; the X removes the constant
    term so no classical-bit Z is needed).
Only entries that target q36 / q38 inside their accumulation segments are deleted (they change no other wire).
T2's ccx becomes 18. No-op unless the width w47 body module is loaded with TAIL == 'donor'.
"""
import copy, hashlib, json, sys
from pathlib import Path

HERE = Path('@FG_ROOT@/agents/normroot')
T2_SHA_PREFIX = '9a4cd975a1062505'
DATA = HERE / 'q47_t2_rewrite.json'
REPORT = {}


def _bits(v):
    out, i = [], 0
    while v:
        if v & 1: out.append(i)
        v >>= 1; i += 1
    return out


def _emit(plan, variables, target):
    ent = []
    if plan['constant']:
        ent.append(['X', [target], [], None])
    for b in _bits(plan['product_linear']):
        ent.append(['CX', [variables[b], target], [], None])
    for left, right, i, j in plan['products']:
        frame = [(variables[k], variables[i]) for k in _bits(left) if k != i]
        frame += [(variables[k], variables[j]) for k in _bits(right) if k != j]
        ent += [['CX', [a, b], [], None] for a, b in frame]
        ent.append(['CCX', [variables[i], variables[j], target], [], None])
        ent += [['CX', [a, b], [], None] for a, b in reversed(frame)]
    return ent


def _erase_cap(fix):
    v = fix['variables']
    ent = []
    if fix['constant']:
        ent.append(['X', ['qcap'], [], None])        # measure 1^p: the constant term cancels
    ent.append(['HMR', ['qcap'], ['bcap_normroot'], None])
    for b in _bits(fix['linear']):
        ent.append(['Z', [v[b]], [], 'bcap_normroot'])
    for i, j in fix['edges']:
        ent.append(['CZ', [v[i], v[j]], [], 'bcap_normroot'])
    ent.append(['ZERO', 'qcap'])
    return ent


def rewrite(T2, d):
    lo = T2['lo']
    cap_op, (ca, cb, ct) = d['capture']['donor_op'], d['capture']['ccx']
    segs = {d['q21']['donor_target']: d['q21'], d['q13']['donor_target']: d['q13']}
    dele = {}
    for tgt, s in segs.items():
        for k in s['segment_donor_ops']:
            dele[k] = tgt
    insert = {d['q21']['reader_donor_op']: _emit(d['q21']['plan'], d['q21']['variables'], d['q21']['donor_target'])
              + _erase_cap(d['cap_fix']),
              d['q13']['reader_donor_op']: _emit(d['q13']['plan'], d['q13']['variables'], d['q13']['donor_target'])}
    spans = {tgt: (min(s['segment_donor_ops']), s['reader_donor_op']) for tgt, s in segs.items()}
    out, op = [], lo
    deleted = 0
    for item in T2['plan']:
        if item[0] == 'ZERO':
            w = item[1]
            if w in spans and spans[w][0] <= op <= spans[w][1]:
                continue
            out.append(item); continue
        if op in insert:
            out.extend(insert[op])
        if op == cap_op:
            assert item[0] == 'CCX' and item[1] == [ca, cb, ct], item
            out.append(['CX', [ct, 'qcap'], [], None]); out.append(item); out.append(['CX', [ct, 'qcap'], [], None])
        elif op in dele:
            tgt = dele[op]
            assert item[0] in ('X', 'CX', 'CCX') and item[1][-1] == tgt and item[3] is None, item
            deleted += 1
        else:
            for tgt, (s0, s1) in spans.items():
                if s0 <= op < s1:
                    assert tgt not in item[1], ('target read inside its segment', op, item)
            out.append(item)
        op += 1
    assert deleted == len(dele)
    new = dict(T2); new['plan'] = out; new['ccx'] = T2['ccx'] - 2
    return new


def apply(ctx):
    body = sys.modules.get('variant_patch_patch_w47_body')
    if body is None or getattr(body, 'TAIL', None) != 'donor':
        REPORT['status'] = 'inactive'
        return
    plan_path = Path('@FG_ROOT@/agents/width/plans/T2_decoder_capture.json')
    assert hashlib.sha256(plan_path.read_bytes()).hexdigest().startswith(T2_SHA_PREFIX)
    tail = body._tail_modules()
    assert tail['T2']['ccx'] == 20 and tail['T2']['lo'] == 26385
    tail['T2'] = rewrite(copy.deepcopy(tail['T2']), json.loads(DATA.read_text()))
    REPORT['status'] = 'T2 decoder 20 -> 18 CCX'
