# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Construct low-product restorations after deferred-HMR idle intervals.

Unlike the prior immediate-feedback endpoint screen, retirement is always
an HMR and its phase debt is repaid by a Z on the exactly restored target.
Every target reference, including rotations and diagonal reads, is excluded
inside the interval. Entry precedes a peak birth and exit follows a peak
death, both at native occupancy <=43. Products accumulate into the target;
parity preparation needs no helper. Quadratic fiber rank minimization is
constructive only, with no claim of globally minimum restoration cost.
"""
from pathlib import Path
from itertools import combinations
from collections import Counter
import argparse
import gzip
import json
import pickle
import time
from temporal_core import NOTICE, Program, Span, affine_preimage, bits, captures, mul, sha, xor
from screen_q43_idle_recompute import pack
from screen_initial_cubic_outputs import dual_from_basis

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def matrix_rows(n, pairs, value):
    rows = [0]*n
    for k in bits(value):
        i,j = pairs[k]
        rows[i] ^= 1 << j
        rows[j] ^= 1 << i
    return rows


def matrix_rank(rows):
    basis = {}
    for row in rows:
        while row:
            pivot = row.bit_length()-1
            if pivot not in basis:
                basis[pivot] = row
                break
            row ^= basis[pivot]
    return len(basis)


def factor_alternating(rows):
    rows = list(rows)
    result = []
    while any(rows):
        p = next(i for i,row in enumerate(rows) if row)
        q = (rows[p]&-rows[p]).bit_length()-1
        a,b = rows[p],rows[q]
        assert not (a>>p&1) and (a>>q&1) and (b>>p&1) and not (b>>q&1)
        result.append((a,b))
        for i in range(len(rows)):
            rows[i] ^= (b if a>>i&1 else 0) ^ (a if b>>i&1 else 0)
        assert rows[p] == rows[q] == 0
    return result


def restore(frame, owner, full, xs, sweeps=3):
    physical = [('constant',{0:full})] + [(f'q{i}',frame[f'q{i}']) for i in range(44) if f'q{i}' != owner]
    products = [mul(p,q) for (_,p),(_,q) in combinations(physical,2)]
    monomials = sorted({m for _,p in physical for m in p} |
                       {m for p in products for m in p} | set(frame[owner]))
    n = len(xs)
    initial = Span()
    for q,p in physical:
        initial.add(pack(p,monomials,n),q)
    target = pack(frame[owner],monomials,n)
    affine = initial.solve(target)
    rec = dict(target_owner=owner,available_affine_rank=len(initial.columns),
               available_basis=initial.descriptors,formal_HMR_monomials=[list(bits(m)) for m in monomials])
    if affine is not None:
        return dict(rec,status='ACTUAL_AFFINE_RESTORATION_ON_BOUND_CHART',paid_products=0,
                    products=[],affine_offset=[initial.descriptors[j] for j in bits(affine)])
    names = initial.descriptors[1:]
    polynomials = [dict(physical)[q] for q in names]
    pairs = list(combinations(range(len(names)),2))
    values = [pack(mul(polynomials[i],polynomials[j]),monomials,n) for i,j in pairs]
    point,kernel,rank = affine_preimage([initial.normal(v) for v in values],initial.normal(target))
    rec.update(complete_quadratic_rank=len(initial.columns)+rank,
               complete_product_fiber_dimension=len(kernel))
    if point is None:
        Q = initial.copy()
        for edge,value in zip(pairs,values):
            Q.add(value,edge)
        dual = dual_from_basis(Q,target)
        character = []
        for j,m in enumerate(monomials):
            local = (dual >> (n*j))&full
            if local:
                character.append(dict(HMR_events=list(bits(m)),
                                      original_inputs=[int(xs[k]) for k in bits(local)]))
        return dict(rec,status='COMPLETE_NEGATIVE_QUADRATIC_RESTORATION_IMAGE',
                    literal_character=character,target_pairing=1,all_quadratic_pairings=0)
    rows = matrix_rows(len(names),pairs,point)
    best_rank = matrix_rank(rows)
    kernel_rows = [matrix_rows(len(names),pairs,k) for k in kernel]
    accepted = []
    for sweep in range(sweeps):
        changed = False
        for j,delta in enumerate(kernel_rows):
            candidate_rows = [x^y for x,y in zip(rows,delta)]
            candidate_rank = matrix_rank(candidate_rows)
            if candidate_rank < best_rank:
                point ^= kernel[j]
                rows = candidate_rows
                best_rank = candidate_rank
                accepted.append(j)
                changed = True
                if best_rank == 2:
                    break
        if not changed or best_rank == 2:
            break
    factors = factor_alternating(rows)
    assert 2*len(factors) == best_rank
    actual_sum = {}
    plans = []
    for a,b in factors:
        aa = xor(*[polynomials[j] for j in bits(a)])
        bb = xor(*[polynomials[j] for j in bits(b)])
        actual_sum = xor(actual_sum,mul(aa,bb))
        plans.append(dict(A=[names[j] for j in bits(a)],B=[names[j] for j in bits(b)]))
    offset = initial.solve(target^pack(actual_sum,monomials,n))
    assert offset is not None
    return dict(rec,status='ACTUAL_QUADRATIC_PRODUCT_SUM_RESTORATION_ON_BOUND_CHART',
                paid_products=len(plans),products=plans,
                affine_offset=[initial.descriptors[j] for j in bits(offset)],
                alternating_rank=best_rank,fiber_point_hex=hex(point),
                greedy_improvement_kernel_indices=accepted,minimum_cost_not_claimed=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--gaps',type=int,default=200)
    ap.add_argument('--endpoints-per-gap',type=int,default=8)
    ap.add_argument('--limit',type=int,default=1000)
    ap.add_argument('--max-seconds',type=float,default=480)
    args = ap.parse_args()
    began = time.monotonic()
    native = ROOT/'root/combined1114_selective_qualification_v1/first/emitted/candidate.kmx'
    width_path = ROOT/'root/incumbent_width_v1/REPORT.json'
    census_path = HERE/'q43_idle_recompute_v1/IDLE_GAP_CENSUS.json'
    occupancy_path = width_path.with_name('ALL_INPUT_ALL_HMR_OCCUPANCY.json.gz')
    width = json.loads(width_path.read_text())
    census = json.loads(census_path.read_text())
    with gzip.open(occupancy_path,'rt') as f:
        occupancy = json.load(f)['occupied_owner_masks']
    assert sha(native) == width['native_sha256'] == census['native_sha256']
    windows = width['peak_windows']
    batches = []
    for gap in census['gaps'][:args.gaps]:
        eligible = [(i,a,b) for i,(a,b) in enumerate(windows)
                    if gap['start_cut'] <= a-1 and b <= gap['end_cut']]
        if not eligible:
            continue
        # Deterministic endpoints distributed across the entire eligible range;
        # longest intervals first. Every tested input is from the old panel.
        count = min(args.endpoints_per_gap,len(eligible))
        indices = sorted({round(j*(len(eligible)-1)/max(1,count-1)) for j in range(count)},reverse=True)
        records = []
        first = eligible[0][0]
        entry = eligible[0][1]-1
        for j in indices:
            last,_,exit_cut = eligible[j]
            covered = sum(b-a for a,b in windows[first:last+1])
            assert occupancy[entry].bit_count() <= 43 and occupancy[exit_cut].bit_count() <= 43
            records.append(dict(gap_id=gap['gap_id'],owner=gap['owner'],start_cut=entry,end_cut=exit_cut,
                                original_idle_gap=[gap['start_cut'],gap['end_cut']],
                                first_peak_window=first,last_peak_window=last,covered_peak_cuts=covered,
                                entry_native_occupancy=occupancy[entry].bit_count(),
                                exit_native_occupancy=occupancy[exit_cut].bit_count(),
                                entry_may_be_delayed_to_any_contained_peak_birth_predecessor=True))
        batches.append(records)
    # Round-robin over gaps so a few long negative flags cannot consume the
    # whole batch before the shorter, more constructive intervals are checked.
    declared = [batch[j] for j in range(args.endpoints_per_gap) for batch in batches if j<len(batch)][:args.limit]
    args.out.mkdir(exist_ok=False)
    (args.out/'DECLARED_CASES.json').write_text(json.dumps(dict(notice=NOTICE,cases=declared),indent=2)+'\n')
    with gzip.open(HERE/'window2216_joined_contract_v1/JOINED_BINDINGS.pkl.gz','rb') as f:
        binding = pickle.load(f)
    xs,full = binding['xs'],binding['full']
    program = Program(native.read_text())
    cuts = {x for r in declared for x in (r['start_cut'],r['end_cut'])}
    captured = captures(program,cuts,xs,formal=True)
    records = []
    candidates = []
    for case,row in enumerate(declared):
        if time.monotonic()-began > args.max_seconds:
            break
        assert captured[row['start_cut']][row['owner']] == captured[row['end_cut']][row['owner']]
        assert all(row['owner'] not in o.arguments for o in program.operations[row['start_cut']:row['end_cut']])
        plan = restore(captured[row['end_cut']],row['owner'],full,xs)
        rec = dict(case_id=case,**row,restoration=plan)
        if 'paid_products' in plan:
            k = plan['paid_products']
            rec.update(exact_modelled_added_expected_Toffolis=str(k),all_paid_gate_guard_probabilities=['1']*k,
                       retirement='HMR target into fresh classical owner at start_cut',
                       phase_repayment='Z target under that fresh HMR outcome after exact reconstruction at end_cut',
                       intermediate_phase_changes='None: target has no value or diagonal references inside the interval.',
                       zero_extra_helpers=True,full_domain_identity_and_global_Q43_packing_pending=True)
            candidates.append(rec)
        records.append(rec)
        if case%20==0 or 'paid_products' in plan:
            print(json.dumps(dict(case=case,gap=row['gap_id'],owner=row['owner'],cuts=[row['start_cut'],row['end_cut']],
                                  coverage=row['covered_peak_cuts'],status=plan['status'],products=plan.get('paid_products'),
                                  seconds=time.monotonic()-began)),flush=True)
    # Sequential interval covering: a candidate may retire later than the
    # earliest start. Restore before retiring the next target, so every factor
    # owner is available and no simultaneous missing-control assumption occurs.
    n = len(windows)
    dp = [None]*(n+1);dp[0]=(0,[])
    for start in range(n):
        if dp[start] is None:
            continue
        cost,chosen = dp[start]
        for r in candidates:
            if r['first_peak_window'] <= start <= r['last_peak_window']:
                end = r['last_peak_window']+1
                proposal = (cost+r['restoration']['paid_products'],chosen+[dict(case_id=r['case_id'],
                    delayed_entry_cut=windows[start][0]-1,exit_cut=r['end_cut'],covers_peak_windows=[start,end-1])])
                if dp[end] is None or proposal[0] < dp[end][0]:
                    dp[end] = proposal
    reachable = max(i for i,x in enumerate(dp) if x is not None)
    union = sorted({i for r in candidates for i in range(r['first_peak_window'],r['last_peak_window']+1)})
    report = dict(notice=NOTICE,status='DEFERRED_IDLE_HMR_RECONSTRUCTION_CHART_BATCH',
                  numerical_verification='AGENT_VERIFIED_ROOT_REPLAY_PENDING',qualified=False,
                  source_sha256=sha(__file__),native_sha256=sha(native),width_sha256=sha(width_path),
                  census_sha256=sha(census_path),occupancy_sha256=sha(occupancy_path),
                  original_inputs=len(xs),all_existing_HMR_formal=True,
                  declared_cases=len(declared),completed_cases=len(records),records=records,
                  actual_chart_candidates=len(candidates),candidate_product_histogram=dict(Counter(r['restoration']['paid_products'] for r in candidates)),
                  union_peak_windows=union,union_peak_cuts=sum(windows[i][1]-windows[i][0] for i in union),
                  total_peak_windows=n,total_peak_cuts=width['peak_cut_count'],
                  sequential_cover_longest_prefix_windows=reachable,
                  sequential_cover_prefix_cost_and_plan=dp[reachable],
                  complete_sequential_Q43_model=dp[n],
                  modelled_base_expected_Toffolis='22857/16',Q43_Toffoli_only_extra_budget_strict='22857/688',
                  full_domain_restoration_proof_and_actual_global_recoloring_pending=True,
                  negative_scope='Only complete quadratic reconstruction at each listed endpoint with the target omitted from available owners. No arbitrary cubic or serial nonlinear restoration exclusion.',
                  positive_scope=__doc__,seconds=time.monotonic()-began)
    (args.out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    (args.out/'CANDIDATES.json').write_text(json.dumps(dict(notice=NOTICE,candidates=candidates),indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('records','union_peak_windows','positive_scope')},indent=2))


if __name__ == '__main__':
    main()
