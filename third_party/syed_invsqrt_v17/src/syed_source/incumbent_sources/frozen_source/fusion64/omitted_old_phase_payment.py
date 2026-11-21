# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Pay every pre-capture phase using the actual18 live endpoint controls.

This module is standalone and may be copied with its adjacent JSON into a
private native source tree. No high-root output or decoder helper is used.
"""
from pathlib import Path
import hashlib
import json
import os

NOTICE='Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.'
DATA_PATH=Path(__file__).with_name('omitted_phase_settlement_data.json')
_DATA=None


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parity(values,mask):
    answer=0
    while mask:
        bit=mask&-mask;answer^=values[bit.bit_length()-1];mask^=bit
    return answer


def quadratic_columns(functions,ones):
    return[ones]+list(functions)+[functions[i]&functions[j]for i in range(len(functions))for j in range(i)]


def load_data():
    global _DATA
    if _DATA is None:
        data=json.loads(DATA_PATH.read_text());assert data['notice']==NOTICE
        functions=[int(t,16)for t in data['initial_control_truths_hex']];assert len(functions)==18
        columns=quadratic_columns(functions,(1<<128)-1);assert len(columns)==172
        assert len(data['basis_witnesses'])==71
        for item in data['basis_witnesses']:
            assert parity(columns,int(item['quadratic_coefficient_hex'],16))==int(item['truth_hex'],16)
        _DATA=data
    return _DATA


def emit_quadratic(b,variables,outcome,coefficient):
    """Explicit branch-exact phase, including its constant branch sign."""
    assert len(variables)==18 and coefficient>=0 and coefficient.bit_length()<=172
    counts=dict(classical_outcome_Z=0,conditional_quantum_Z=0,conditional_CZ=0)
    if coefficient&1:b.z(outcome);counts['classical_outcome_Z']+=1
    b.push_condition(outcome)
    for i,q in enumerate(variables):
        if coefficient>>(1+i)&1:b.z(q);counts['conditional_quantum_Z']+=1
    bit=19
    for i in range(18):
        for j in range(i):
            if coefficient>>bit&1:b.cz(variables[i],variables[j]);counts['conditional_CZ']+=1
            bit+=1
    assert bit==172
    b.pop_condition()
    return counts


def settle_endpoint(b,v,D,S,token,debts,truths,top_outcome,*,native=None):
    """Consume omitted row0, measured D7, and every actual historical debt."""
    data=load_data();variables=[v[0]]+list(D[:11])+[S[i]for i in(2,3,4,5,6,1)]
    assert len(variables)==18 and all(q is not None for q in variables)
    assert len(set(variables))==18,'Endpoint phase controls must be distinct live owners.'
    row=token.row_debts[0]
    assert row.width==8 and not row.consumed and set(row.measurements)==set(range(1,7))
    assert len(token.row_debts)==6
    assert all(r.consumed and not r.measurements for r in token.row_debts[1:])
    assert token.saved_bit is None
    witnesses={item['label']:item for item in data['basis_witnesses']}
    functions=[int(t,16)for t in data['initial_control_truths_hex']];columns=quadratic_columns(functions,(1<<128)-1)
    pending=list(debts.pending);requests=[]
    for i in range(1,7):
        item=witnesses[f'row0_carry{i}'];requests.append((f'row0_carry{i}',row.measurements[i],int(item['truth_hex'],16),int(item['quadratic_coefficient_hex'],16),None))
    item=witnesses['remaining_measured_D7'];requests.append(('remaining_measured_D7',top_outcome,int(item['truth_hex'],16),int(item['quadratic_coefficient_hex'],16),None))
    indicator_coefficients=[int(witnesses[f'old_loader_address_indicator_{i}']['quadratic_coefficient_hex'],16)for i in range(64)]
    for index,(outcome,truth)in enumerate(pending):
        truth=int(truth);assert 0<=truth<(1<<64)
        coefficient=parity(indicator_coefficients,truth);expanded=sum(3<<(2*i)for i in range(64)if truth>>i&1)
        assert parity(columns,coefficient)==expanded
        requests.append((f'old_loader_pending_{index}',outcome,expanded,coefficient,truth))
    outcomes=[outcome for _,outcome,_,_,_ in requests]
    assert len(set(outcomes))==len(outcomes),'Every pending classical owner must be consumed exactly once.'
    before=b.num_allocated_qubits;records=[];counts=dict(classical_outcome_Z=0,conditional_quantum_Z=0,conditional_CZ=0)
    for label,outcome,target,coefficient,old_truth in requests:
        assert parity(columns,coefficient)==target
        delta=emit_quadratic(b,variables,outcome,coefficient)
        for key,value in delta.items():counts[key]+=value
        records.append(dict(label=label,classical_outcome_owner=str(outcome),target_truth128_hex=hex(target),
            original_loader_truth64_hex=None if old_truth is None else hex(old_truth),quadratic_coefficient_hex=hex(coefficient),gate_counts=delta))
        b.free(outcome)
    row.measurements.clear();row.consumed=True;debts.pending=[]
    assert b.num_allocated_qubits==before and not row.measurements and row.consumed and not debts.pending
    report=dict(notice=NOTICE,status='EMITTED_ALL_PRECAPTURE_PHASE_DEBTS_WITH_LIVE18_CONTROL_BINDING',
        source_sha256=sha(__file__),data_sha256=sha(DATA_PATH),basis_function_count=71,
        control_order=data['initial_control_order'],physical_control_owners=list(map(str,variables)),
        live_quantum_owners_before=before,live_quantum_owners_after=b.num_allocated_qubits,max_qubits=b.max_qubits,
        omitted_row_carry_outcomes_paid=6,remaining_measured_D7_outcomes_paid=1,
        actual_old_loader_outcomes_paid=len(pending),total_classical_outcomes_paid=len(requests),
        all_actual_outcomes_distinct=True,paid_outcome_records=records,gate_counts=counts,
        added_Toffoli_like=0,added_T_gates=0,added_rotations=0,additional_quantum_owners=0,
        omitted_row_token_consumed=True,historical_debt_list_empty=True,
        phase_control_contract='Before decoder helper preparation: [v0]+[C1_0..C1_6,A7..A10]+[S2,S3,S4,S5,S6,S1]. No restored high-root or later helper is used.',
        original_domain_ALL_HMR_proof_pending=True)
    if native is not None:
        native.OMITTED_V0=v[0];native.OMITTED_PHASE_SETTLEMENT_REPORT=report
    if os.environ.get('OMITTED_PHASE_SETTLEMENT_LEDGER'):
        Path(os.environ['OMITTED_PHASE_SETTLEMENT_LEDGER']).write_text(json.dumps(report,indent=2)+'\n')
    return report


def install(native):
    def hook(b,v,D,S,token,debts,truths,top_outcome):
        return settle_endpoint(b,v,D,S,token,debts,truths,top_outcome,native=native)
    native.omitted_settle_endpoint=hook
    return hook
