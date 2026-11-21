# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Regenerate fifteen exact retained-native-product decoder frames.

The captured product is prepared by free copies of actual native CCX deltas.
The indexed first AND is a NEW decoder product, so none of the older no-G
three-product first-plane exclusions is inherited.
"""
import argparse
import gzip
import hashlib
import json
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from gf2 import NOTICE, Span, affine_preimage, combine

HERE=Path(__file__).resolve().parent
TABLE_SHA='33df7dead4957dc34f5262913d94e7bc3f1b9117820bfb229860df3347d4e7c8'
BASE_NAMES=[f'D{i}' for i in range(5,13)]+[f'S{i}' for i in range(6)]+['v4','v5']
ALL_NAMES=[f'D{i}' for i in range(13)]+[f'S{i}' for i in range(6)]+[f'v{i}' for i in range(6)]+['A7']
PHYSICAL={'D0':16,'D1':17,'D2':18,'D3':19,'D4':43,'D5':29,'D6':27,'D7':9,
          'D8':20,'D9':31,'D10':33,'D11':26,'D12':28,
          'S0':32,'S1':30,'S2':0,'S3':11,'S4':13,'S5':34,
          'v0':39,'v1':37,'v2':12,'v3':38,'v4':14,'v5':15,'A7':35,'G':10}
PRODUCTS=[
    dict(label='g0',operation=28056,target='q41',A=['D8','D11','D12','S0','S1'],B=['D10','D11','D12']),
    dict(label='g1',operation=28102,target='q40',A=['D8','S1'],B=['D10','D12','S1']),
    dict(label='g2',operation=28126,target='q13',A=['D8','D10','D12','S1'],B=['D11','D12','S0']),
    dict(label='g3',operation=28197,target='q34',A=['D9','D12'],B=['D11','D12'])]


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_gz(path,data):
    with Path(path).open('wb') as f:
        with gzip.GzipFile(fileobj=f,mode='wb',mtime=0,filename='') as z:
            z.write((json.dumps(data,sort_keys=True,separators=(',',':'))+'\n').encode())


def component():
    path=HERE/'reference/component_table.json';assert digest(path)==TABLE_SHA
    data=json.loads(path.read_text());full=(1<<4096)-1
    truth=lambda seq,j:sum(((int(v)>>j)&1)<<i for i,v in enumerate(seq))
    val={f'D{i}':truth(data['D'],i) for i in range(13)}
    val.update({f'S{i}':truth([data['S'][v>>6] for v in range(4096)],i) for i in range(7)})
    val.update({f'v{i}':truth(range(4096),i) for i in range(6)})
    val['A7']=truth([data['A'][v>>6] for v in range(4096)],7)
    for row in PRODUCTS:
        val[row['label']]=combine([val[n] for n in row['A']],(1<<len(row['A']))-1)&combine([val[n] for n in row['B']],(1<<len(row['B']))-1)
    return full,val


def degree_span(controls,full,degree):
    S=Span();S.add(full)
    for v in controls:S.add(v)
    for k in range(2,degree+1):
        for inds in combinations(range(len(controls)),k):
            v=full
            for j in inds:v&=controls[j]
            S.add(v)
    return S


def regenerate(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    config=json.loads((HERE/'JOB_CONFIG.json').read_text())
    full,val=component();F=val['A7'];names=BASE_NAMES+['G']
    base=degree_span([val[n] for n in BASE_NAMES],full,1)
    extra=degree_span([val[n] for n in BASE_NAMES]+[val[n] for n in ['S6','v3','D3']],full,1)
    group=Span()
    for j in range(4):assert group.add(base.normal(val[f'g{j}']))
    assert len(group.columns)==4
    no_named_equivalence={name:group.solve(base.normal(val[name])) is None for name in ['S6','v3','D3']}
    assert all(no_named_equivalence.values())
    union=degree_span([val[n] for n in BASE_NAMES]+[val[n] for n in ['S6','v3','D3']]+[val[f'g{j}'] for j in range(4)],full,1)
    total=0;cases=[];residues=set()
    for mask in config['selected_parity_masks']:
        ci=mask-1;G=combine([val[f'g{j}'] for j in range(4)],mask)
        residue=base.normal(G);assert residue and residue not in residues;residues.add(residue)
        values=dict(val,G=G);groups={}
        for v in range(4096):
            key=sum(((values[n]>>v)&1)<<j for j,n in enumerate(names))
            rows=groups.setdefault(key,[])
            if rows:assert (F>>rows[0]&1)==(F>>v&1)
            rows.append(v)
        ordered=sorted(groups.items(),key=lambda item:item[1][0]);reps=[rows[0] for _,rows in ordered]
        assert len(reps)==434
        compress=lambda v:sum(((v>>r)&1)<<j for j,r in enumerate(reps))
        controls=[compress(values[n]) for n in names];target=compress(F);ones=(1<<len(reps))-1
        I=degree_span(controls,ones,1);Q=degree_span(controls,ones,2)
        C3=degree_span(controls,ones,3);C4=degree_span(controls,ones,4)
        assert len(I.columns)==18 and Q.solve(target) is None
        _,kernel,rank=affine_preimage([Q.normal(target&v) for v in I.columns],0)
        count=((1<<17)-1)*((1<<17)-2)//6
        record=dict(notice=NOTICE,case_id=ci,retained_parity_mask=mask,
                    retained_native_products=[f'g{j}' for j in range(4) if mask>>j&1],
                    control_names=names,control_physical_owners={n:f'q{PHYSICAL[n]}' for n in names},
                    component_rows=4096,signature_rows=len(reps),control_truth_hex=list(map(hex,controls)),
                    target_truth_hex=hex(target),target='original_A7',target_owner='q35',
                    affine_rank=len(I.columns),quadratic_rank=len(Q.columns),cubic_rank=len(C3.columns),quartic_rank=len(C4.columns),
                    target_in_cubic=C3.solve(target) is not None,target_in_quartic=C4.solve(target) is not None,
                    base_multiplier_rank=rank,base_kernel_masks_hex=list(map(hex,kernel)),
                    global_label_start=str(total),raw_plane_labels=str(count),stage_A_columns=17+rank+1,
                    retained_control_added_ANDs='0',phase_expected_Toffolis='0',entry_inverse_products=0,
                    modelled_current_total=str(Fraction(config['source_parent_expected_Toffolis'])+3),
                    no_old_plane_exclusion_transfer=True,
                    rows=[dict(signature=key,representative_component_v=vs[0],all_component_v=vs,target=F>>vs[0]&1) for key,vs in ordered])
        file=f'PARITY_{mask:02d}.json.gz';write_gz(out/file,record)
        cases.append(dict(case_id=ci,retained_parity_mask=mask,dimension=17,start=total,count=count,
                          signature_rows=len(reps),input=file,input_sha256=digest(out/file)))
        total+=count
    assert str(total)==config['raw_expected_plane_labels'] and len(cases)==15
    index=dict(notice=NOTICE,job_id=config['job_id'],cases=cases,total_labels=str(total),
               no_static_label_exclusions=True,all_labels_explicitly_open_for_GPU=True,
               parity_span_dimension_mod_base=4,distinct_retained_control_extensions=15,
               no_parity_equivalent_to_named_existing_extra=no_named_equivalence,
               base_affine_rank=len(base.columns),base_plus_S6_v3_D3_rank=len(extra.columns),
               base_plus_S6_v3_D3_all_four_native_products_rank=len(union.columns),
               old_two_product_history_bound_is_not_a_three_product_plane_skip=True,
               exact_case_order='Nonzero mask1..15 of (g0,g1,g2,g3), least significant bit is g0; case_id=mask-1.')
    (out/'INDEX.json').write_text(json.dumps(index,indent=2,sort_keys=True)+'\n')
    return dict(notice=NOTICE,status='DETERMINISTIC_RETAINED_NATIVE_PARITY_INPUTS_REGENERATED',job_id=config['job_id'],
                case_count=len(cases),total_plane_labels=str(total),source_sha256=digest(__file__),
                files={p.name:digest(p) for p in sorted(out.iterdir())})


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True)
    print(json.dumps(regenerate(ap.parse_args().out),sort_keys=True))
