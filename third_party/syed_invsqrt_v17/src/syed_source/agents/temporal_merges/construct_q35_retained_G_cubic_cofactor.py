# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Construct F=Q0+C*Q1 over full existing owners and one retained native G.

Only the declared low-support C family is visited. Complete quadratic
solution fibers are saved for every image-positive case. Rank improvement
is a deterministic heuristic, so failure to reach the budget is OPEN.
The compact17-control GPU first-plane domain is not scanned here.
"""
import argparse
import gzip
import json
import sys
import time
from itertools import combinations
from pathlib import Path

HERE=Path(__file__).resolve().parent
PACKAGE=HERE/'q43_q35_retained_native_parities_gpu_job_v1'
sys.path.insert(0,str(PACKAGE))
from gf2 import NOTICE,Span,affine_preimage,combine,bits,separating_dual
from regenerate_inputs import component,degree_span,digest,write_gz,PHYSICAL

NAMES=[f'D{i}' for i in range(13)]+[f'S{i}' for i in range(6)]+[f'v{i}' for i in range(6)]+['G']


def matrix_rows(n,pairs,bivector):
    rows=[0]*n
    for k in bits(bivector):
        i,j=pairs[k];rows[i]^=1<<j;rows[j]^=1<<i
    return rows


def matrix_rank(rows):
    basis={}
    for row in rows:
        while row:
            p=row.bit_length()-1
            if p in basis:row^=basis[p]
            else:basis[p]=row;break
    return len(basis)


def factor_alternating(rows):
    rows=list(rows);answer=[]
    while any(rows):
        p=next(i for i,row in enumerate(rows) if row);q=(rows[p]&-rows[p]).bit_length()-1
        a,b=rows[p],rows[q];answer.append((a,b))
        for i in range(len(rows)):rows[i]^=(b if a>>i&1 else 0)^(a if b>>i&1 else 0)
        assert not rows[p] and not rows[q]
    return answer


def quadratic_plan(n,pairs,coefficient,controls,full):
    linear=coefficient&((1<<(n+1))-1);M=matrix_rows(n,pairs,coefficient>>(n+1))
    products=factor_alternating(M);value=combine([full]+controls,linear)
    for a,b in products:
        linear^=(a&b)<<1
    expected=combine([full]+controls,coefficient&((1<<(n+1))-1))
    for k in bits(coefficient>>(n+1)):
        i,j=pairs[k];expected^=controls[i]&controls[j]
    value=combine([full]+controls,linear)
    for a,b in products:value^=combine(controls,a)&combine(controls,b)
    assert value==expected
    return dict(products=[dict(A_mask=hex(a),B_mask=hex(b),A=[NAMES[i] for i in bits(a)],B=[NAMES[i] for i in bits(b)]) for a,b in products],
                affine_mask=hex(linear),affine_terms=[(['constant']+NAMES)[i] for i in bits(linear)],
                product_count=len(products),truth_hex=hex(value),coefficient_mask_hex=hex(coefficient))


def improve(point,kernel,n,pairs,columns_per_form,max_sweeps,deadline):
    width=len(pairs);qmask=(1<<width)-1;affine=n+1
    def project(x):return ((x>>affine)&qmask)|(((x>>(columns_per_form+affine))&qmask)<<width)
    def cost(x):
        return (matrix_rank(matrix_rows(n,pairs,x&qmask))+matrix_rank(matrix_rows(n,pairs,x>>width)))//2+1
    S=Span();directions=[]
    for k in kernel:
        q=project(k)
        if S.add(q):directions.append((q,k))
    current=point;projected=project(current);best=cost(projected);start=best;steps=[];checked=0
    for sweep in range(max_sweeps):
        if time.monotonic()>deadline:break
        choice=None
        for i,(q,k) in enumerate(directions):
            value=cost(projected^q);checked+=1
            if value<best:best=value;choice=(q,k,[i])
        if choice is None:
            # A bounded deterministic two-direction improvement. All original
            # fiber directions remain saved; no rank-minimum claim is made.
            for i,j in combinations(range(min(96,len(directions))),2):
                if time.monotonic()>deadline:break
                q=directions[i][0]^directions[j][0]
                value=cost(projected^q);checked+=1
                if value<best:best=value;choice=(q,directions[i][1]^directions[j][1],[i,j])
        if choice is None:break
        projected^=choice[0];current^=choice[1];steps.append(dict(sweep=sweep,directions=choice[2],cost=best))
        if best<=6:break
    assert cost(projected)==best
    return current,dict(initial_upper_cost=start,best_actual_upper_cost=best,projected_fiber_dimension=len(directions),
                        rank_candidates_checked=checked,improvements=steps,heuristic_only=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--C-support',type=int,default=2);ap.add_argument('--max-seconds',type=float,default=240)
    ap.add_argument('--rank-sweeps',type=int,default=6);ap.add_argument('--parities',nargs='+',type=int,default=list(range(1,16)))
    args=ap.parse_args();args.out.mkdir(exist_ok=False);began=time.monotonic();deadline=began+args.max_seconds
    full,values=component();F=values['A7'];base=[values[n] for n in NAMES[:-1]];n=len(NAMES)
    pairs=list(combinations(range(n),2));M=1+n+len(pairs)
    frames=[];positives=[];winner=None;timed_out=False
    for parity in args.parities:
        if time.monotonic()>deadline:timed_out=True;break
        G=combine([values[f'g{j}'] for j in range(4)],parity);controls=base+[G]
        I=degree_span(controls,full,1);Q=degree_span(controls,full,2);C3=degree_span(controls,full,3)
        row=dict(retained_parity_mask=parity,affine_rank=len(I.columns),quadratic_rank=len(Q.columns),cubic_rank=len(C3.columns),
                 target_cubic=C3.solve(F) is not None,C_records=[])
        if not row['target_cubic']:
            row.update(status='NO_CUBIC_COFACTOR_FORM_IN_THIS_EXACT_FRAME',noncubic_character=list(bits(separating_dual(C3.columns,F))))
            frames.append(row);continue
        _,km,rank=affine_preimage([C3.normal(F&v) for v in I.columns],0)
        K=Span()
        for k in km:K.add(k)
        row.update(cubic_multiplier_rank=rank,complete_cubic_multiplier_kernel_masks_hex=list(map(hex,km)))
        # Complements have the same image but can have different rank costs.
        # Both orientations are explicitly optimized for every image pass.
        masks=[sum(1<<(i+1) for i in inds) for w in range(1,args.C_support+1) for inds in combinations(range(n),w)]
        masks=[m for m in masks if K.solve(m) is not None]
        row['declared_C_count']=len(masks)
        monomials=[full]+controls+[controls[i]&controls[j] for i,j in pairs]
        for cmask in masks:
            if time.monotonic()>deadline:timed_out=True;break
            C=combine(I.columns,cmask);W=Span()
            for q in Q.columns:W.add(q)
            for q in Q.columns:W.add(q&C)
            record=dict(C_affine_mask=hex(cmask),C_terms=[(['constant']+NAMES)[i] for i in bits(cmask)],
                        image_rank=len(W.columns),image_pass=W.solve(F) is not None)
            if not record['image_pass']:
                # Compact exact character for only this declared C; no
                # unrestricted-C or rank-fiber closure is inferred.
                record['separating_component_v']=list(bits(separating_dual(W.columns,F)))
                row['C_records'].append(record);continue
            point,kernel,wrank=affine_preimage(monomials+[C&q for q in monomials],F)
            assert point is not None and wrank==len(W.columns)
            fiber=dict(notice=NOTICE,retained_parity_mask=parity,C_affine_mask=hex(cmask),
                       full_component_rows=4096,control_names=NAMES,columns_per_quadratic_form=M,
                       monomial_order='constant; controls in declared order; unordered control pairs lexicographically',
                       complete_point_hex=hex(point),complete_kernel_masks_hex=list(map(hex,kernel)),complete_kernel_dimension=len(kernel),
                       image_rank=wrank,complement_transform='(Q0,Q1) -> (Q0+Q1,Q1)',complete_fiber_preserved=True)
            file=f'PARITY_{parity:02d}_C_{cmask:x}.json.gz';write_gz(args.out/file,fiber)
            record.update(complete_fiber_file=file,complete_fiber_sha256=digest(args.out/file),complete_kernel_dimension=len(kernel),orientations=[])
            for complement in (0,1):
                flip=lambda x:x^((x>>M)&((1<<M)-1))
                pp=flip(point) if complement else point;kk=[flip(k) for k in kernel] if complement else kernel
                solved,optimization=improve(pp,kk,n,pairs,M,args.rank_sweeps,deadline)
                q0=quadratic_plan(n,pairs,solved&((1<<M)-1),controls,full)
                q1=quadratic_plan(n,pairs,solved>>M,controls,full)
                actualC=C^(full if complement else 0)
                assert int(q0['truth_hex'],16)^(actualC&int(q1['truth_hex'],16))==F
                actual_cost=q0['product_count']+q1['product_count']+1
                assert actual_cost==optimization['best_actual_upper_cost']
                plan=dict(retained_parity_mask=parity,C_affine_mask=hex(cmask^complement),
                          C_terms=[(['constant']+NAMES)[i] for i in bits(cmask^complement)],
                          Q0=q0,Q1=q1,new_ANDs=actual_cost,physical_G_owner='q10',quadratic_helper_owner='q40',output_owner='q35',
                          decoder_peak_bound=42,complete_component_identity=True,actual_native_emission_and_proof_pending=True)
                record['orientations'].append(dict(complement=complement,optimization=optimization,actual_value_plan=plan))
                if actual_cost<=6:winner=plan;break
            positives.append(dict(retained_parity_mask=parity,**record));row['C_records'].append(record)
            print(json.dumps(dict(parity=parity,C=hex(cmask),fiber=len(kernel),best=min(o['actual_value_plan']['new_ANDs'] for o in record['orientations']),seconds=time.monotonic()-began)),flush=True)
            if winner:break
        row['completed_C_count']=len(row['C_records']);row['complete_declared_C_images']=len(row['C_records'])==len(masks)
        row['status']='ACTUAL_COMPONENT_DECODER_WITHIN_SIX_ANDS' if winner else 'BOUNDED_C_IMAGE_AND_HEURISTIC_RANK_RESULTS'
        frames.append(row)
        (args.out/f'FRAME_{parity:02d}.json').write_text(json.dumps(dict(notice=NOTICE,**row),indent=2,sort_keys=True)+'\n')
        print(json.dumps(dict(parity=parity,completed=len(row['C_records']),declared=len(masks),positive=sum(r['image_pass'] for r in row['C_records']),seconds=time.monotonic()-began)),flush=True)
        if winner or timed_out:break
    report=dict(notice=NOTICE,status='ACTUAL_COMPONENT_DECODER_WITHIN_SIX_ANDS' if winner else 'CONSTRUCTIVE_SEARCH_INCOMPLETE_OR_NO_WITHIN_BUDGET_WITNESS',
                source_sha256=digest(__file__),native_sha256=json.loads((PACKAGE/'JOB_CONFIG.json').read_text())['native_sha256'],
                base_expected_Toffolis='5845/4',component_rows=4096,full_existing_control_names=NAMES,
                control_physical_owners={n:f'q{PHYSICAL[n]}' for n in NAMES},declared_parities=args.parities,
                C_support_limit=args.C_support,rank_sweeps=args.rank_sweeps,positive_fibers=len(positives),
                complete_positive_fibers_preserved=True,rank_failure_never_negative=True,timed_out=timed_out,
                frames=frames,actual_value_witness=winner,qualified=False,numerical_verification='AGENT_VERIFIED_ROOT_REPLAY_PENDING',
                compact_GPU_first_plane_domain_not_scanned=True,
                cost_model='rank(M0)/2 + rank(M1)/2 +1, with zero-AND retained-G capture and free quadratic HMR cleanup.',
                outside_scope='Dense C beyond the stated support; unsolved lower-rank points of any saved complete quadratic fiber; other serial circuits.',
                seconds=time.monotonic()-began)
    (args.out/'REPORT.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('frames','control_physical_owners','actual_value_witness')},sort_keys=True),flush=True)


if __name__=='__main__':main()
