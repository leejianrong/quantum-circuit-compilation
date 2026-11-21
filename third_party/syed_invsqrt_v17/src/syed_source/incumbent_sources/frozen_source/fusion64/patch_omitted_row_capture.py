# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Native omitted-row decoder with two physical captures and complete cleanup.

This patch is a candidate emitter. Only the unchanged whole-domain native
checker and a byte-identical rebuild can qualify the resulting circuit.
"""
from pathlib import Path
import hashlib,json,os,sys

HERE=Path(__file__).resolve().parent
FULL128=(1<<128)-1
NOTICE='Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.'
STATE={}


class Span:
    def __init__(self,values=()):
        self.p={};self.count=0
        for v in values:self.add(v)
    def add(self,v):
        w=1<<self.count;self.count+=1
        while v:
            k=v.bit_length()-1
            if k not in self.p:self.p[k]=(v,w);return True
            a,c=self.p[k];v^=a;w^=c
        return False
    def solve(self,v):
        w=0
        while v:
            k=v.bit_length()-1
            if k not in self.p:return None
            a,c=self.p[k];v^=a;w^=c
        return w


def xor(values,mask):
    result=0
    while mask:
        bit=mask&-mask;result^=values[bit.bit_length()-1];mask^=bit
    return result


def bits(mask):
    while mask:
        bit=mask&-mask;yield bit.bit_length()-1;mask^=bit


def cnot_frame(rows):
    n=len(rows);work=list(rows);ops=[]
    def cx(c,t):work[t]^=work[c];ops.append((c,t))
    for j in range(n):
        if not work[j]>>j&1:
            i=next(i for i in range(j+1,n) if work[i]>>j&1)
            cx(i,j);cx(j,i);cx(i,j)
        for i in range(n):
            if i!=j and work[i]>>j&1:cx(j,i)
    assert work==[1<<j for j in range(n)]
    return ops[::-1]


def factor_frame(forms,n):
    rows=list(forms);span=Span(rows);assert len(span.p)==len(rows)
    for i in range(n):
        if span.add(1<<i):rows.append(1<<i)
    assert len(rows)==n
    return cnot_frame(rows)


def emit_frame(b,owners,operations):
    for c,t in operations:b.cx(owners[c],owners[t])


def emit_product(b,owners,target,L,R):
    assert target not in owners and L and R and L!=R
    ops=factor_frame([L,R],len(owners));emit_frame(b,owners,ops);b.ccx(owners[0],owners[1],target);emit_frame(b,owners,reversed(ops))


def emit_ccz(b,owners,masks):
    ops=factor_frame(masks,len(owners));emit_frame(b,owners,ops);b.ccz(owners[0],owners[1],owners[2]);emit_frame(b,owners,reversed(ops))


def emit_cz_product(b,owners,L,R):
    ops=factor_frame([L,R],len(owners));emit_frame(b,owners,ops);b.cz(owners[0],owners[1]);emit_frame(b,owners,reversed(ops))


def emit_quadratic(b,owners,coefficient,outcome=None):
    coefficient=int(coefficient,16) if isinstance(coefficient,str) else coefficient
    if coefficient&1:b.z(True if outcome is None else outcome)
    if outcome is not None:b.push_condition(outcome)
    k=1
    for q in owners:
        if coefficient>>k&1:b.z(q)
        k+=1
    for i,q in enumerate(owners):
        for j in range(i):
            if coefficient>>k&1:b.cz(q,owners[j])
            k+=1
    assert coefficient>>k==0
    if outcome is not None:b.pop_condition()


def quadratic_value(values,coefficient):
    columns=[FULL128]+values+[values[i]&values[j] for i in range(len(values)) for j in range(i)]
    return xor(columns,int(coefficient,16) if isinstance(coefficient,str) else coefficient)


def enter(b,outcomes,branch):
    for i,m in enumerate(outcomes):
        if not branch>>i&1:b.x(m)
    for m in outcomes:
        b.push_condition(m)


def leave(b,outcomes,branch):
    for _ in outcomes:
        b.pop_condition()
    for i in reversed(range(len(outcomes))):
        if not branch>>i&1:b.x(outcomes[i])


def erase_joint_qr(b,raw,owners,programs):
    outcomes=list(b.alloc_bits(2))
    for q,m in zip(owners,outcomes):b.hmr(q,m);b.free(q)
    record=[]
    for name,p in programs.items():
        branch=p['branch'];enter(b,outcomes,branch);values=list(raw);helpers=[]
        for L,R in p['ands']:
            q=b.alloc_qubits(1)[0];emit_product(b,values,q,L,R);helpers.append(q);values.append(q)
        for masks in p['cczs']:emit_ccz(b,values,masks)
        emit_quadratic(b,values,p['quad'])
        for j in reversed(range(len(helpers))):
            q=helpers[j];m=b.alloc_bits(1)[0];b.hmr(q,m);b.free(q)
            b.push_condition(m);emit_cz_product(b,values[:7+j],*p['ands'][j]);b.pop_condition();b.free(m)
        leave(b,outcomes,branch);record.append(dict(name=name,branch=branch,executed_nonlinear=len(p['ands'])+len(p['cczs'])))
    for m in outcomes:b.free(m)
    return record


def apply(ctx):
    native=sys.modules['variant_patch_native64_q44_A10_swap']
    bundle_path=HERE/'omitted_row_bundle.json';bundle=json.loads(bundle_path.read_text());cap=bundle['capture'];physical=bundle['physical_frame'];tail=bundle['retained_S_tail'];fphase=bundle['finishing_phase']
    assert fphase['target_original_G_parity']==121 and tail['finishing_original18_mask']==121
    assert [int(x,16) for x in fphase['control_truths_hex']]==[int(x,16) for x in tail['retained_f_phase_control_truths_hex']]
    raw_truths=[int(x,16) for x in cap['raw_truths_hex']];G_truths=[int(x,16) for x in cap['garbage_truths_hex']]
    H=physical['remaining_garbage_basis'];initial_G_frame=physical['actual_targets']+H;assert len(Span(initial_G_frame).p)==18
    initial_G_ops=cnot_frame(initial_G_frame);Gspan=Span(initial_G_frame);record=dict(notice=NOTICE,status='NATIVE_CANDIDATE_EMISSION_AWAITING_FULL_PROOF',source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),bundle_sha256=hashlib.sha256(bundle_path.read_bytes()).hexdigest())

    def settle(b,v,D,S,token,debts,truths,m):
        # Fail closed until the independently bound payment emitter is present.
        from omitted_old_phase_payment import settle_endpoint
        STATE['v0']=v[0]
        record['old_phase_payment']=settle_endpoint(b,v,D,S,token,debts,truths,m)
        assert not debts.pending and token.row_debts[0].consumed
    native.omitted_settle_endpoint=settle

    def decode(b,outputs):
        from native_loader64 import cb,plan
        assert len(outputs)==17 and 'v0' in STATE
        v0=STATE['v0'];entry=b.num_allocated_qubits;assert entry==37
        helper=b.alloc_qubits(1)[0];hp=plan(bundle['helper_preparation']);assert hp.and_count==1
        assert hp.evaluate_factored_functions([raw_truths[0]]+G_truths[:17],FULL128)==G_truths[17]
        cb.emit_xor(b,[v0]+list(outputs),helper,hp)
        Gowners=list(outputs)+[helper];Gvalues=[xor(G_truths,m) for m in initial_G_frame];emit_frame(b,Gowners,initial_G_ops)
        roots=[];basis=[];rootvalues=[];captured=[];steps=[]

        def translate(mask):
            low=mask&1;upper=(mask>>1)&63;gm=mask>>7
            rm=Span(basis).solve(upper);assert rm is not None,(basis,upper)
            cm=Gspan.solve(gm);assert cm is not None
            for index in captured:assert not(cm>>index&1),(index,mask)
            return low|(cm<<1)|(rm<<19)

        for i,step in enumerate(cap['decoder_steps']):
            if i==2:
                continue
            if i==1:
                from shared_prefix_decoder import emit_shared_pair
                assert basis==[48] and len(roots)==1 and not captured
                variables=[v0]+Gowners+roots;values=[raw_truths[0]]+Gvalues+rootvalues
                new_owners,new_values,shared=emit_shared_pair(b,sys.modules[__name__],variables,values,translate)
                assert shared['output_root_parities']==[8,32]
                assert new_values==[xor(raw_truths[1:],m) for m in (8,32)]
                roots.extend(new_owners);rootvalues.extend(new_values);basis.extend([8,32])
                assert basis==[48,8,32]
                # Literal intermediate root-owner record before the final frame.
                steps.append(dict(index=1,new_parity=8,basis=[48,8],owners=list(map(str,roots[:2])),live_owners=41,products=2,capture_index=None,temporary_shared_helper_live=True))
                rows=[2,5,4];ops=cnot_frame(rows);emit_frame(b,roots,ops)
                rootvalues=[xor(rootvalues,m) for m in rows];basis=[8,16,32]
                assert basis==bundle['decoder_steps'][2]['after_basis']==cap['decoder_steps'][3]['before_root_basis']
                assert rootvalues==[xor(raw_truths[1:],m) for m in basis]
                steps.append(dict(index=2,new_parity=32,basis=list(basis),owners=list(map(str,roots)),live_owners=b.num_allocated_qubits,products=1,capture_index=None,temporary_shared_helper_live=False))
                record['shared_prefix']=dict(shared)
                if os.environ.get('SHARED_PREFIX_LEDGER'):
                    Path(os.environ['SHARED_PREFIX_LEDGER']).write_text(json.dumps(record['shared_prefix'],indent=2)+'\n')
                continue
            assert basis==step['before_root_basis']
            variables=[v0]+Gowners+roots;values=[raw_truths[0]]+Gvalues+rootvalues
            linear=translate(step['linear_mask']);target=b.alloc_qubits(1)[0];outvalue=(FULL128 if step['constant'] else 0)^xor(values,linear)
            if step['constant']:b.x(target)
            for j in bits(linear):b.cx(variables[j],target)
            order=[1,0] if i==3 else list(range(len(step['products'])))
            for j in order:
                capture_index=0 if i==3 and j==1 else 1 if i==4 and j==0 else None
                p=step['products'][j];L,R=translate(p['left_mask']),translate(p['right_mask']);product=xor(values,L)&xor(values,R)
                assert product==int(p['truth_hex'],16)
                if capture_index is not None:
                    assert not(L>>(1+capture_index)&1) and not(R>>(1+capture_index)&1)
                    b.cx(target,Gowners[capture_index]);Gvalues[capture_index]^=outvalue
                emit_product(b,variables,target,L,R);outvalue^=product
                if capture_index is not None:
                    b.cx(target,Gowners[capture_index]);Gvalues[capture_index]^=outvalue;captured.append(capture_index)
                values=[raw_truths[0]]+Gvalues+rootvalues
            assert outvalue==xor(raw_truths[1:],step['new_root_parity'])
            roots.append(target);basis.append(step['new_root_parity']);rootvalues.append(outvalue)
            wanted=bundle['decoder_steps'][i]['after_basis'];span=Span(basis);rows=[span.solve(m) for m in wanted];assert all(m is not None for m in rows)
            ops=cnot_frame(rows);emit_frame(b,roots,ops);rootvalues=[xor(rootvalues,m) for m in rows];basis=list(wanted)
            if i==3:
                b.x(Gowners[0]);Gvalues[0]^=FULL128
                for mask in (5,16,32):
                    k=basis.index(mask);b.cx(roots[k],Gowners[0]);Gvalues[0]^=rootvalues[k]
                assert Gvalues[0]==int(tail['canonical_capture_truths_hex'][0],16)
            if i==4:assert Gvalues[1]==int(tail['canonical_capture_truths_hex'][1],16)
            assert rootvalues==[xor(raw_truths[1:],m) for m in basis]
            steps.append(dict(index=i,new_parity=step['new_root_parity'],basis=list(basis),owners=list(map(str,roots)),live_owners=b.num_allocated_qubits,products=len(step['products']),capture_index=(0 if i==3 else 1 if i==4 else None)))
        assert basis==[1,2,4,8,16,32] and b.num_allocated_qubits==44
        assert sum(step['products'] for step in steps)==10
        assert Gvalues[2:]==[xor(G_truths,m) for m in H]
        STATE.update(Gowners=Gowners,Gvalues=Gvalues,raw=[v0]+roots)
        record['decoder']=dict(entry_owners=entry,exit_owners=b.num_allocated_qubits,helper_preparation_Toffolis=1,decoder_products=10,total_Toffolis=11,steps=steps,initial_G_frame_in_original18=initial_G_frame,initial_frame_CNOTs=initial_G_ops,capture_owner_names=list(map(str,Gowners[:2])),captured_truths_hex=list(map(hex,Gvalues[:2])),canonical_q_free_correction='X and CX from decoded root parities5,16,32 immediately after step3')
        return roots
    native.decode_seven_products=decode

    def cleanup(b,address,outputs,data,debts):
        assert not debts.pending and b.num_allocated_qubits==44
        raw=STATE['raw'];Gowners=STATE['Gowners'];Howners=Gowners[2:];Hvalues=STATE['Gvalues'][2:]
        assert raw==[STATE['v0']]+list(address)
        ops=tail['CNOTs_control_target_H16'];emit_frame(b,Howners,ops)
        changed_values=[xor(Hvalues,m) for m in tail['physical_output_rows_in_H16']]
        controls={f'raw{i}':q for i,q in enumerate(raw)};controls.update(q=Gowners[0],r=Gowners[1]);controls.update({f'H{i}':q for i,q in enumerate(Howners)})
        truths={f'raw{i}':t for i,t in enumerate(raw_truths)};truths.update(q=STATE['Gvalues'][0],r=STATE['Gvalues'][1]);truths.update({f'H{i}':t for i,t in enumerate(changed_values)})
        free_erasures=[]
        def erase_step(step):
            target_label=step['target_owner'];variables=[controls[name] for name in step['control_labels']];values=[truths[name] for name in step['control_labels']]
            assert quadratic_value(values,step['quadratic_coefficient_hex'])==truths[target_label]
            q=controls.pop(target_label);truths.pop(target_label);m=b.alloc_bits(1)[0];b.hmr(q,m);b.free(q)
            emit_quadratic(b,variables,step['quadratic_coefficient_hex'],m);b.free(m)
            free_erasures.append(dict(target=target_label,owner=str(q),live_owners=b.num_allocated_qubits))
        for step in tail['erase_six_steps']:erase_step(step)
        fcontrols=[controls[name] for name in tail['retained_f_phase_control_labels']];fvalues=[truths[name] for name in tail['retained_f_phase_control_labels']]
        assert [hex(v) for v in fvalues]==fphase['control_truths_hex']
        phase=quadratic_value(fvalues,fphase['free_quadratic_coefficient_hex'])
        for masks in fphase['CCZ_control_masks']:phase^=xor(fvalues,masks[0])&xor(fvalues,masks[1])&xor(fvalues,masks[2])
        assert phase==truths['H9']==int(fphase['target_truth_hex'],16)
        f=controls.pop('H9');truths.pop('H9');m=b.alloc_bits(1)[0];b.hmr(f,m);b.free(f)
        b.push_condition(m)
        for masks in fphase['CCZ_control_masks']:emit_ccz(b,fcontrols,masks)
        b.pop_condition();emit_quadratic(b,fcontrols,fphase['free_quadratic_coefficient_hex'],m);b.free(m)
        for step in tail['erase_S9_steps']:erase_step(step)
        assert b.num_allocated_qubits==28
        joint=erase_joint_qr(b,raw,Gowners[:2],bundle['joint_qr_programs'])
        assert b.num_allocated_qubits==26 and not debts.pending
        STATE.clear();record['cleanup']=dict(entry_owners=44,after_R6=38,after_f=37,after_S9=28,exit_owners=26,extra_quantum_owners=0,free_erasures=free_erasures,finishing_f_original18_mask=121,finishing_CCZs=2,finishing_expected_Toffolis='1',joint_qr_cases=joint,joint_qr_expected_Toffolis='5/2',total_expected_Toffolis='7/2')
        Path(os.environ['OMITTED_ROW_LEDGER']).write_text(json.dumps(record,indent=2)+'\n')
    native.cleanup_loader=cleanup


def emit_body(*args,**kwargs):
    return sys.modules['variant_patch_native64_q44_A10_swap'].emit_body(*args,**kwargs)
