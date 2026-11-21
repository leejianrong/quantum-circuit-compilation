# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Deterministic binary staged row13 replacement in both original-oldq sectors.

Preserve the qualified oldq0 V2 network. In oldq1 use the independently
bound changed first and second factors and their all-HMR binary correction.
Omit row13 recoding and its feedback in both selected sectors. Every other
parent value and HMR operation is retained. This module is sealed only with
its exact companion V3 witness bundle and still requires native qualification.
"""
from pathlib import Path
from fractions import Fraction
import argparse,hashlib,json,shlex,shutil

NOTICE=('Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. '
        'Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, '
        'Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science '
        'supporting the research.')


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def affine_ccz(physical,masks,pivots):
    # The three selected pivot owners occur only in their own factor. Thus
    # these CNOT accumulations commute and preserve the other factor inputs.
    assert len(masks)==len(pivots)==3
    for i,p in enumerate(pivots):
        assert masks[i]>>p&1 and all(not(m>>p&1) for j,m in enumerate(masks) if j!=i)
    forward=[]
    for mask,pivot in zip(masks,pivots):
        forward.extend(f'CX {physical[j]} {physical[pivot]}' for j in range(len(physical)) if j!=pivot and mask>>j&1)
    return forward+['CCZ '+' '.join(physical[p] for p in pivots)]+list(reversed(forward))


def oldq1_second_ccz():
    forward=['CX q19 q0','CX q34 q0','CX q15 q17','CX q18 q17','CX q43 q17','CX q15 q29','CX q19 q29','CX q30 q29']
    return forward+['CCZ q0 q17 q29']+list(reversed(forward))


def apply(raw_directory,legacy_bundle_path=None):
    from branch_prover import Program,generated_text
    from fourier_resource_expectation import exact_expectation
    import arithmetic_variant as variant
    raw_directory=Path(raw_directory);own=Path(__file__).resolve().parent
    bundle_path=own/'staged_bank_bundle_v3_causal.json';envelope=json.loads(bundle_path.read_text())
    if legacy_bundle_path is None:legacy_bundle_path=own/'suffix_hmr_phase_bundle_v3.json'
    legacy_bundle_path=Path(legacy_bundle_path);assert sha(legacy_bundle_path)==envelope['legacy_bundle_sha256']
    old_envelope=json.loads(legacy_bundle_path.read_text());old=old_envelope['identity_bundle']
    old_audit=old_envelope['full_domain_algebra_audit']
    assert old_audit['exact_phase_identity'] and old_audit['failed_original_inputs']==0 and old_audit['original_inputs']==3133452
    assert old_audit['every_other_HMR_symbolic']
    text_path=raw_directory/'study.kmx';parent_text=text_path.read_text()
    assert sha(text_path)==envelope['parent_raw_sha256']==old['parent_raw_sha256']
    parent=Program(parent_text);status_path=raw_directory/'study.json';parent_status=json.loads(status_path.read_text())
    assert parent_status['Q']==44 and Fraction(parent_status['expectation']['mean']['toffoli_like'])==Fraction('11567/8')
    saved=dict(oldq='b363',m13='b364',mB='b365',selected0='b366',selected1='b367',selected0_mB0='b368',selected1_mB0='b369')
    assert not(set(saved.values())&set(parent.wires))
    for cut,quantum,classical,event in [(4664,'q7','b159',284),(13909,'q34','b359',834),(14705,'q36','b361',869)]:
        op=parent.operations[cut];assert (op.kind,op.arguments,op.condition,op.event)==('HMR',(quantum,classical),None,event)
    removed={d['op']:d for d in old['removed_diagonal_operations']}
    assert set(removed)==set(envelope['remove_F_diagonal_operations'])
    assert all(14106<=i<=14152 for i in removed)
    for i,d in removed.items():
        op=parent.operations[i];assert (op.kind,list(op.arguments),op.condition)==(d['kind'],d['owners'],None)
    removed_bank_value_ops={14120:('CCX',('q18','q43','q21')),14164:('CZ',('q18','q43')),14165:('CZ',('q18','q0'))}
    assert set(removed_bank_value_ops)==set(envelope['remove_bank_recode_operations'])
    for i,(kind,owners) in removed_bank_value_ops.items():
        op=parent.operations[i];assert (op.kind,op.arguments,op.condition)==(kind,owners,None)
    # Every addition is a complete affine frame or a diagonal phase at the
    # parent cut, outside the original surrounding conditional stack.
    at={}
    def schedule(cut,guards,lines,label):
        at.setdefault(cut,[]).append(dict(guards=list(guards),lines=list(lines),label=label))
    for sector in (0,1):
        for pulse in envelope[f'literal_pulses_oldq{sector}']:
            desc=pulse['descriptor'];kind=desc['kind'];c=pulse['coefficient_mod4'];q=desc['owners']
            names=list(desc.get('guard_names',[]))
            if 'guard' in desc:names.append(desc['guard'])
            guards=[saved[f'selected{sector}']]
            for name in names:
                if name=='saved_row12_mB':
                    assert desc['op']>=14706;guards.append(saved['mB'])
                else:
                    assert name.startswith('b') and name in parent.wires
                    guards.append(name)
            guards=list(dict.fromkeys(guards))
            assert c==2, ('nonbinary staged phase',desc,c)
            if kind=='constant':lines=['NEG']
            elif kind=='CZ':
                assert len(q)==2;lines=['CZ '+' '.join(q)]
            elif kind=='Z':
                assert len(q)==1;lines=[f'Z {q[0]}']
            else:raise AssertionError(('nonbinary staged phase kind',kind))
            schedule(desc['op'],guards,lines,f'oldq{sector}_Clifford')
    physical=envelope['first_control_order']
    first0=affine_ccz(physical,[116,3099,17441],[2,1,14])
    first1=affine_ccz(physical,[116,3099,16450],[2,10,14])
    schedule(14122,[saved['selected0']],first0,'qualified_oldq0_first_CCZ')
    schedule(14122,[saved['selected1']],first1,'new_oldq1_first_CCZ')
    second0=['CX q43 q15','CX q29 q16','CX q34 q16','CCZ q0 q15 q16','CX q34 q16','CX q29 q16','CX q43 q15']
    second1=oldq1_second_ccz()
    schedule(14706,[saved['selected0_mB0']],second0,'qualified_oldq0_second_CCZ')
    schedule(14706,[saved['selected1_mB0']],second1,'new_oldq1_second_CCZ')
    last=max(at)
    assert last==envelope['last_saved_control_cut']
    assert envelope['last_literal_cut']==max(p['descriptor']['op'] for sector in (0,1) for p in envelope[f'literal_pulses_oldq{sector}'])
    save_cuts={4665,13910,14706};stack=[];writes={};output=[];operation_count=0;op_map={};index=0;guard_receipts=[]
    def emit(line):
        nonlocal operation_count
        output.append(line)
        if line and line.split()[0] not in ('APPEND_TO_REGISTER','REGISTER','INFO_TAG','DEBUG_PRINT'):operation_count+=1
    def external(cut):
        # Current parent guards can be restored iff their classical controls
        # retain the values captured by the original PUSH instructions.
        for bit,previous_write in stack:assert writes.get(bit)==previous_write,('native scope bit changed',cut,bit)
        guard_receipts.append(dict(parent_operation=cut,parent_guards=[b for b,_ in stack],controls_unchanged_since_push=True))
        for _ in stack:emit('POP_CONDITION')
        if cut==4665:
            emit(f'BIT_STORE0 {saved["oldq"]}');emit(f'BIT_INVERT {saved["oldq"]} if b159')
        if cut==13910:
            emit(f'BIT_STORE0 {saved["m13"]}');emit(f'BIT_INVERT {saved["m13"]} if b359')
            emit(f'BIT_STORE0 {saved["selected0"]}');emit(f'BIT_STORE0 {saved["selected1"]}')
            emit(f'PUSH_CONDITION if {saved["m13"]}')
            emit(f'BIT_INVERT {saved["selected0"]}');emit(f'BIT_INVERT {saved["selected0"]} if {saved["oldq"]}')
            emit(f'BIT_INVERT {saved["selected1"]} if {saved["oldq"]}');emit('POP_CONDITION')
        if cut==14706:
            emit(f'BIT_STORE0 {saved["mB"]}');emit(f'BIT_INVERT {saved["mB"]} if b361')
            for sector in (0,1):
                target=saved[f'selected{sector}_mB0'];selection=saved[f'selected{sector}']
                emit(f'BIT_STORE0 {target}');emit(f'PUSH_CONDITION if {selection}')
                emit(f'BIT_INVERT {target}');emit(f'BIT_INVERT {target} if {saved["mB"]}');emit('POP_CONDITION')
        for item in at.get(cut,[]):
            for guard in item['guards']:emit(f'PUSH_CONDITION if {guard}')
            for line in item['lines']:emit(line)
            for _ in item['guards']:emit('POP_CONDITION')
        if cut==last:
            for bit in saved.values():emit(f'BIT_STORE0 {bit}')
        for bit,_ in stack:emit(f'PUSH_CONDITION if {bit}')
    for line in parent_text.splitlines():
        tokens=shlex.split(line,comments=True)
        if not tokens or tokens[0] in ('APPEND_TO_REGISTER','REGISTER','INFO_TAG','DEBUG_PRINT'):
            output.append(line);continue
        op=parent.operations[index];assert tokens[0]==op.kind;op_map[index]=operation_count
        if index in at or index in save_cuts:external(index)
        if index in removed_bank_value_ops:
            assert stack and stack[0][0]=='b359'
        elif index not in removed:emit(line)
        if op.kind=='PUSH_CONDITION':stack.append((op.condition,writes.get(op.condition)))
        elif op.kind=='POP_CONDITION':stack.pop()
        elif op.kind=='HMR':writes[op.arguments[1]]=index
        elif op.kind in ('BIT_STORE0','BIT_STORE1','BIT_INVERT','X','CX') and op.arguments[-1].startswith('b'):writes[op.arguments[-1]]=index
        index+=1
    assert index==len(parent.operations) and not stack;op_map[index]=operation_count
    circuit=variant.old.common.km.Circuit('\n'.join(output)+'\n');canonical=generated_text(circuit);program=Program(canonical)
    assert circuit.num_qubits==44 and program.measurements==parent.measurements==1286
    assert len(program.operations)==operation_count
    assert list(circuit.register_data)==['x'] and len(circuit.register_data['x'])==22
    resources=exact_expectation(canonical)
    assert Fraction(resources['mean']['toffoli_like'])==Fraction('11561/8'),resources['mean']
    assert resources['mean']['T']=='4' and resources['mean']['generic_rotations']=='34'
    assert resources['static']['toffoli_like']==parent_status['expectation']['static']['toffoli_like']+1
    circuit.to_file(str(raw_directory/'study.kmb'),format='kmb');text_path.write_text(canonical)
    status=dict(parent_status);status.update(notice=NOTICE,status='STAGED_PURE_BINARY_NATIVE_CANDIDATE_FULL_PROOF_PENDING',expectation=resources,kmb_sha256=sha(raw_directory/'study.kmb'),
        staged_substitution=dict(module_sha256=sha(__file__),bundle_sha256=sha(bundle_path),legacy_bundle_sha256=sha(legacy_bundle_path),parent_raw_sha256=envelope['parent_raw_sha256'],literal_witness_inputs=35184,every_other_HMR_symbolic=True,full_domain_qualified=False))
    status['parent_cuts_before_staged_pass']=parent_status['cuts'];status['cuts']=[]
    for prior_cut in parent_status['cuts']:
        cut=dict(prior_cut);parent_index=cut['instruction_cut'];cut['parent_instruction_cut']=parent_index;cut['instruction_cut']=op_map[parent_index]
        if 'cumulative_expected' in cut:
            cut['cumulative_expected']=dict(cut['cumulative_expected']);delta=Fraction(0)
            if parent_index>14120:delta-=Fraction(1,2)
            if parent_index>14122:delta+=Fraction(1,2)
            if parent_index>14129:delta-=Fraction(1,2)
            if parent_index>14143:delta-=Fraction(1,2)
            if parent_index>14706:delta+=Fraction(1,4)
            cut['cumulative_expected']['toffoli_like']+=float(delta)
        status['cuts'].append(cut)
    status_path.write_text(json.dumps(status,indent=2)+'\n')
    ledger=dict(notice=NOTICE,status='STAGED_PURE_BINARY_NATIVE_CANDIDATE_PROOF_PENDING',module_sha256=sha(__file__),bundle_sha256=sha(bundle_path),legacy_bundle_sha256=sha(legacy_bundle_path),parent_raw_sha256=envelope['parent_raw_sha256'],native_raw_sha256=sha(text_path),native_kmb_sha256=sha(raw_directory/'study.kmb'),
        original_F_diagonals_removed=list(removed.values()),removed_native_bank_operations=[dict(op=i,kind=k,owners=list(q)) for i,(k,q) in removed_bank_value_ops.items()],
        saved_classical_owners=saved,chronological_guards=[dict(copy_after_parent_operation=4664,meaning='saved oldq,event284'),dict(copy_after_parent_operation=13909,meaning='saved m13,event834; selected0=m13*(1+oldq),selected1=m13*oldq'),dict(copy_after_parent_operation=14705,meaning='saved mB,event869; selected0_mB0=m13*(1+oldq)*(1+mB); selected1_mB0=m13*oldq*(1+mB)'),dict(clear_before_parent_operation=last,meaning='Clear all seven saved classical values after last correction.')],
        expected_ledger='earlyq raw11567/8 minus recoding1/2 minus original twoCCZ1 plus oldq0 andoldq1 firstCCZs1/2 plus both mB0 secondCCZs1/4 =11561/8. Frozen finishing is expected to remove9, yielding11489/8=1436.125; finishing and full-domain proof must confirm.',
        expected_finished_Toffolis='11489/8',expected_saving_from_qualified_incumbent='1/8',raw_resources=resources,quantum_owners=44,HMR_events=1286,oldq0_literal_phase_pulses=len(envelope['literal_pulses_oldq0']),oldq1_literal_phase_pulses=len(envelope['literal_pulses_oldq1']),native_guard_receipts=guard_receipts,
        oldq0_first_CCZ_literal=first0,oldq0_second_CCZ_literal=second0,oldq1_first_CCZ_literal=first1,oldq1_second_CCZ_literal=second1,parent_to_raw_operation_map={str(k):v for k,v in op_map.items()},qualified=False)
    (raw_directory.parent/'STAGED_NATIVE_LEDGER.json').write_text(json.dumps(ledger,indent=2)+'\n')
    print(json.dumps({k:ledger[k] for k in ('status','native_raw_sha256','native_kmb_sha256','raw_resources','expected_finished_Toffolis','quantum_owners','HMR_events')}),flush=True)
    return ledger


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--parent-raw',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--legacy-bundle',type=Path)
    args=parser.parse_args();parent=args.parent_raw if args.parent_raw.is_dir() else args.parent_raw.parent
    args.out.mkdir(parents=True,exist_ok=False)
    for name in ('study.kmx','study.kmb','study.json'):shutil.copy2(parent/name,args.out/name)
    apply(args.out,args.legacy_bundle)


if __name__=='__main__':main()
