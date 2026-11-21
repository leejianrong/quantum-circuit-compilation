# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Pure native CCX deletion using an earlier causal X measurement of q8.

The advanced HMR retains its own independent outcome. Its order among four
measurements changes; no outcome is substituted for a quantum input value.
"""
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shlex

NOTICE = ('Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. '
          'Credits: Syed Asad Ali, working with a team of AI agents '
          '(GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and '
          'Opus 5.5), with Claude Science supporting the research.')
PARENT_SHA256 = '4a162e9d785ba5d17f1d3b9ee55d48b46a7e7beff424cf1fe3ffbbdfc3ab720a'
FIRST, ADVANCE, OLD_MEASUREMENT = 25560, 25570, 25592
DELETE = {
    25560: ('CCX', ('q10', 'q33', 'q21'), None),
    25569: ('CZ', ('q10', 'q33'), 'b1'),
    25580: ('X', ('q8',), None),
    25585: ('CX', ('q15', 'q8'), None),
    25592: ('HMR', ('q8', 'b163'), None),
}
PREFIX = {
    25560: ['CZ q10 q33 if b163'],
    25570: ['HMR q8 b163', 'CZ q10 q33 if b163'],
    # Keep each affine-measurement correction at its original causal write.
    25580: ['NEG if b163'],
    25585: ['Z q15 if b163'],
}
NEW_TO_OLD_EVENT = {1115: 1118, 1116: 1115, 1117: 1116, 1118: 1117}


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def transform_text(text):
    from branch_prover import Program
    assert hashlib.sha256(text.encode()).hexdigest() == PARENT_SHA256
    original = Program(text)
    for i, expected in DELETE.items():
        op = original.operations[i]
        assert (op.kind, op.arguments, op.condition) == expected
    assert original.operations[OLD_MEASUREMENT].event == 1118
    assert original.operations[ADVANCE].kind == 'CX'
    assert original.operations[ADVANCE].arguments == ('q10', 'q33')
    # These are all q8 uses and all writes to the outcome owner in the moved
    # interval. There is no quantum read or intervening phase on q8.
    q8_uses = [i for i in range(ADVANCE, OLD_MEASUREMENT+1)
               if 'q8' in original.operations[i].arguments]
    assert q8_uses == [25580, 25585, 25592]
    assert not any(original.operations[i].condition == 'b163'
                   for i in range(ADVANCE, OLD_MEASUREMENT))
    assert not any(original.operations[i].kind in ('BIT_INVERT','BIT_STORE0','BIT_STORE1','HMR')
                   and original.operations[i].arguments[-1] == 'b163'
                   for i in range(ADVANCE, OLD_MEASUREMENT))
    lines=[]; mapping={}; deltas={}; index=count=depth=delta=0
    metadata=('REGISTER','APPEND_TO_REGISTER','INFO_TAG','DEBUG_PRINT')
    for line in text.splitlines():
        tokens=shlex.split(line, comments=True)
        if not tokens or tokens[0] in metadata:
            lines.append(line); continue
        op=original.operations[index]; assert op.kind == tokens[0]
        mapping[index],deltas[index]=count,delta
        inserted=PREFIX.get(index,[])
        if inserted or index in DELETE: assert depth == 0
        lines.extend(inserted); count+=len(inserted)
        if index not in DELETE:
            lines.append(line); count+=1
        elif op.kind == 'CCX':
            delta-=1
        if op.kind=='PUSH_CONDITION':depth+=1
        elif op.kind=='POP_CONDITION':depth-=1
        assert depth>=0
        index+=1
    assert index==len(original.operations) and depth==0 and delta==-1
    mapping[index],deltas[index]=count,delta
    result='\n'.join(lines)+'\n'; candidate=Program(result)
    assert len(candidate.operations)==len(original.operations)  # five for five
    assert candidate.measurements==original.measurements==1286
    assert candidate.registers==original.registers
    old_events={op.event:op.arguments for op in original.operations if op.kind=='HMR'}
    for op in candidate.operations:
        if op.kind=='HMR':
            assert op.arguments==old_events[NEW_TO_OLD_EVENT.get(op.event,op.event)]
    return result,mapping,deltas


def apply(raw_directory):
    """Apply after the qualified q27 and pair-A raw transforms, without rebuild."""
    from branch_prover import Program, generated_text
    from fourier_resource_expectation import exact_expectation
    import arithmetic_variant as variant
    directory=Path(raw_directory)
    text_path=directory/'study.kmx';status_path=directory/'study.json'
    parent_status=json.loads(status_path.read_text())
    assert parent_status['Q']==44
    assert Fraction(parent_status['expectation']['mean']['toffoli_like'])==Fraction(11537,8)
    text,mapping,deltas=transform_text(text_path.read_text())
    circuit=variant.old.common.km.Circuit(text)
    canonical=generated_text(circuit);resources=exact_expectation(canonical)
    assert circuit.num_qubits==44 and Program(canonical).measurements==1286
    assert list(circuit.register_data)==['x'] and len(circuit.register_data['x'])==22
    assert Fraction(resources['mean']['toffoli_like'])==Fraction(11529,8)
    assert resources['mean']['T']=='4' and resources['mean']['generic_rotations']=='34'
    assert resources['static']['toffoli_like']==parent_status['expectation']['static']['toffoli_like']-1
    circuit.to_file(str(directory/'study.kmb'),format='kmb')
    text_path.write_text(canonical)
    status=dict(parent_status)
    status.update(notice=NOTICE,status='Q21_ADVANCED_HMR_CANDIDATE_FULL_PROOF_PENDING',
        expectation=resources,kmb_sha256=sha(directory/'study.kmb'))
    status['cuts_before_q21_advanced_HMR']=parent_status['cuts']
    status['cuts']=[]
    for prior in parent_status['cuts']:
        cut=dict(prior);old_index=cut['instruction_cut']
        cut['q21_advanced_HMR_parent_instruction_cut']=old_index
        cut['instruction_cut']=mapping[old_index]
        if 'cumulative_expected' in cut:
            cut['cumulative_expected']=dict(cut['cumulative_expected'])
            cut['cumulative_expected']['toffoli_like']+=deltas[old_index]
        status['cuts'].append(cut)
    ledger=dict(notice=NOTICE,status='Q21_ADVANCED_HMR_CANDIDATE_FULL_PROOF_PENDING',
        parent_raw_sha256=PARENT_SHA256,module_sha256=sha(__file__),native_raw_sha256=sha(text_path),
        native_kmb_sha256=sha(directory/'study.kmb'),removed_CCX=FIRST,
        advanced_HMR=dict(original_operation=OLD_MEASUREMENT,new_cut=ADVANCE,owners=['q8','b163']),
        prefixes=PREFIX,removed_operations=sorted(DELETE),new_to_old_event_permutation=NEW_TO_OLD_EVENT,
        raw_resources=resources,measured_parent_finished_expected_Toffolis='11465/8',
        modelled_finished_expected_Toffolis='11457/8',modelled_saving='1',Q=44,HMR_events=1286,
        new_classical_owners=0,new_fractional_phases=False,qualified=False,
        qualification_debt='Unchanged official full-domain/all-HMR proof, actual finished cost, and two byte-identical native builds.')
    status['q21_advanced_HMR']=ledger
    status_path.write_text(json.dumps(status,indent=2)+'\n')
    (directory.parent/'Q21_ADVANCED_HMR_NATIVE_LEDGER.json').write_text(json.dumps(ledger,indent=2)+'\n')
    return ledger
