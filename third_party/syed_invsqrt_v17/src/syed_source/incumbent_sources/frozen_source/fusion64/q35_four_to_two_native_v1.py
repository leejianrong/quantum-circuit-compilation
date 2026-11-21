# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Two timed products replace four q35 writes on the qualified1432.125 raw parent."""
from fractions import Fraction
from pathlib import Path
import hashlib,json,shlex
NOTICE=('Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. '
        'Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, '
        'Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science '
        'supporting the research.')
PARENT_SHA256='06125274f34f16c47bd9ffa03b6d64aa76eb87cbac20aa424d42a03f8165f0ac'
FINISHED_PARENT_SHA256='b7a34063e71e2420742e9af20c5a9f80219e1240f333d6d1941b824906863460'
DELETE=(3012,3069,3130,3195)
EARLY_A=['q20','q28','q32'];EARLY_B=['q11','q26','q27','q28','q29','q31','q33','q38']
LATE_A=['q14','q20','q26','q27','q29','q31','q32','q33','q38'];LATE_B=['q28','q32']
EARLY_FRAME=['CX q28 q20','CX q32 q20']+[f'CX {q} q11' for q in EARLY_B if q!='q11']
LATE_FRAME=[f'CX {q} q14' for q in LATE_A if q!='q14']+['CX q32 q28']
EARLY_PRODUCT=EARLY_FRAME+['CCX q20 q11 q35']+list(reversed(EARLY_FRAME))
LATE_PRODUCT=LATE_FRAME+['CCX q14 q28 q35']+list(reversed(LATE_FRAME))
INSERTIONS={3012:['CX q28 q35','CX q32 q35']+EARLY_PRODUCT,
            3064:['CX q43 q35'],3125:['CX q43 q35'],
            3193:['CX q20 q35']+LATE_PRODUCT}
RAW_FINISHED_CUTS={3012:3016,3064:3068,3069:3073,3125:3129,3130:3134,3193:3197,3195:3199}
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def apply(raw_directory):
    from branch_prover import Program,generated_text
    from fourier_resource_expectation import exact_expectation
    import arithmetic_variant as variant
    raw_directory=Path(raw_directory);text_path=raw_directory/'study.kmx';status_path=raw_directory/'study.json';assert sha(text_path)==PARENT_SHA256
    text=text_path.read_text();parent=Program(text);parent_status=json.loads(status_path.read_text());assert parent_status['Q']==44
    assert Fraction(parent_status['expectation']['mean']['toffoli_like'])==Fraction(11529,8)
    for i in DELETE:
        op=parent.operations[i];assert(op.kind,op.arguments,op.condition)==('CCX',('q20','q28','q35'),None)
    for i,a in [(3064,('q20','q30')),(3125,('q20','q30')),(3193,('q43','q32'))]:
        op=parent.operations[i];assert(op.kind,op.arguments,op.condition)==('CX',a,None)
    target_uses=[]
    for i in range(DELETE[0],DELETE[-1]+1):
        op=parent.operations[i]
        if 'q35' in op.arguments:
            assert op.kind in ('X','CX','CCX') and op.arguments[-1]=='q35' and op.condition is None
            target_uses.append(dict(op=i,kind=op.kind,owners=list(op.arguments)))
    output=[];index=count=depth=0;op_map={};metadata={'APPEND_TO_REGISTER','REGISTER','INFO_TAG','DEBUG_PRINT'}
    for line in text.splitlines():
        tokens=shlex.split(line,comments=True)
        if not tokens or tokens[0] in metadata:output.append(line);continue
        op=parent.operations[index];assert op.kind==tokens[0];op_map[index]=count
        if index in DELETE or index in INSERTIONS:assert depth==0
        if index in INSERTIONS:output.extend(INSERTIONS[index]);count+=len(INSERTIONS[index])
        if index not in DELETE:output.append(line);count+=1
        if op.kind=='PUSH_CONDITION':depth+=1
        elif op.kind=='POP_CONDITION':depth-=1
        assert depth>=0;index+=1
    op_map[index]=count;assert index==len(parent.operations) and depth==0 and count==len(parent.operations)+39
    circuit=variant.old.common.km.Circuit('\n'.join(output)+'\n');canonical=generated_text(circuit);program=Program(canonical);resources=exact_expectation(canonical)
    assert circuit.num_qubits==44 and program.measurements==parent.measurements==1286 and len(program.operations)==count
    assert list(circuit.register_data)==['x'] and len(circuit.register_data['x'])==22
    assert Fraction(resources['mean']['toffoli_like'])==Fraction(11513,8) and resources['mean']['T']=='4' and resources['mean']['generic_rotations']=='34'
    assert resources['static']['toffoli_like']==parent_status['expectation']['static']['toffoli_like']-2
    circuit.to_file(str(raw_directory/'study.kmb'),format='kmb');text_path.write_text(canonical)
    status=dict(parent_status);status.update(notice=NOTICE,status='Q35_FOUR_TO_TWO_NATIVE_FULL_PROOF_PENDING',expectation=resources,kmb_sha256=sha(raw_directory/'study.kmb'));status['cuts_before_q35_four_to_two']=parent_status['cuts'];status['cuts']=[]
    for prior in parent_status['cuts']:
        cut=dict(prior);old=cut['instruction_cut'];cut['prior_q35_four_to_two_instruction_cut']=old;cut['instruction_cut']=op_map[old]
        if 'cumulative_expected' in cut:
            cut['cumulative_expected']=dict(cut['cumulative_expected']);cut['cumulative_expected']['toffoli_like']+=sum(int(old>i) for i in [3012,3193])-sum(int(old>i) for i in DELETE)
        status['cuts'].append(cut)
    ledger=dict(notice=NOTICE,status='Q35_FOUR_TO_TWO_NATIVE_FULL_PROOF_PENDING',module_sha256=sha(__file__),parent_raw_sha256=PARENT_SHA256,parent_finished_sha256=FINISHED_PARENT_SHA256,native_raw_sha256=sha(text_path),native_kmb_sha256=sha(raw_directory/'study.kmb'),delete_op_indices=list(DELETE),insertions=INSERTIONS,raw_to_finished_capture_indices=RAW_FINISHED_CUTS,early_factors=[EARLY_A,EARLY_B],late_factors=[LATE_A,LATE_B],native_raw_resources=resources,modelled_finished_Toffolis='11441/8=1430.125',previous_qualified_Toffolis='11457/8=1432.125',modelled_saving='2',finished_cost_owed=True,target_unread_interval=[3012,3195],all_target_uses=target_uses,all_insertions_unconditional=True,Q=44,HMR_events=1286,qualified=False)
    status['q35_four_to_two']=ledger;status_path.write_text(json.dumps(status,indent=2)+'\n');(raw_directory.parent/'Q35_FOUR_TO_TWO_NATIVE_LEDGER.json').write_text(json.dumps(ledger,indent=2)+'\n');print(json.dumps(ledger,indent=2),flush=True);return ledger
