# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Factor the long virtual-q21 phase into literal parity products.

Each old-HMR branch receives one four-parity phase, implemented with an
existing dirty owner by two CCX and two CCZ gates, plus a small exact cubic
sum and free quadratic phases. No added quantum owner is granted.
"""
import argparse
import json
from itertools import combinations, product
from pathlib import Path
from temporal_core import NOTICE, Span, bits, comb, sha
from analyze_q43_long_virtual_phase import mul
from lift_q43_joint_overflow_C_fibers import atomic

HERE=Path(__file__).resolve().parent


def parity(mask):return frozenset(1<<j for j in bits(mask))


def product_polynomial(factors):
    result=frozenset([0])
    for f in factors:result=mul(result,parity(f))
    return result


def support_basis(poly,degree):
    columns={}
    for m in sorted(poly):
        if m.bit_count()!=degree:continue
        for subset in combinations(list(bits(m)),degree-1):
            key=sum(1<<j for j in subset)
            columns[key]=columns.get(key,0)^(m^key)
    S=Span()
    for key in sorted(columns):S.add(columns[key])
    return S.columns


def rref_planes(n,k):
    for pivots in combinations(range(n),k):
        positions=[(r,c) for r,p in enumerate(pivots) for c in range(p+1,n) if c not in pivots]
        for value in range(1<<len(positions)):
            rows=[1<<p for p in pivots]
            for j,(r,c) in enumerate(positions):
                if value>>j&1:rows[r]^=1<<c
            yield rows


def cubic_factors(poly):
    cubic={m for m in poly if m.bit_count()==3}
    if not cubic:return []
    basis=support_basis(cubic,3);n=len(basis);assert n<=6,n
    physical_index={sum(1<<j for j in tri):i for i,tri in enumerate(combinations(range(44),3))}
    encode=lambda terms:sum(1<<physical_index[m] for m in terms if m.bit_count()==3)
    tensor=Span();triples=list(combinations(range(n),3))
    for tri in triples:
        tensor.add(encode(product_polynomial([basis[j] for j in tri])),tri)
    assert len(tensor.columns)==len(triples)
    target=tensor.solve(encode(cubic));assert target is not None
    coordinate_index={sum(1<<j for j in tri):i for i,tri in enumerate(triples)}
    planes={}
    for rows in rref_planes(n,3):
        pp=product_polynomial(rows)
        key=sum(1<<coordinate_index[m] for m in pp if m.bit_count()==3)
        assert key and key not in planes
        planes[key]=rows
    if target in planes:chosen=[target]
    else:
        chosen=next(([a,target^a] for a in planes if target^a in planes),None)
        if chosen is None:
            chosen=next(([a,b,target^a^b] for a in planes for b in planes if target^a^b in planes),None)
    assert chosen is not None
    return [[comb(basis,row) for row in planes[key]] for key in chosen]


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();args.out.mkdir(exist_ok=False)
    source=HERE/'q43_long_virtual_phase_v1/REPORT.json';data=json.loads(source.read_text())
    by={tuple(c['HMR_events']):frozenset(sum(1<<q for q in t) for t in c['quantum_terms']) for c in data['coefficients']}
    branches=[]
    for u,v in product(range(2),repeat=2):
        p=by[(881,)]
        for key,on in [((292,881),u),((846,881),v),((292,846,881),u*v)]:
            if on:p=p^by[key]
        quartic=support_basis(p,4);assert len(quartic)==4
        residual=p^product_polynomial(quartic);assert max(m.bit_count() for m in residual)<=3
        cubics=cubic_factors(residual)
        for factors in cubics:residual=residual^product_polynomial(factors)
        assert max((m.bit_count() for m in residual),default=0)<=2
        future=by[(881,888)]
        if u:future=future^by[(292,881,888)]
        if v:future=future^by[(846,881,888)]
        assert max(m.bit_count() for m in future)<=2
        check=product_polynomial(quartic)
        for ff in cubics:check^=product_polynomial(ff)
        check^=residual;assert check==p
        branches.append(dict(outcomes={'292':u,'846':v,'881':1},probability='1/8',
            quartic_factors=[[f'q{q}' for q in bits(mask)] for mask in quartic],
            quartic_factor_masks_hex=[hex(mask) for mask in quartic],
            cubic_products=[[[f'q{q}' for q in bits(mask)] for mask in ff] for ff in cubics],
            cubic_factor_masks_hex=[[hex(mask) for mask in ff] for ff in cubics],
            free_phase_terms=[[f'q{q}' for q in bits(m)] for m in sorted(residual)],
            free_future_HMR_phase_terms=[[f'q{q}' for q in bits(m)] for m in sorted(future)],
            future_HMR_outcome='b197',dirty_owner='q1',
            paid_gate_count=4+len(cubics),paid_quartic_implementation=['CCX A B q1','CCZ q1 C D','CCX A B q1','CCZ q1 C D']))
    report=dict(notice=NOTICE,status='EXACT_UNIVERSAL_DIRTY_OWNER_PHASE_PLANS_CONSTRUCTED',
                numerical_verification='AGENT_VERIFIED_ROOT_REPLAY_PENDING',qualified=False,
                source_sha256=sha(__file__),phase_debt_sha256=sha(source),native_sha256=data['native_sha256'],
                interval=data['interval'],every_branch_polynomial_identity_checked=True,
                branches=branches,weighted_phase_gate_cost_numerator_over8=sum(r['paid_gate_count'] for r in branches),
                dirty_owner_returned_exactly=True,extra_quantum_owners=0,
                native_removed_gate_cost_not_yet_subtracted=True,whole_emitter_and_full_domain_phase_proof_owed=True)
    atomic(args.out/'REPORT.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='branches'}))
    print(json.dumps([dict(outcomes=r['outcomes'],cubic_products=len(r['cubic_products']),paid_gate_count=r['paid_gate_count']) for r in branches]))


if __name__=='__main__':main()
