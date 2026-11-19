# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""COPY by agent width of Pro 2 q47_loader_native_v1/paid_R_cleanup_q47.py (sha d1743939...): certificate read from
the original directory, `builder.max_qubits==47` asserts accept 47 or 48. No other change.

Explicit paid-R snapshot and joint A13/H5 phase cleanup, Q48.

The caller keeps the original final root_R_frame inverse call between the
two capture helpers. All preceding arithmetic/preparation calls stay intact.
This module owns the retained product and every joint-cleanup measurement.
"""
from pathlib import Path
from fractions import Fraction
import hashlib,json

HERE=Path('@FG_ROOT@/work/pro2_q47_loader/work/loaders/q47_loader_native_v1')
CERT_SHA='9c4b4aea56ad334f7082608d3a24193d900390c76e578e48aa67a88456664ff7'
CERT_PATH=HERE/'paid_R_cleanup_certificate.json'
CERT=json.loads(CERT_PATH.read_text())
assert hashlib.sha256(CERT_PATH.read_bytes()).hexdigest()==CERT_SHA
EXPECTED=Fraction(*CERT['selected']['mean_fraction'])
assert EXPECTED==Fraction(809,128)
FULL=(1<<128)-1
LAST_REPORT=None

def capture_R_before_inverse(builder,framed_a3):
    """At44 owners, copy the current framed v8=R into one new zero owner."""
    assert builder.max_qubits in (46,47,48) and builder.num_allocated_qubits==44
    product=builder.alloc_qubits(1)[0]
    assert product!=framed_a3
    builder.cx(framed_a3,product)
    assert builder.num_allocated_qubits==45
    return product

def finish_R_capture(builder,raw_a3,raw_a2,product):
    """After the unchanged inverse frame, leave p=R+a3+a2=a1*(a2+a5)."""
    assert builder.num_allocated_qubits==45
    assert len({raw_a3,raw_a2,product})==3
    builder.cx(raw_a3,product);builder.cx(raw_a2,product)
    return product

def cleanup_joint18(builder,address7,A13,H5,product,debts,*,table_api):
    """Erase A13/H5, all phase helpers and paid p; retain all26 body owners."""
    global LAST_REPORT
    api=table_api;cb=api.cb
    address,A,H=list(address7),list(A13),list(H5)
    assert (len(address),len(A),len(H))==(7,13,5)
    assert len(set(address+A+H+[product]))==26
    assert isinstance(debts,api.TableDebts)
    assert builder.max_qubits in (46,47,48) and builder.num_allocated_qubits==45
    truths=api.model_truths();raw=list(truths['address'])
    output_truths=list(truths['A'])+list(truths['H'])
    assert len(output_truths)==18
    paid_truth=raw[1]&(raw[2]^raw[5]);base_truths=raw+[paid_truth]
    assert paid_truth==int(CERT['free_coordinate']['truth'],16)
    # The original universal repayment chart and all incoming debts are
    # unchanged. Additional high metadata and p are not needed by this flush.
    flushed=debts.flush(builder,address+A+H[:3],raw+output_truths[:16])
    assert not debts.pending and flushed['quadratic_rank']==128
    selected=CERT['selected'];masks=selected['masks']
    assert len(masks)==len(cb.BinarySpan(masks).pivots)==18
    framed=[cb.parity_function(m,output_truths)for m in masks]
    outputs=A+H
    api.emit_affine_frame(builder,address,outputs,[m<<8 for m in masks])
    producers=[];helper_truths=[]
    for item in CERT['bank_steps']:
        plan=api.plan_from_json(item['plan']);truth=int(item['truth'],16)
        assert plan.width==8+len(producers)and plan.and_count==1
        assert plan.evaluate_factored_functions(base_truths+helper_truths,FULL)==truth
        producers.append(plan);helper_truths.append(truth)
    helpers=[];present=[];live=list(outputs);trace=[45]
    users=[set()for _ in producers];compute_sites=0
    for item in selected['erasures']:
        index=item['output_index'];assert len(live)==index+1
        old=live.pop();outcome=builder.alloc_bits(1)[0]
        builder.hmr(old,outcome);builder.free(old)
        prefix=item['min_prefix']
        if prefix and not helpers:
            helpers=list(builder.alloc_qubits(len(producers)))
            present=list(builder.alloc_bits(len(producers)))
            for flag in present:builder.bit_store(flag,False)
        for j in item['needed']:
            users[j].add(index)
            missing=builder.alloc_bits(1)[0]
            builder.bit_store(missing,True);builder.cx(present[j],missing)
            builder.push_condition(outcome);builder.push_condition(missing)
            cb.emit_xor(builder,address+[product]+helpers[:j],helpers[j],producers[j])
            builder.bit_store(present[j],True)
            builder.pop_condition();builder.pop_condition();builder.free(missing)
            compute_sites+=1
        plan=api.plan_from_json(item['plan'])
        variables=address+[product]+helpers[:prefix]+live
        assert plan.width==len(variables)
        assert plan.evaluate_functions(base_truths+helper_truths[:prefix]+framed[:index],FULL)==framed[index]
        cb.emit_phase(builder,variables,outcome,plan);builder.free(outcome)
        trace.append(builder.num_allocated_qubits)
    assert not live and len(helpers)==len(present)==len(producers)
    for j in reversed(range(len(producers))):
        builder.push_condition(present[j])
        cb.emit_erase(builder,address+[product]+helpers[:j],[helpers[j]],[producers[j]])
        builder.pop_condition();builder.free(helpers[j]);trace.append(builder.num_allocated_qubits)
    for flag in present:builder.free(flag)
    assert builder.num_allocated_qubits==27
    paid_plan=api.plan_from_json(CERT['free_coordinate']['final_erase_plan'])
    assert paid_plan.width==7 and paid_plan.evaluate_functions(raw,FULL)==paid_truth
    # This is a quadratic Clifford phase correction, never a new AND.
    cb.emit_erase(builder,address,[product],[paid_plan]);builder.free(product)
    trace.append(builder.num_allocated_qubits)
    assert [sorted(s)for s in users]==selected['users']
    expected=sum((1-Fraction(1,1<<len(s))for s in users),Fraction(0))
    assert expected==EXPECTED and builder.num_allocated_qubits==26
    assert max(trace)<=selected['cleanup_peak_bound']<=47 and not debts.pending
    LAST_REPORT=dict(status='EMITTED_PAID_R18_COMPONENT_NATIVE_PROOF_PENDING',
        expected_Toffolis=float(expected),expected_fraction=[expected.numerator,expected.denominator],
        entry=45,return_owners=26,capture_peak=45,cleanup_peak_bound=selected['cleanup_peak_bound'],
        trace=trace,output_signs_repaid=18,paid_product_sign_repaid=True,
        helper_signs_all_branches_repaid=True,incoming_table_debts_repaid=flushed['outcomes'],
        incoming_flush_unchanged=True,compute_sites=compute_sites,
        helper_activation_users=[sorted(s)for s in users],
        producer_added_Toffolis=0,producer_added_CNOTs=3,
        root_frame_and_arithmetic_callbacks_external_and_unchanged=True,
        certificate_sha256=CERT_SHA)
    return LAST_REPORT
