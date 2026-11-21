# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Port q21/q26 idle packets to the first-coefficient Q43-stage native base.

The selective1/16 saving is explicitly forgone. Value-operation alignment
locates the two packet boundaries; exact full-domain value and all-HMR phase
replay decides validity. The first coefficient stage is byte-identical at
the operation level to the already checked width43 stage. Whole-circuit Q43
still requires the remaining peak-region replacements and physical packing.
"""
from pathlib import Path
from collections import Counter
from fractions import Fraction
import argparse
import difflib
import gzip
import json
import sys
import time
import numpy as np
from temporal_core import NOTICE, Program, captures, mul, sha, xor
from emit_q43_deferred_idle_plans import product_lines, replay

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BASE_SHA='5099a3e69167cc8341137bdeae0d91bc13f13a569326344bf1acb7e0555ff768'
CURRENT_SHA='3ced9b53d9a499037527c6097030e8699bfbdcdfc17342fc2647247ad99c6259'


def value_operations(program):
    result=[]
    for i,op in enumerate(program.operations):
        if op.kind in ('X','CX','CCX','SWAP','CSWAP','HMR','R','Z_POW'):
            signature=(op.kind,op.arguments[:1] if op.kind=='HMR' else op.arguments,op.half_turns)
            result.append((i,signature))
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();began=time.monotonic()
    base_path=HERE/'q43_first_coefficient_retimed_v1/retimed.kmx'
    current_path=ROOT/'root/combined1114_selective_qualification_v1/first/emitted/candidate.kmx'
    screen_path=HERE/'q43_deferred_idle_recompute_v1/REPORT.json'
    stage_path=HERE/'q43_first_coefficient_retimed_v1/STAGE_WIDTH_RECEIPT.json'
    helper=HERE/'emit_q43_deferred_idle_plans.py'
    assert sha(base_path)==BASE_SHA and sha(current_path)==CURRENT_SHA
    assert sha(helper)=='cbd499e70cb5155e9bee8bf8efccc9baa97696428c06c88cef606760ad3ee36d'
    base_text=base_path.read_text();base=Program(base_text);current=Program(current_path.read_text())
    screen=json.loads(screen_path.read_text());stage=json.loads(stage_path.read_text())
    assert stage['retimed_native_sha256']==BASE_SHA and stage['peak_nonzero_owners']==43
    av,bv=value_operations(current),value_operations(base)
    blocks=difflib.SequenceMatcher(None,[x[1] for x in av],[x[1] for x in bv],autojunk=False).get_matching_blocks()
    alignment={av[b.a+j][0]:bv[b.b+j][0] for b in blocks for j in range(b.size)}
    plans=[next(r for r in screen['records'] if r['case_id']==i) for i in [143,100]]
    target_maps=[]
    for p in plans:
        a,b=p['start_cut'],p['end_cut']
        assert a in alignment and b in alignment
        target_maps.append(dict(case_id=p['case_id'],owner=p['owner'],current_cuts=[a,b],
                               base_cuts=[alignment[a],alignment[b]]))
    assert [p['base_cuts'] for p in target_maps]==[[5102,5205],[7403,8281]]
    depth=0;depths=[]
    for op in base.operations:
        depths.append(depth);depth+=(op.kind=='PUSH_CONDITION')-(op.kind=='POP_CONDITION')
    depths.append(depth);assert depth==0
    inserts={};fresh=max(int(q[1:]) for q in base.wires if q.startswith('b'))+1
    fresh_events={};literal=[]
    for j,(p,mp) in enumerate(zip(plans,target_maps)):
        a,b=mp['base_cuts'];q=p['owner'];outcome=f'b{fresh+j}'
        assert depths[a]==depths[b]==0
        assert all(q not in op.arguments for op in base.operations[a:b])
        fresh_events[outcome]=base.measurements+j
        entry=[f'HMR {q} {outcome}'];exit=[]
        for product in p['restoration']['products']:
            exit+=product_lines(product['A'],product['B'],q)
        for name in p['restoration']['affine_offset']:
            exit.append(f'X {q}' if name=='constant' else f'CX {name} {q}')
        exit.append(f'Z {q} if {outcome}')
        assert sum(x.startswith('CCX ') for x in exit)==1
        inserts.setdefault(a,[]).extend(entry);inserts.setdefault(b,[]).extend(exit)
        literal.append(dict(**mp,outcome_owner=outcome,retirement_gates=entry,restoration_gates=exit,
                            exact_added_expected_Toffolis='1',original_current_peak_cuts=p['covered_peak_cuts']))
    by_line={op.line:i for i,op in enumerate(base.operations)}
    lines=['# '+NOTICE];origin=[];mapping={};count=0
    for line_number,line in enumerate(base_text.splitlines(),1):
        i=by_line.get(line_number)
        if i is None:
            lines.append(line);continue
        mapping[i]=count
        added=inserts.get(i,[]);lines+=added;origin += [None]*len(added);count+=len(added)
        lines.append(line);origin.append(i);count+=1
    mapping[len(base.operations)]=count
    changed='\n'.join(lines)+'\n';candidate=Program(changed)
    assert len(candidate.operations)==count and candidate.measurements==base.measurements+2
    assert candidate.registers==base.registers
    stage_a,stage_b=stage['interval']
    assert [(o.kind,o.arguments,o.condition,o.half_turns) for o in candidate.operations[stage_a:stage_b]] == [
        (o.kind,o.arguments,o.condition,o.half_turns) for o in base.operations[stage_a:stage_b]]
    xs=np.arange(1,3133453,dtype=np.uint64);full=(1<<len(xs))-1
    wanted={c for p in target_maps for c in p['base_cuts']}
    frames=captures(base,wanted,xs,formal=True,include_classical=True)
    current_frames=captures(current,{c for p in target_maps for c in p['current_cuts']},xs,formal=True)
    rebindings=[]
    for p,mp in zip(plans,target_maps):
        a,b=mp['base_cuts'];q=p['owner'];v={}
        assert frames[a][q]==frames[b][q]
        for product in p['restoration']['products']:
            aa=xor(*[frames[b][u] for u in product['A']]);bb=xor(*[frames[b][u] for u in product['B']])
            v=xor(v,mul(aa,bb))
        v=xor(v,*[({0:full} if u=='constant' else frames[b][u]) for u in p['restoration']['affine_offset']])
        assert v==frames[b][q]
        equal=[all(current_frames[old][f'q{k}']==frames[new][f'q{k}'] for k in range(44))
               for old,new in zip(mp['current_cuts'],mp['base_cuts'])]
        assert equal==[True,True]
        rebindings.append(dict(**mp,all44_quantum_values_identical_at_both_cuts=True,
                               restored_target_identity=True,all_legal_inputs=len(xs),all_HMR_formal=True))
    a,b=target_maps[0]['base_cuts'][0],target_maps[-1]['base_cuts'][1]
    ca,cb=mapping[a],mapping[b]+len(inserts[b])
    old=replay(frames[a],base.operations[a:b],list(range(a,b)),base,fresh_events,full)
    new=replay(frames[a],candidate.operations[ca:cb],origin[ca:cb],base,fresh_events,full)
    assert all(old[0][q]==new[0][q] for q in base.wires)
    assert old[1]==new[1] and old[2]==new[2]
    args.out.mkdir(exist_ok=False)
    dest=args.out/'candidate_text.kmx';dest.write_text(changed)
    with gzip.open(args.out/'BASE_OPERATION_MAP.json.gz','wt',compresslevel=9) as f:
        json.dump(dict(notice=NOTICE,parent_sha256=BASE_SHA,candidate_sha256=sha(dest),old_cut_to_new_cut=mapping,
                       new_operation_origin=origin),f,separators=(',',':'))
    with gzip.open(args.out/'CURRENT_NATIVE_VALUE_ALIGNMENT.json.gz','wt',compresslevel=9) as f:
        json.dump(dict(notice=NOTICE,current_sha256=CURRENT_SHA,base_sha256=BASE_SHA,
                       current_operation_to_base_operation=alignment,
                       current_operation_to_integrated_operation={k:mapping[v] for k,v in alignment.items()},
                       caution='Alignment compares quantum gate symbols and rotation angles, ignoring classical guard names. It is an index aid; full value/phase replay decides correctness.'),f,separators=(',',':'))
    with gzip.open(args.out/'LOCAL_OCCUPANCY.json.gz','wt',compresslevel=9) as f:
        json.dump(dict(notice=NOTICE,base_start_cut=a,base_masks=old[3],candidate_start_cut=ca,candidate_masks=new[3]),f,separators=(',',':'))
    occupancy=[]
    for mp in target_maps:
        a,b=mp['base_cuts'];s,t=mapping[a],mapping[b]+len(inserts[b])
        hist=Counter(x.bit_count() for x in new[3][s-ca:t-ca+1]);assert max(hist)<=43
        occupancy.append(dict(case_id=mp['case_id'],candidate_interval=[s,t],peak=max(hist),histogram=dict(sorted(hist.items()))))
    engine=ROOT/'incumbent_sources/frozen_source/fusion/runtime/work/c10/narrow/checkpoint002/cleanroom/baseline_stage97'
    sys.path.insert(0,str(engine/'tests'));sys.path.insert(0,str(engine/'engine'))
    from fourier_resource_expectation import exact_expectation
    resources=exact_expectation(changed)
    assert Fraction(resources['mean']['toffoli_like'])==Fraction(11469,8)
    assert resources['mean']['T']=='1' and resources['mean']['generic_rotations']=='34'
    report=dict(notice=NOTICE,status='INTEGRATED_FIRST_COEFFICIENT_AND_TWO_IDLE_WIDTH_BASE_LOCAL_FULL_DOMAIN_PASS',
        numerical_verification='AGENT_VERIFIED_ROOT_REPLAY_PENDING',qualified=False,
        source_sha256=sha(__file__),helper_source_sha256=sha(helper),base_native_sha256=BASE_SHA,
        current_reference_native_sha256=CURRENT_SHA,candidate_native_sha256=sha(dest),
        source_screen_sha256=sha(screen_path),source_stage_width_receipt_sha256=sha(stage_path),
        exact_original_inputs=len(xs),all_old_and_new_HMR_symbolic=True,rebindings=rebindings,plans=literal,
        fresh_HMR_event_map=fresh_events,first_stage_operation_sequence_identical=True,
        first_stage_interval=[stage_a,stage_b],first_stage_exact_peak=43,
        idle_interval_occupancies=occupancy,old_quantum_and_classical_values_identical_at_endpoint=True,
        all_HMR_binary_phase_identical=True,rotation_reads_and_angles_identical=True,
        exact_added_expected_Toffolis_vs_width_base='2',exact_candidate_expected_Toffolis='11469/8',
        exact_added_expected_Toffolis_vs_current='81/16',selective_1_over_16_saving_explicitly_forgone=True,
        total_current_native_peak_stage_and_packet_obligations_resolved=414+109+165,
        native_resources=resources,whole_native_Q=44,global_Q43_not_yet_claimed=True,
        full_unchanged_official_proof_and_rebuild_pending=True,
        mapping_sha256=sha(args.out/'BASE_OPERATION_MAP.json.gz'),
        current_alignment_sha256=sha(args.out/'CURRENT_NATIVE_VALUE_ALIGNMENT.json.gz'),
        local_occupancy_sha256=sha(args.out/'LOCAL_OCCUPANCY.json.gz'),seconds=time.monotonic()-began)
    (args.out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('native_resources','plans')},indent=2))


if __name__=='__main__':main()
