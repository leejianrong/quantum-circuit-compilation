# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Pure q27 temporal merge on exact qualified1435.125 raw parent.

Replace only the target-unread q27 pair3294/3320 by one product at3318
plus temporal CXs. The q35/q9 affine redundancies are already in the finisher.
The caller rebuilds/applies distributive_q28_native_v1 before this transform.
"""
from fractions import Fraction
from pathlib import Path
import hashlib,json,shlex
NOTICE=('Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. '
        'Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, '
        'Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science '
        'supporting the research.')
PARENT_SHA256='63c8ae4d464f816f8e46092a36ad2e796e13b2e43908edc58fa492da410980df'
Q35=2959;Q9=22002;FIRST=3294;INSERT=3318;SECOND=3320
FRAME=['CX q15 q26','CX q15 q20','CX q40 q20']
PRODUCT=FRAME+['CCX q26 q20 q27']+list(reversed(FRAME))
REPLACEMENTS={FIRST:['X q27','CX q20 q27','CX q26 q27','CX q42 q27'],SECOND:[]}
INSERTIONS={INSERT:PRODUCT+['CX q40 q27']}
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def apply(raw_directory):
    from branch_prover import Program,generated_text
    from fourier_resource_expectation import exact_expectation
    import arithmetic_variant as variant
    raw_directory=Path(raw_directory);text_path=raw_directory/'study.kmx';status_path=raw_directory/'study.json';assert sha(text_path)==PARENT_SHA256
    text=text_path.read_text();parent=Program(text);parent_status=json.loads(status_path.read_text());assert parent_status['Q']==44
    assert Fraction(parent_status['expectation']['mean']['toffoli_like'])==Fraction(11553,8)
    expected={Q35:('q20','q28','q35'),Q9:('q33','q27','q9'),FIRST:('q26','q42','q27'),SECOND:('q40','q26','q27')}
    for i,a in expected.items():op=parent.operations[i];assert(op.kind,op.arguments,op.condition)==('CCX',a,None)
    assert parent.operations[INSERT].kind=='CX' and parent.operations[INSERT].arguments==('q41','q20')
    retained=[]
    for i in range(FIRST+1,SECOND):
        op=parent.operations[i]
        if 'q27' in op.arguments:
            assert op.kind in ('X','CX','CCX') and op.arguments[-1]=='q27' and op.condition is None;retained.append(dict(op=i,kind=op.kind,owners=list(op.arguments)))
    output=[];index=count=depth=0;op_map={};metadata={'APPEND_TO_REGISTER','REGISTER','INFO_TAG','DEBUG_PRINT'}
    for line in text.splitlines():
        tokens=shlex.split(line,comments=True)
        if not tokens or tokens[0] in metadata:output.append(line);continue
        op=parent.operations[index];assert op.kind==tokens[0];op_map[index]=count
        if index in REPLACEMENTS or index in INSERTIONS:assert depth==0
        if index in INSERTIONS:output.extend(INSERTIONS[index]);count+=len(INSERTIONS[index])
        if index in REPLACEMENTS:output.extend(REPLACEMENTS[index]);count+=len(REPLACEMENTS[index])
        else:output.append(line);count+=1
        if op.kind=='PUSH_CONDITION':depth+=1
        elif op.kind=='POP_CONDITION':depth-=1
        assert depth>=0;index+=1
    op_map[index]=count;assert index==len(parent.operations) and depth==0 and count==len(parent.operations)+10
    circuit=variant.old.common.km.Circuit('\n'.join(output)+'\n');canonical=generated_text(circuit);program=Program(canonical);resources=exact_expectation(canonical)
    assert circuit.num_qubits==44 and program.measurements==parent.measurements==1286 and len(program.operations)==count
    assert list(circuit.register_data)==['x'] and len(circuit.register_data['x'])==22
    assert Fraction(resources['mean']['toffoli_like'])==Fraction(11545,8) and resources['mean']['T']=='4' and resources['mean']['generic_rotations']=='34'
    assert resources['static']['toffoli_like']==parent_status['expectation']['static']['toffoli_like']-1
    circuit.to_file(str(raw_directory/'study.kmb'),format='kmb');text_path.write_text(canonical)
    status=dict(parent_status);status.update(notice=NOTICE,status='Q27_TEMPORAL_MERGE_NATIVE_FULL_PROOF_PENDING',expectation=resources,kmb_sha256=sha(raw_directory/'study.kmb'));status['cuts_before_q27_temporal_merge']=parent_status['cuts'];status['cuts']=[]
    for prior in parent_status['cuts']:
        cut=dict(prior);old=cut['instruction_cut'];cut['prior_q28_instruction_cut']=old;cut['instruction_cut']=op_map[old]
        if 'cumulative_expected' in cut:
            cut['cumulative_expected']=dict(cut['cumulative_expected']);cut['cumulative_expected']['toffoli_like']+=-int(old>FIRST)+int(old>INSERT)-int(old>SECOND)
        status['cuts'].append(cut)
    ledger=dict(notice=NOTICE,status='Q27_TEMPORAL_MERGE_NATIVE_FULL_PROOF_PENDING',module_sha256=sha(__file__),parent_raw_sha256=PARENT_SHA256,native_raw_sha256=sha(text_path),native_kmb_sha256=sha(raw_directory/'study.kmb'),replacements=REPLACEMENTS,insertions=INSERTIONS,native_identities=['q26(3294)*q42(3294) XOR q40(3320)*q26(3320) = (q15 XOR q26)(3318)*(q15 XOR q20 XOR q40)(3318) XOR 1 XOR q20(3294) XOR q26(3294) XOR q42(3294) XOR q40(3318)'],q27_target_unread_interval=True,all_insertion_scopes_unconditional=True,retained_q27_target_writes=retained,raw_resources=resources,expected_finished_Toffolis='11473/8',finished_cost_assumption='Raw saving1 is new relative to known affine0 q35/q9 simplifications; actual finished resources still require measurement',previous_qualified_parent_Toffolis='11481/8',modelled_saving='1',Q=44,HMR_events=1286,qualified=False)
    status['q27_temporal_merge']=ledger;status_path.write_text(json.dumps(status,indent=2)+'\n');(raw_directory.parent/'Q27_TEMPORAL_MERGE_NATIVE_LEDGER.json').write_text(json.dumps(ledger,indent=2)+'\n');print(json.dumps(ledger,indent=2),flush=True);return ledger
