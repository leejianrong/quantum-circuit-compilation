# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Native hook for the exact three-product shared-prefix decoder.

Call immediately after frozen C33 decoder step0, when the root basis is[48].
Return two owners in root-parity order[8,32]. The caller appends them and
uses Clifford frame rows[2,5,4] to obtain[8,16,32], skips old steps1/2,
and resumes original step3. The frozen C33 source must not be edited.
"""
import hashlib,json
from pathlib import Path

HERE=Path(__file__).resolve().parent
FULL=(1<<128)-1


def xor(values,mask):
    out=0
    while mask:
        bit=mask&-mask;out^=values[bit.bit_length()-1];mask^=bit
    return out


def lift_original_mask(mask):
    """Map F12=[originalG7..G17,root48] to frozen raw7+G18 masks."""
    assert 0<=mask<1<<12
    return ((mask&2047)<<14)^((48<<1)if mask>>11&1 else 0)


def emit_shared_pair(b,emit,variables,values,translate):
    """Return([root8_owner,root32_owner], exact_truths, JSON ledger).

    emit supplies the already-qualified native emit_product and
    emit_cz_product routines. variables/values are the current physical
    [v0]+framedG18+[root48] snapshot. translate is the frozen decoder's
    raw7+originalG18 to current physical linear-mask function.
    """
    plan_path=HERE/'shared_prefix_plan.json';plan=json.loads(plan_path.read_text())
    assert len(variables)==len(values)==20
    entry=b.num_allocated_qubits;assert entry==39
    logical_forms=[translate(lift_original_mask(1<<i))for i in range(12)]
    logical_values=[xor(values,m)for m in logical_forms]
    assert list(map(hex,logical_values))==plan['control_truths_hex']
    base_count=len(variables)
    def physical_mask(mask,extra_count):
        assert 0<=mask<1<<(12+extra_count)
        return xor(logical_forms,mask&4095)|((mask>>12)<<base_count)
    helper=b.alloc_qubits(1)[0];L,R=plan['helper_product_masks']
    helper_masks=[physical_mask(L,0),physical_mask(R,0)]
    emit.emit_product(b,variables,helper,*helper_masks)
    helper_value=xor(logical_values,L)&xor(logical_values,R)
    assert helper_value==int(plan['helper_truth_hex'],16)
    owners=[];truths=[];events=[dict(event='prepare_shared_helper',live_owners=b.num_allocated_qubits)]
    for index,step in enumerate(plan['outputs']):
        extra_owners=[helper]+owners;extra_values=[helper_value]+truths
        all_owners=list(variables)+extra_owners;all_values=logical_values+extra_values
        out=b.alloc_qubits(1)[0];linear=step['affine_mask'];outvalue=FULL if linear&1 else 0
        if linear&1:b.x(out)
        physical_linear=physical_mask(linear>>1,len(extra_owners))
        for j,q in enumerate(all_owners):
            if physical_linear>>j&1:b.cx(q,out)
        left,right=step['left_mask'],step['right_mask']
        emit.emit_product(b,all_owners,out,physical_mask(left,len(extra_owners)),physical_mask(right,len(extra_owners)))
        outvalue^=xor(all_values,linear>>1)^(xor(all_values,left)&xor(all_values,right))
        assert outvalue==int(step['target_truth_hex'],16)
        owners.append(out);truths.append(outvalue)
        events.append(dict(event='decode_root',root_parity=plan['output_root_parities'][index],live_owners=b.num_allocated_qubits))
    m=b.alloc_bits(1)[0];b.hmr(helper,m);b.free(helper)
    b.push_condition(m);emit.emit_cz_product(b,variables,*helper_masks);b.pop_condition();b.free(m)
    assert helper_value^(xor(values,helper_masks[0])&xor(values,helper_masks[1]))==0
    assert b.num_allocated_qubits==entry+2
    events.append(dict(event='erase_shared_helper',live_owners=b.num_allocated_qubits))
    ledger=dict(notice=plan['notice'],status='NATIVE_SHARED_PREFIX_EMISSION_PENDING_WHOLE_PROOF',
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),plan_sha256=hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        source_positive_report_sha256=plan['source_positive_report_sha256'],input_root_basis=[48],output_root_parities=[8,32],
        caller_final_root_basis=[8,16,32],caller_frame_rows=[2,5,4],entry_owners=entry,exit_owners=b.num_allocated_qubits,
        component_peak_owners=max(item['live_owners']for item in events),replaced_value_Toffolis=4,new_value_Toffolis=3,
        helper_cleanup_Toffolis=0,new_HMR_outcomes=1,helper_HMR_phase_coefficient_hex='0x0',
        original_G_and_root48_unchanged=True,exact128_value_and_HMR_identities=True,events=events)
    return owners,truths,ledger
