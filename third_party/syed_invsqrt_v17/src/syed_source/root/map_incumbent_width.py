# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon,
# Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Exact full-domain/all-HMR value liveness of the already qualified incumbent.

This is a value-lifetime analysis, not a replacement phase qualification checker.
Each coefficient is a bitset over all 3,133,452 legal original inputs. Sparse
Boolean polynomials retain every syntactic HMR variable and actual guard.
"""
from pathlib import Path
from collections import Counter
from fractions import Fraction
import gzip, hashlib, json, sys, time
import numpy as np

BASE = Path(__file__).resolve().parents[1]
ENGINE = BASE / 'incumbent_sources/frozen_source/fusion/runtime/work/c10/narrow/checkpoint002/cleanroom/baseline_stage97/engine'
sys.path.insert(0, str(ENGINE))
from branch_prover import Program
NOTICE = 'Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.'
NATIVE = BASE / 'root/combined1114_selective_qualification_v1/first/emitted/candidate.kmx'
NATIVE_SHA = '3ced9b53d9a499037527c6097030e8699bfbdcdfc17342fc2647247ad99c6259'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def px(a, b):
    if not a: return b.copy()
    if not b: return a.copy()
    out = a.copy()
    for k, v in b.items():
        w = out.get(k, 0) ^ v
        if w: out[k] = w
        else: out.pop(k, None)
    return out

def pm(a, b):
    if not a or not b: return {}
    out = {}
    for k, v in a.items():
        for j, w in b.items():
            r = v & w
            if not r: continue
            key = k | j
            z = out.get(key, 0) ^ r
            if z: out[key] = z
            else: out.pop(key, None)
    return out

def runs(values, predicate):
    out = []; start = None
    for i, value in enumerate(values):
        yes = predicate(value)
        if yes and start is None: start = i
        if start is not None and (not yes or i == len(values)-1):
            stop = i if not yes else i+1
            out.append([start, stop]); start = None
    return out

def main():
    began = time.monotonic()
    assert sha(NATIVE) == NATIVE_SHA
    source_proof = BASE / 'root/combined1114_selective_qualification_v1/proof.json'
    p = json.loads(source_proof.read_text())
    assert p['qualified'] and p['Q'] == 44 and p['proved_inputs'] == 3133452
    program = Program(NATIVE.read_text()); assert len(program.operations) == 40536
    n = 3133452; full = (1 << n)-1; one = {0:full}
    xs = np.arange(1, n+1, dtype=np.uint64)
    state = {q:{} for q in program.wires}
    state.update({'0':{}, 'False':{}, '1':one, 'True':one})
    original = {}
    for bit, q in enumerate(program.registers['x']):
        value = int.from_bytes(np.packbits(((xs >> bit) & 1).astype(np.uint8), bitorder='little').tobytes(), 'little')
        state[q] = original[q] = {0:value}
    del xs
    stack = [one]; quantum = [f'q{i}' for i in range(44)]
    masks = []; data_masks = []; largest = 0; events = []; gate_cost = Counter()
    def record():
        nonlocal largest
        m = d = 0
        for qi, q in enumerate(quantum):
            poly = state[q]; largest = max(largest, len(poly))
            if poly: m |= 1 << qi
            if any(v != full for v in poly.values()): d |= 1 << qi
        masks.append(m); data_masks.append(d)
    record()
    for i, op in enumerate(program.operations):
        kind, a = op.kind, op.arguments
        if kind == 'PUSH_CONDITION':
            g = stack[-1] if op.condition is None else pm(stack[-1], state[op.condition])
            stack.append(g); record(); continue
        if kind == 'POP_CONDITION':
            assert len(stack)>1; stack.pop(); record(); continue
        # Diagonal gates have no effect on values. Their full phases were already
        # proved by the separately bound unchanged qualification checker.
        if kind in ('Z','CZ','CCZ','NEG','Z_POW'):
            record(); continue
        g = stack[-1] if op.condition is None else pm(stack[-1], state[op.condition])
        if g:
            if kind in ('X','BIT_INVERT'):
                state[a[0]] = px(state[a[0]], g)
            elif kind == 'CX':
                state[a[1]] = px(state[a[1]], pm(g,state[a[0]]))
            elif kind == 'CCX':
                state[a[2]] = px(state[a[2]], pm(g,pm(state[a[0]],state[a[1]])))
            elif kind in ('SWAP','CSWAP'):
                u,v = a[-2:]; delta = pm(g,px(state[u],state[v]))
                if kind == 'CSWAP': delta = pm(delta,state[a[0]])
                state[u],state[v] = px(state[u],delta),px(state[v],delta)
            elif kind == 'HMR':
                complement = px(one,g)
                state[a[0]] = pm(complement,state[a[0]])
                state[a[1]] = px(pm(complement,state[a[1]]),pm(g,{1 << op.event:full}))
                events.append(dict(operation=i,event=op.event,quantum_owner=a[0],outcome_owner=a[1],unconditional=g==one))
            elif kind in ('BIT_STORE0','BIT_STORE1'):
                desired = one if kind == 'BIT_STORE1' else {}
                state[a[0]] = px(state[a[0]],pm(g,px(state[a[0]],desired)))
            elif kind == 'R':
                assert not pm(g,state[a[0]])
            else: raise AssertionError((i,kind))
        record()
        if i % 5000 == 0:
            print(json.dumps(dict(operation=i,seconds=time.monotonic()-began,occupied=masks[-1].bit_count(),max_quantum_terms=largest)),flush=True)
    assert stack == [one]
    assert all(state[q] == v for q,v in original.items())
    assert all(not state[q] for q in quantum if q not in original)
    assert len(masks) == len(program.operations)+1
    peak = max(m.bit_count() for m in masks)
    windows = runs(masks,lambda m:m.bit_count()==peak)
    intervals = []
    for qi,q in enumerate(quantum):
        for a,b in runs(masks,lambda m:bool(m >> qi & 1)):
            birth = None if a==0 else a-1
            death = None if b==len(masks) else b-1
            entry = dict(owner=q,first_occupied_cut=a,first_zero_cut=b,birth_operation=birth,clear_operation=death)
            if birth is not None:
                op=program.operations[birth];entry['birth_kind']=op.kind;entry['birth_arguments']=list(op.arguments);entry['birth_condition']=op.condition
            if death is not None:
                op=program.operations[death];entry['clear_kind']=op.kind;entry['clear_arguments']=list(op.arguments);entry['clear_condition']=op.condition
            intervals.append(entry)
    out = BASE / 'root/incumbent_width_v1';out.mkdir(exist_ok=True)
    def write_gz(path,data):
        with path.open('wb') as f:
            with gzip.GzipFile(fileobj=f,mode='wb',mtime=0,filename='') as z:
                z.write((json.dumps(data,separators=(',',':'))+'\n').encode())
    mask_path=out/'ALL_INPUT_ALL_HMR_OCCUPANCY.json.gz'
    write_gz(mask_path,dict(notice=NOTICE,native_sha256=NATIVE_SHA,cut_semantics='Cut i is immediately before operation i; final cut is40536.',occupied_owner_masks=masks,input_dependent_owner_masks=data_masks))
    interval_path=out/'VALUE_LIFETIMES.json'
    interval_path.write_text(json.dumps(dict(notice=NOTICE,native_sha256=NATIVE_SHA,intervals=intervals),indent=2)+'\n')
    hist=Counter(m.bit_count() for m in masks);data_hist=Counter(m.bit_count() for m in data_masks)
    report=dict(notice=NOTICE,status='EXACT_FULL_DOMAIN_ALL_HMR_INCUMBENT_VALUE_LIFETIMES',qualified_incumbent_circuit_sha256=p['circuit_sha256'],native_sha256=NATIVE_SHA,operations=len(program.operations),full_original_inputs=n,all_syntactic_HMR_variables=program.measurements,all_HMR_branches_symbolically_retained=True,full_phase_qualification_unchanged_and_bound=True,peak_nonzero_quantum_owners=peak,peak_input_dependent_owners=max(m.bit_count() for m in data_masks),cut_count_histogram=dict(sorted(hist.items())),input_dependent_cut_count_histogram=dict(sorted(data_hist.items())),peak_windows=windows,peak_window_count=len(windows),peak_cut_count=sum(b-a for a,b in windows),value_lifetime_count=len(intervals),maximum_quantum_polynomial_terms=largest,original_inputs_restored=True,scratch_zero=True,scope='Nonzero Boolean-value occupancy on every legal original input and every HMR transcript. A nonempty polynomial denotes a wire that is nonzero on at least one branch/input. The union peak does not assert that all44values are simultaneously1. Interference, owner availability for gates, affine compression and reversible recoloring still require analysis. This is an exact lifetime map of an already qualified circuit, not a new circuit qualification.',Q43_break_even_expected_Toffolis=str(Fraction(44*22857,43*16)),Q43_added_Toffoli_budget_strict=str(Fraction(22857,688)),bindings={str(x.relative_to(BASE)):sha(x) for x in [Path(__file__),NATIVE,source_proof,ENGINE/'branch_prover.py',mask_path,interval_path]},seconds=time.monotonic()-began)
    (out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['status','peak_nonzero_quantum_owners','peak_input_dependent_owners','peak_window_count','peak_cut_count','value_lifetime_count','maximum_quantum_polynomial_terms','seconds']}),flush=True)

if __name__=='__main__': main()
