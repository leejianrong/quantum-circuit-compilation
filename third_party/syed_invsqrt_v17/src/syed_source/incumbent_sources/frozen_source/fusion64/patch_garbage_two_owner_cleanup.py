# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Clifford parity erasure to two owners, followed by exact joint HMR phases."""
from pathlib import Path
from fractions import Fraction
import hashlib
import json
import os
import sys
from native_loader64 import cb,plan,FULL


def apply(ctx):
    native=sys.modules['variant_patch_native64_q44_A10_swap']
    path=Path(os.environ['GARBAGE_PARITY_PLAN']);certificate=json.loads(path.read_text())
    assert certificate['status']=='EXACT_TWO_OWNER_PARITY_GARBAGE_CLEANUP_PLAN'
    tail_count=len(certificate['seed_masks']);assert tail_count==2
    branch_count=1<<tail_count

    def cleanup(b,address,outputs,data,debts):
        raw=cb.word_functions(range(64),6);output_truths=[int(t,16)for t in data['output_truths']]
        assert len(outputs)==17
        helper=native.GARBAGE_DECODER_HELPER
        values=output_truths+[int(certificate['decoder_helper_truth_hex'],16)]
        assert [f'{x:016x}'for x in values]==certificate['garbage_truths_hex']
        entry=b.num_allocated_qubits;assert entry==44
        debts.flush(b,list(address)+list(outputs),raw+output_truths)
        owners=list(outputs)+[helper];basis=[1<<i for i in range(18)]
        for operation,i,j in certificate['basis_conversion_operations']:
            if operation=='swap':owners[i],owners[j]=owners[j],owners[i];basis[i],basis[j]=basis[j],basis[i]
            else:b.cx(owners[i],owners[j]);basis[j]^=basis[i]
        assert basis==certificate['basis_masks']
        def truth(mask):
            value=0
            for i in cb.bits(mask):value^=values[i]
            return value
        erasures=[]
        for step in certificate['free_erasure_steps']:
            assert basis[-1]==step['mask'] and basis[:-1]==step['before_masks']
            q=owners.pop();basis.pop();p=plan(step['plan'])
            variables=list(address)+owners;functions=raw+[truth(m)for m in basis]
            assert p.evaluate_functions(functions,FULL)==truth(step['mask'])
            outcome=b.alloc_bits(1)[0];b.hmr(q,outcome);b.free(q)
            cb.emit_phase(b,variables,outcome,p);b.free(outcome)
            erasures.append(dict(mask=step['mask'],remaining_basis=basis.copy(),owner=str(q),live_owners=b.num_allocated_qubits,Toffolis=0))
        assert basis==certificate['seed_masks'] and len(owners)==tail_count and b.num_allocated_qubits==26+tail_count
        outcomes=[]
        for q in owners:
            m=b.alloc_bits(1)[0];b.hmr(q,m);b.free(q);outcomes.append(m)
        assert b.num_allocated_qubits==26
        def enter(branch):
            for i,m in enumerate(outcomes):
                if not(branch>>i&1):b.x(m)
                b.push_condition(m)
        def leave(branch):
            for i in reversed(range(tail_count)):
                b.pop_condition()
                if not(branch>>i&1):b.x(outcomes[i])
        cases=[]
        for case in certificate['cases']:
            branch=case['branch'];helpers=[];functions=list(raw);made=[]
            enter(branch)
            for helper_plan,truth_hex in zip(case['helper_plans'],case['helper_truths_hex']):
                p=plan(helper_plan);assert p.and_count==1 and p.width==6+len(helpers)
                truthv=p.evaluate_functions(functions,FULL);assert truthv==int(truth_hex,16)
                q=b.alloc_qubits(1)[0];cb.emit_xor(b,list(address)+helpers,q,p)
                helpers.append(q);functions.append(truthv);made.append(dict(owner=str(q),truth_hex=truth_hex,live_owners=b.num_allocated_qubits))
            p=plan(case['phase_plan']);variables=list(address)+helpers
            assert p.evaluate_functions(functions,FULL)==int(case['target_truth_hex'],16)
            if p.constant:b.z(True)
            for i in cb.bits(p.linear):b.z(variables[i])
            for i,j in p.edges:b.cz(variables[i],variables[j])
            leave(branch)
            for index in reversed(range(len(helpers))):
                q=helpers.pop();m=b.alloc_bits(1)[0];b.hmr(q,m);b.free(q)
                enter(branch);cb.emit_phase(b,list(address)+helpers,m,plan(case['helper_plans'][index]));leave(branch);b.free(m)
            assert b.num_allocated_qubits==26
            cases.append(dict(branch=branch,helper_count=case['helpers'],conditional_probability=str(Fraction(1,branch_count)),expected_Toffolis=str(Fraction(case['helpers'],branch_count)),helper_owners=made,helper_cleanup_Toffolis=0))
        for m in outcomes:b.free(m)
        native.GARBAGE_DECODER_HELPER=None
        assert not debts.pending and b.num_allocated_qubits==26
        record=dict(notice=certificate['notice'],status='NATIVE_TWO_OWNER_GARBAGE_PARITY_COMPLETE_LIFETIME_LEDGER',
                    entry_owners=entry,peak=entry,exit_owners=b.num_allocated_qubits,
                    decoder_helper_owner=str(helper),basis_masks=certificate['basis_masks'],
                    conversion_matrix_rows=certificate['conversion_matrix_rows'],free_erasure_steps=erasures,
                    tail_owner_truths=certificate['seed_truths_hex'],joint_HMR_case_count=branch_count,cases=cases,
                    expected_Toffolis=str(sum(Fraction(c['helper_count'],branch_count)for c in cases)),
                    plan_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        assert record['expected_Toffolis']=='5/2'
        Path(os.environ['GARBAGE_PARITY_LEDGER']).write_text(json.dumps(record,indent=2)+'\n')
    native.cleanup_loader=cleanup
