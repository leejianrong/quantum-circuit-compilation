# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Compose the proved q31 retirement after explicitly matching bank ownership."""
from pathlib import Path
import argparse, gzip, json, shlex
from map_incumbent_width import BASE, NOTICE, Program, sha

def signature(o,mp):
    return o.kind,tuple(mp.get(a,a) for a in o.arguments),mp.get(o.condition,o.condition),o.half_turns

def operation_lines(lines):
    result=[]
    for i,line in enumerate(lines):
        words=shlex.split(line,comments=True)
        if words and words[0] not in ('REGISTER','APPEND_TO_REGISTER','INFO_TAG','DEBUG_PRINT'):result.append(i)
    return result

def mapped_literal(text,mp,old_bit,new_bit):
    return ' '.join(new_bit if s==old_bit else mp.get(s,s) for s in text.split())

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();assert not args.out.exists()
    parent=BASE/'agents/paid_helper/phase_outer_parity_retirement_v1b/candidate_text.kmx'
    ref=BASE/'root/q43_phase_and_late_width_v1/candidate_text.kmx'
    patch=BASE/'agents/temporal_merges/q43_later_q31_native_v1/REPORT.json'
    bank=BASE/'agents/paid_helper/fourth_bank_deferred_phase_v1/REPORT.json'
    assert sha(parent)=='bead9766a2290ec7a1264855d011ac0b552d753090344db6baa2db49fbc13b8f'
    assert sha(ref)=='501f1d90c3a82c45c6a60d6ec478bd89c91ebc3f72e847cc56f8d4182a014e43'
    component=json.loads(patch.read_text());assert component['candidate_native_sha256']=='96113363305204abb756c1d31fe833c5ef3853b29de41cc19e6a338202e3e837'
    assert component['original_research_interval']==[27071,27700] and component['exact_added_expected_Toffolis']=='3'
    permutation=json.loads(bank.read_text())['endpoint_permutation']
    assert permutation=={'q7':'q21','q8':'q26','q21':'q7','q26':'q8'}
    text=parent.read_text();p=Program(text);r=Program(ref.read_text());a0,b0=component['original_research_interval']
    wanted=[signature(o,permutation) for o in r.operations[a0:b0]];actual=[signature(o,{}) for o in p.operations]
    matches=[i for i,s in enumerate(actual) if s==wanted[0] and actual[i:i+len(wanted)]==wanted]
    assert len(matches)==1,matches;a=matches[0];b=a+len(wanted)
    assert all(permutation.get('q31','q31') not in o.arguments for o in p.operations[a:b])
    depth=0;depths=[]
    for o in p.operations:depths.append(depth);depth+=(o.kind=='PUSH_CONDITION')-(o.kind=='POP_CONDITION')
    assert depth==0 and depths[a]==depths[b]==0
    old_bit=component['fresh_outcome'];new_bit='b'+str(1+max(int(q[1:]) for q in p.wires if q.startswith('b')))
    assert new_bit not in p.wires
    inserts={a:[mapped_literal(x,permutation,old_bit,new_bit) for x in component['retirement_gates']],b:[mapped_literal(x,permutation,old_bit,new_bit) for x in component['restoration_gates']]}
    assert inserts[a]==[f'HMR q31 {new_bit}'] and sum(x.startswith('CCX ') for x in inserts[b])==3
    lines=text.splitlines();locations=operation_lines(lines);assert len(locations)==len(p.operations);by_line={v:i for i,v in enumerate(locations)}
    out=['# '+NOTICE];origins=[];old_to_new={}
    for j,line in enumerate(lines):
        if j in by_line:
            i=by_line[j];old_to_new[i]=len(origins)
            out.extend(inserts.get(i,[]));origins.extend([None]*len(inserts.get(i,[])));origins.append(i)
        out.append(line)
    old_to_new[len(p.operations)]=len(origins)
    changed='\n'.join(out)+'\n';c=Program(changed)
    assert c.registers==p.registers and len(c.operations)==len(p.operations)+42 and c.measurements==p.measurements+1
    assert c.wires-p.wires=={new_bit}
    # The emitted existing interval is preserved byte for byte; only its two endpoints gain gates.
    assert [signature(c.operations[i],{}) for i,o in enumerate(origins) if o is not None]==actual
    args.out.mkdir(parents=True);dest=args.out/'candidate_text.kmx';dest.write_text(changed)
    mapping=dict(notice=NOTICE,parent_native_sha256=sha(parent),output_native_sha256=sha(dest),output_to_parent_operation=origins,old_cut_to_new_cut=old_to_new)
    (args.out/'OPERATION_MAP.json.gz').write_bytes(gzip.compress(json.dumps(mapping,separators=(',',':')).encode(),mtime=0))
    report=dict(notice=NOTICE,status='ROOT_EXPLICIT_BANK_OWNER_MATCH_Q31_COMPONENT_COMPOSED_FULL_PROOF_PENDING',parent_native_sha256=sha(parent),native_sha256=sha(dest),component_native_sha256=component['candidate_native_sha256'],reference_interval=[a0,b0],parent_interval=[a,b],candidate_interval=[old_to_new[a],old_to_new[b]+len(inserts[b])],matched_operation_count=len(wanted),endpoint_owner_permutation=permutation,retired_physical_owner='q31',fresh_outcome=new_bit,added_expected_Toffolis='3',modelled_total_expected_Toffolis='2913/2',Q=44,T=1,rotations=34,modelled_removed_peak_windows=7,modelled_removed_peak_cuts=59,physical_Q43_not_claimed=True,full_domain_proof_pending=True,bindings={str(x.relative_to(BASE)):sha(x) for x in [Path(__file__),parent,ref,patch,bank]})
    (args.out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':main()
