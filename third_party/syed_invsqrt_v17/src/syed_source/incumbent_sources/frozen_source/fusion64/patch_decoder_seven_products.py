# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Seven-product native decoder retaining its helper for the following garbage cleanup."""
from pathlib import Path
import hashlib
import inspect
import json
import os
import sys


def emit_body(*args, **kwargs):
    return sys.modules['variant_patch_native64_q44_A10_swap'].emit_body(*args, **kwargs)


def conversion(current, wanted):
    n=len(current);span={0:0}
    for i,value in enumerate(current):
        span.update({key^value:mask^(1<<i)for key,mask in list(span.items())})
    matrix=[span[value]for value in wanted];original=matrix.copy();ops=[]
    for j in range(n):
        pivot=next(i for i in range(j,n)if matrix[i]>>j&1)
        if pivot!=j:
            matrix[j],matrix[pivot]=matrix[pivot],matrix[j];ops.append(('swap',j,pivot))
        for i in range(n):
            if i!=j and matrix[i]>>j&1:
                matrix[i]^=matrix[j];ops.append(('cx',j,i))
    assert matrix==[1<<i for i in range(n)]
    ops.reverse();actual=list(current)
    for op,a,b in ops:
        if op=='swap':actual[a],actual[b]=actual[b],actual[a]
        else:actual[b]^=actual[a]
    assert actual==list(wanted)
    return original,ops


def apply(ctx):
    native=sys.modules['variant_patch_native64_q44_A10_swap']
    path=Path(os.environ['RETAINED_DECODER_PLAN']);data=json.loads(path.read_text())
    steps=data['best']['steps'];assert len(steps)==6 and data['best']['cost']==7

    def decode(b,outputs):
        from loader64 import cb,NOTICE
        from native_loader64 import plan as decode_plan
        full=(1<<64)-1
        table=json.loads(native.SECOND.read_text())
        functions=[int(t,16)for t in data['metadata_truths_hex']]
        assert len(outputs)==17 and len(functions)==17
        roots=cb.word_functions(range(64),6)
        def truth(mask):
            value=0
            for i in cb.bits(mask):value^=roots[i]
            return value
        entry=b.num_allocated_qubits;helpers=[];helper_truths=[];owners=[];basis=[];ledger=[];prepared=[]
        for rank,item in enumerate(steps,1):
            assert basis==item['before_basis']
            if rank==1:
                assert basis==data['helper_preparation_root_basis']==[]
                prep=decode_plan(data['helper_preparation_plan']);assert prep.and_count==1
                variables=outputs+owners;values=functions+[truth(m)for m in basis]
                value=prep.evaluate_functions(values,full)
                assert value==int(data['helper_truths_hex'][0],16)
                helper=b.alloc_qubits(1)[0];cb.emit_xor(b,variables,helper,prep)
                helpers.append(helper);helper_truths.append(value)
                prepared.append(dict(after_rank=0,helper_owner=str(helper),truth_hex=f'{value:016x}',
                                     live_owners=b.num_allocated_qubits,Toffolis=1))
            variables=outputs+helpers+owners
            values=functions+helper_truths+[truth(m)for m in basis]
            formula=decode_plan(item['plan'])
            assert formula.and_count==item['Toffolis']==1
            assert formula.evaluate_functions(values,full)==truth(item['new_parity'])
            target=b.alloc_qubits(1)[0];peak=b.num_allocated_qubits
            cb.emit_xor(b,variables,target,formula)
            owners.append(target);basis.append(item['new_parity'])
            matrix,ops=conversion(basis,item['after_basis'])
            for op,i,j in ops:
                if op=='swap':owners[i],owners[j]=owners[j],owners[i]
                else:b.cx(owners[i],owners[j])
            basis=list(item['after_basis'])
            assert b.num_allocated_qubits==entry+rank+len(helpers) and peak<=44
            ledger.append(dict(rank=rank,entry_owners=entry,live_owners=b.num_allocated_qubits,
                              transition_peak=peak,helper_count=len(helpers),helper_owners=list(map(str,helpers)),
                              Toffolis=1,new_parity=item['new_parity'],basis=basis.copy(),
                              conversion_matrix_rows=matrix,basis_conversion=ops,physical_owners=list(map(str,owners))))
        assert basis==[1,2,4,8,16,32] and len(helpers)==1
        helper=helpers[0];native.GARBAGE_DECODER_HELPER=helper
        assert b.num_allocated_qubits==entry+7
        record=dict(notice=NOTICE,status='NATIVE_SEVEN_PRODUCT_DECODER_HELPER_RETAINED_FOR_CLEANUP',
                    entry_owners=entry,peak=max(step['transition_peak']for step in ledger),Toffolis=7,
                    standalone_helper_preparation=prepared,root_products=sum(step['Toffolis']for step in ledger),
                    helper_cleanup_Toffolis=0,steps=ledger,exit_owners=b.num_allocated_qubits,
                    retained_helper_owner=str(helper),retained_helper_truth_hex=f'{helper_truths[0]:016x}',
                    helper_phase_scope='Retained for the complete eighteen-owner garbage parity cleanup',
                    plan_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        Path(os.environ['RETAINED_DECODER_LEDGER']).write_text(json.dumps(record,indent=2)+'\n')
        return owners

    source=inspect.getsource(native.emit_body)
    endpoint_old="""    outputs=D+[q for q in S if q is not None]
    data=dict(cert2,reusable_input_bits=list(range(6)),fixed_address_bits=[],output_truths=[t for i,t in enumerate(cert2['output_truths'])if i not in(13,14)])
"""
    endpoint_new="""    assert D[11] is None and D[12] is None and S[1] is not None
    outputs=D[:11]+[S[i]for i in(2,3,4,5,6,1)]
    changed_truths=cb.word_functions(table['A'],13)[:11]+[truths['S'][i]for i in(2,3,4,5,6,1)]
    data=dict(cert2,reusable_input_bits=list(range(6)),fixed_address_bits=[],output_truths=[f'{t:016x}'for t in changed_truths])
"""
    assert source.count(endpoint_old)==1
    source=source.replace(endpoint_old,endpoint_new)
    old="""    address=[None]*6;decode_plan_data=json.loads((HERE/'decoder_dp_early01.json').read_text())
    for item in decode_plan_data['steps']:
        variables=outputs+[address[i]for i in range(6)if item['before_mask']>>i&1]
        address[item['bit']]=prep(b,variables,decode_plan(item['plan']))
"""
    assert source.count(old)==1
    native.decode_seven_products=decode
    exec(compile(source.replace(old,'    address=decode_seven_products(b,outputs)\n'),
                 str(Path(__file__))+':emit_body','exec'),native.__dict__)
