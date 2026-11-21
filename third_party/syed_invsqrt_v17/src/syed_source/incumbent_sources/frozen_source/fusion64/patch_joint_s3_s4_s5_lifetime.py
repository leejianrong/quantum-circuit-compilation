# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Seven-product joint S3/S4/S5 recovery; convert the final elementary helper to S5 in place."""
from pathlib import Path
from fractions import Fraction
import hashlib,json,os,sys
HERE=Path(__file__).resolve().parent


def apply(ctx):
    native=sys.modules['variant_patch_native64_q44_A10_swap']
    h2=sys.modules['variant_patch_patch_h2ret'];old_h2=h2.rebuild_h2
    from native_loader64 import plan as decode_plan
    data=json.loads((HERE/'joint_s3_s4_s5_plan.json').read_text())
    definitions=[decode_plan(p)for p in data['helper_plans']]
    S4plan=decode_plan(data['S4_plan']);S5delta=decode_plan(data['S5_inplace_delta_plan']);pending={};pending5={};ledger={};old_prep=native.prep

    def write():
        Path(os.environ['JOINT_S3_S4_LEDGER']).write_text(json.dumps(ledger,indent=2)+'\n')

    def snapshot(b):
        from branch_prover import generated_text,Program
        from fourier_resource_expectation import exact_expectation
        text=generated_text(b.finish_circuit())
        return dict(owners=b.num_allocated_qubits,operations=len(Program(text).operations),mean=exact_expectation(text)['mean'])

    def affine_xor(b,variables,target,expression,skip=None):
        if expression&1:b.x(target)
        for index in native.cb.bits(expression>>1):
            if index!=skip:b.cx(variables[index],target)

    def rebuild_s3(b,D,S):
        assert not pending
        before=snapshot(b);base=[D[i]for i in range(8,13)]+S[:3];helpers=[];events=[]
        for index,p in enumerate(definitions):
            q=b.alloc_qubits(1)[0];native.cb.emit_xor(b,base,q,p);helpers.append(q)
            events.append(dict(event='prepare_helper',index=index,owner=str(q),owners=b.num_allocated_qubits))
        variables=base+helpers
        s3=b.alloc_qubits(1)[0];affine_xor(b,variables,s3,data['S3_base_affine_expression'])
        pivot=data['difference_pivot_index'];diff=variables[pivot]
        affine_xor(b,variables,diff,data['difference_affine_expression'],skip=pivot)
        split_indices=list(native.cb.bits(data['split_mask']));sp=split_indices[0]
        for i in split_indices[1:]:b.cx(base[i],base[sp])
        if data['split_invert']:b.x(base[sp])
        b.ccx(base[sp],diff,s3)
        if data['split_invert']:b.x(base[sp])
        for i in reversed(split_indices[1:]):b.cx(base[i],base[sp])
        affine_xor(b,variables,diff,data['difference_affine_expression'],skip=pivot)
        events.append(dict(event='S3_completed',owner=str(s3),owners=b.num_allocated_qubits))
        def erase(index):
            q=helpers[index];m=b.alloc_bits(1)[0];b.hmr(q,m);b.free(q)
            native.cb.emit_phase(b,base,m,definitions[index]);b.free(m)
            events.append(dict(event='erase_helper',index=index,owner=str(q),owners=b.num_allocated_qubits,
                               exact_quadratic_phase_repaid=True))
        for index in data['early_erased_helpers']:erase(index)
        s4=b.alloc_qubits(1)[0]
        native.cb.emit_xor(b,base+[helpers[1],helpers[3],s3],s4,S4plan)
        events.append(dict(event='S4_completed',owner=str(s4),owners=b.num_allocated_qubits))
        for index in data['late_erased_helpers']:erase(index)
        s5=helpers[3];native.cb.emit_xor(b,base+[s3,s4],s5,S5delta)
        events.append(dict(event='helper3_becomes_S5_inplace',owner=str(s5),owners=b.num_allocated_qubits))
        pending5[id(b)]=(tuple(base[1:5]+base[5:]+[s3,s4]),s5)
        after=snapshot(b)
        delta={k:str(Fraction(after['mean'][k])-Fraction(v))for k,v in before['mean'].items()}
        assert delta==dict(toffoli_like='7',T='0',generic_rotations='0')
        assert after['owners']==before['owners']+3
        peak=max(e['owners']for e in events);assert peak<=44
        ledger.update(notice=data['notice'],status='NATIVE_SEVEN_PRODUCT_JOINT_S3_S4_S5_RECOVERY',
            entry=before,exit=after,resources=delta,peak=peak,
            base_owners=list(map(str,base)),events=events,S3_owner=str(s3),S4_owner=str(s4),S5_owner=str(s5),retained_helper_unitary_into_S5=True,
            plan_sha256=hashlib.sha256((HERE/'joint_s3_s4_s5_plan.json').read_bytes()).hexdigest(),
            patch_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            helper_HMR_debts_fully_repaid=True,old_S3_S4_outcomes_repaid_by_unchanged_caller=True)
        pending[id(b)]=(tuple(D),S[2],s3,s4);write();return s3

    def rebuild_h2(b,D,s2,s3):
        if id(b)not in pending:return old_h2(b,D,s2,s3)
        oldD,olds2,olds3,s4=pending.pop(id(b));assert tuple(D)==oldD and s2==olds2 and s3==olds3
        ledger['pending_S4_consumed']=True;ledger['S4_consume_owners']=b.num_allocated_qubits;write();return s4

    def prep(b,variables,p):
        if p is native.PLANS.get('S5current') and id(b) in pending5:
            expected,s5=pending5.pop(id(b));assert tuple(variables)==expected
            ledger['pending_S5_consumed']=True;ledger['S5_consume_owners']=b.num_allocated_qubits;write();return s5
        return old_prep(b,variables,p)

    native.rebuild_s3=rebuild_s3;h2.rebuild_h2=rebuild_h2;native.prep=prep
