# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Price exact idle-gap retirement/reconstruction across Q44 peak cuts.

The qualified emitted incumbent is fixed. A target owner has no reference,
including diagonal reads, inside each declared idle gap. Try affine removal
or a fresh HMR with quadratic Clifford feedback at its left cut, then an
affine or one-product reconstruction at its next use. All original HMRs are
formal on the unchanged original35184-input necessary chart. A positive
still owes full-domain proof, physical Q43 recoloring and compatible global
gap selection. Negative phase/value image tests only close this local scope.
"""
from pathlib import Path
from itertools import combinations
from collections import Counter
import argparse
import gzip
import json
import pickle
import sys
import time
from temporal_core import NOTICE, Program, Span, captures, mul, comb, bits, sha, affine_preimage
from screen_initial_cubic_outputs import dual_from_basis

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'restored/research_v9/second_seed_and_phases'))
from fixed_factor_plucker import affine_forms, complete_bivector


def pack(poly,monomials,n):
    return sum(poly.get(m,0) << (n*j) for j,m in enumerate(monomials))


def frame_test(frame,owner,full,xs,out,need_factor):
    physical=[('constant',{0:full})]+[(f'q{i}',frame[f'q{i}']) for i in range(44) if f'q{i}'!=owner]
    polys=[p for _,p in physical]
    pairs=list(combinations(range(len(polys)),2))
    products=[mul(polys[i],polys[j]) for i,j in pairs]
    monomials=sorted({m for p in polys+products+[frame[owner]] for m in p})
    n=len(xs)
    initial=Span()
    for (name,p) in physical:
        initial.add(pack(p,monomials,n),name)
    target=pack(frame[owner],monomials,n)
    affine=initial.solve(target)
    rec=dict(available_affine_rank=len(initial.columns),available_basis=initial.descriptors,
        formal_HMR_monomials=[list(bits(m)) for m in monomials],target_owner=owner,
        affine=affine is not None)
    if affine is not None:
        rec.update(status='ACTUAL_AFFINE_IDENTITY_ON_BOUND_CHART',
            affine_expression=[initial.descriptors[j] for j in bits(affine)],
            added_expected_value_Toffolis='0')
        return rec
    controls=initial.columns[1:]
    # Rebuild products in formal Boolean polynomials, not bitwise products of
    # flattened HMR coefficient blocks. Every coefficient remains shared.
    lookup=dict(physical)
    control_polys=[lookup[q] for q in initial.descriptors[1:]]
    edges=list(combinations(range(len(controls)),2))
    values=[pack(mul(control_polys[i],control_polys[j]),monomials,n) for i,j in edges]
    Q=initial.copy()
    for (i,j),v in zip(edges,values):
        Q.add(v,[initial.descriptors[1:][i],initial.descriptors[1:][j]])
    coefficient=Q.solve(target)
    rec['complete_quadratic_rank']=len(Q.columns)
    if coefficient is None:
        dual=dual_from_basis(Q,target)
        terms=[]
        for j,m in enumerate(monomials):
            local=(dual >> (n*j))&full
            if local:
                terms.append(dict(HMR_events=list(bits(m)),original_inputs=[int(xs[k]) for k in bits(local)]))
        rec.update(status='COMPLETE_NEGATIVE_QUADRATIC_IMAGE',literal_character=terms,
            target_pairing=1,all_quadratic_pairings=0)
        return rec
    rec['quadratic_expression']=[Q.descriptors[j] for j in bits(coefficient)]
    if not need_factor:
        rec.update(status='ACTUAL_HMR_WITH_QUADRATIC_CLIFFORD_FEEDBACK_ON_BOUND_CHART',
            fresh_HMR_outcomes=1,added_expected_phase_Toffolis='0')
        return rec
    point,kernel,rank=affine_preimage([initial.normal(v) for v in values],initial.normal(target))
    assert point is not None
    result=complete_bivector(len(controls),affine_forms(point,kernel,len(edges)),len(kernel),max_enumerate=16)
    cp=out/'RESTORATION_FACTOR_FIBER.json.gz'
    with gzip.open(cp,'wt',compresslevel=6) as f:
        json.dump(dict(notice=NOTICE,owners=initial.descriptors[1:],point_hex=hex(point),
            kernel_hex=list(map(hex,kernel)),formal_HMR_monomials=rec['formal_HMR_monomials'],result=result),f)
    rec.update(status=result['status'],complete_product_fiber_dimension=len(kernel),
        certificate=cp.name,certificate_sha256=sha(cp))
    if result['status']=='DECOMPOSABLE_WITNESS':
        am,bm=result['factor_masks']
        aa={};bb={}
        from temporal_core import xor
        for j in bits(am):aa=xor(aa,control_polys[j])
        for j in bits(bm):bb=xor(bb,control_polys[j])
        product=pack(mul(aa,bb),monomials,n)
        offset=initial.solve(target^product)
        assert offset is not None
        rec.update(A=[initial.descriptors[1:][j] for j in bits(am)],
            B=[initial.descriptors[1:][j] for j in bits(bm)],
            affine_offset=[initial.descriptors[j] for j in bits(offset)],
            exact_paid_gate_guard_probability='1',added_expected_value_Toffolis='1')
    return rec


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--limit',type=int,default=100)
    ap.add_argument('--max-seconds',type=float,default=480)
    args=ap.parse_args()
    started=time.monotonic()
    native=ROOT/'root/combined1114_selective_qualification_v1/first/emitted/candidate.kmx'
    wp=ROOT/'root/incumbent_width_v1/REPORT.json'
    lp=wp.with_name('VALUE_LIFETIMES.json')
    width=json.loads(wp.read_text())
    assert sha(native)==width['native_sha256']=='3ced9b53d9a499037527c6097030e8699bfbdcdfc17342fc2647247ad99c6259'
    program=Program(native.read_text())
    assert len(program.operations)==40536
    peaks=set(c for a,b in width['peak_windows'] for c in range(a,b))
    uses={f'q{i}':[] for i in range(44)}
    for i,op in enumerate(program.operations):
        for q in set(op.arguments):
            if q in uses:uses[q].append(i)
    gaps=[]
    for lifetime in json.loads(lp.read_text())['intervals']:
        q=lifetime['owner'];a=lifetime['first_occupied_cut'];b=lifetime['first_zero_cut']
        touched=[i for i in uses[q] if a-1 <= i < b]
        if a==0:touched=[-1]+touched
        for left,right in zip(touched,touched[1:]):
            covered=sorted(i for i in peaks if left < i < right)
            if not covered:continue
            gaps.append(dict(gap_id=len(gaps),owner=q,start_cut=left+1,end_cut=right,
                peak_cuts=len(covered),covered_peak_cuts=covered,birth=lifetime['birth_operation'],
                birth_kind=lifetime.get('birth_kind'),birth_arguments=lifetime.get('birth_arguments'),
                last_touch=None if left<0 else [program.operations[left].kind,list(program.operations[left].arguments)],
                next_touch=[program.operations[right].kind,list(program.operations[right].arguments)]))
    gaps.sort(key=lambda r:(-r['peak_cuts'],r['start_cut'],r['owner']))
    selected=gaps[:args.limit]
    args.out.mkdir(exist_ok=False)
    (args.out/'IDLE_GAP_CENSUS.json').write_text(json.dumps(dict(notice=NOTICE,native_sha256=sha(native),
        total_peak_touching_idle_gaps=len(gaps),gaps=gaps),indent=2)+'\n')
    bp=HERE/'window2216_joined_contract_v1/JOINED_BINDINGS.pkl.gz'
    with gzip.open(bp,'rb') as f:old=pickle.load(f)
    xs=old['xs'];full=old['full']
    cuts={cut for r in selected for cut in (r['start_cut'],r['end_cut'])}
    captured=captures(program,cuts,xs,formal=True,include_classical=True)
    with gzip.open(args.out/'NATIVE_CAPTURES.pkl.gz','wb',compresslevel=3) as f:
        pickle.dump(dict(notice=NOTICE,native_sha256=sha(native),xs=xs,captures=captured),f,protocol=5)
    records=[]
    for rank,row in enumerate(selected):
        if time.monotonic()-started>args.max_seconds:break
        directory=args.out/f"GAP_{row['gap_id']:05d}"
        directory.mkdir()
        assert captured[row['start_cut']][row['owner']]==captured[row['end_cut']][row['owner']]
        left=frame_test(captured[row['start_cut']],row['owner'],full,xs,directory,False)
        right=frame_test(captured[row['end_cut']],row['owner'],full,xs,directory,True)
        good_left=left['status'] in ('ACTUAL_AFFINE_IDENTITY_ON_BOUND_CHART','ACTUAL_HMR_WITH_QUADRATIC_CLIFFORD_FEEDBACK_ON_BOUND_CHART')
        good_right=right['status'] in ('ACTUAL_AFFINE_IDENTITY_ON_BOUND_CHART','DECOMPOSABLE_WITNESS')
        rec=dict(**row,priority_rank=rank,left_retirement=left,right_reconstruction=right,
            status='ACTUAL_LOCAL_RETIRE_RECONSTRUCT_IDENTITIES_REQUIRE_FULL_PROOF_AND_Q43_PACKING'
                if good_left and good_right else 'LOCAL_FREE_RETIRE_ONE_PRODUCT_RESTORE_NOT_ESTABLISHED',
            added_expected_Toffolis=right.get('added_expected_value_Toffolis') if good_left and good_right else None,
            guard_probability='1' if good_left and good_right and not right.get('affine') else '0' if good_left and good_right else None)
        records.append(rec)
        (directory/'REPORT.json').write_text(json.dumps(dict(notice=NOTICE,**rec),indent=2)+'\n')
        print(json.dumps(dict(rank=rank,gap=row['gap_id'],owner=row['owner'],cuts=[row['start_cut'],row['end_cut']],
            coverage=row['peak_cuts'],left=left['status'],right=right['status'],cost=rec['added_expected_Toffolis'],
            seconds=time.monotonic()-started)),flush=True)
    actual=[r for r in records if r['added_expected_Toffolis'] is not None]
    covered=sorted({c for r in actual for c in r['covered_peak_cuts']})
    report=dict(notice=NOTICE,status='Q43_IDLE_RECOMPUTE_LOCAL_CHART_BATCH',
        numerical_verification='AGENT_VERIFIED_ROOT_REPLAY_PENDING',source_sha256=sha(__file__),native_sha256=sha(native),
        qualified_incumbent_circuit_sha256=width['qualified_incumbent_circuit_sha256'],
        width_map_sha256=sha(wp),lifetimes_sha256=sha(lp),original_inputs=len(xs),all_HMR_formal=True,
        total_idle_gaps=len(gaps),declared_selected_gaps=len(selected),completed=len(records),records=records,
        actual_local_candidates=len(actual),candidate_cost_histogram=dict(Counter(r['added_expected_Toffolis'] for r in actual)),
        union_peak_cuts_covered=len(covered),total_peak_cuts=len(peaks),all_peak_cuts_covered=len(covered)==len(peaks),
        compatible_global_interval_selection_not_yet_checked=True,
        modelled_base_expected_Toffolis='22857/16',Q43_Toffoli_only_extra_budget_strict='22857/688',
        phase_and_full_domain_proof_and_global_Q43_recoloring_pending=True,qualified=False,
        scope=__doc__,seconds=time.monotonic()-started)
    (args.out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
