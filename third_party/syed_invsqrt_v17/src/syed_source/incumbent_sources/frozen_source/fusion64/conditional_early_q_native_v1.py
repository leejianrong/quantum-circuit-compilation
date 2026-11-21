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


# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Native value and phase helpers for the changed-q conditional cleanup."""


def emit_affine_xor(b, owners, target, coefficient):
    if coefficient & 1:
        b.x(target)
    for j in bits(coefficient >> 1):
        b.cx(owners[j], target)


def emit_changed_decoder_tail(b, index, variables, values, Gowners, Gvalues,
                              roots, basis, rootvalues, raw_truths, changed, wanted):
    endpoint = changed['changed_q_physical_value_endpoint']
    chart = changed['value_chart']
    target = b.alloc_qubits(1)[0]
    if index == 4:
        assert basis == [5, 8, 16, 32]
        assert values == [int(v, 16) for v in chart['pre_capture_control_truths_hex']]
        Bowners, Bvalues = variables[:2] + variables[3:], values[:2] + values[3:]
        assert Bvalues == [int(v, 16) for v in chart['product_control_truths_hex']]
        coefficient = endpoint['root4_initial_affine_mask_in_1_C']
        emit_affine_xor(b, variables, target, coefficient)
        outvalue = xor([FULL128] + values, coefficient)
        left, right = endpoint['captured_product_factor_masks_in_B']
        assert not ((left | right) & 2), 'The product must exclude both capture owners.'
        product = xor(Bvalues, left) & xor(Bvalues, right)
        for j in (0, 1):
            b.cx(target, Gowners[j])
            Gvalues[j] ^= outvalue
        emit_product(b, Bowners, target, left, right)
        outvalue ^= product
        for j in (0, 1):
            b.cx(target, Gowners[j])
            Gvalues[j] ^= outvalue
        Uvalues = [raw_truths[0]] + Gvalues + rootvalues
        assert Uvalues == [int(v, 16) for v in endpoint['after_capture_control_truths_hex']]
        answer = endpoint['remaining_root4']['answer']
        emit_product(b, variables, target, answer['left_mask'], answer['right_mask'])
        outvalue ^= xor(Uvalues, answer['left_mask']) & xor(Uvalues, answer['right_mask'])
        post = endpoint['root4_post_affine_mask_in_U']
        emit_affine_xor(b, variables, target, post << 1)
        outvalue ^= xor(Uvalues, post)
        charged, new_parity = 2, 4
        assert outvalue == raw_truths[3]
    elif index == 5:
        assert basis == [1, 4, 8, 16, 32]
        Wvalues = [int(v, 16) for v in endpoint['after_capture_control_truths_hex']] + [raw_truths[3]]
        physical = Span(values)
        mapping = [physical.solve(v) for v in Wvalues]
        assert all(m is not None for m in mapping)
        answer = endpoint['final_root2']['answer']
        coefficient = answer['affine_mask']
        physical_affine = (xor(mapping, coefficient >> 1) << 1) | (coefficient & 1)
        emit_affine_xor(b, variables, target, physical_affine)
        outvalue = xor([FULL128] + Wvalues, coefficient)
        left, right = xor(mapping, answer['left_mask']), xor(mapping, answer['right_mask'])
        emit_product(b, variables, target, left, right)
        outvalue ^= xor(values, left) & xor(values, right)
        charged, new_parity = 1, 2
        assert outvalue == raw_truths[2]
    else:
        raise AssertionError(index)
    roots.append(target)
    basis.append(new_parity)
    rootvalues.append(outvalue)
    root_span = Span(basis)
    rows = [root_span.solve(p) for p in wanted]
    assert all(m is not None for m in rows)
    emit_frame(b, roots, cnot_frame(rows))
    old_values = list(rootvalues)
    rootvalues[:] = [xor(old_values, m) for m in rows]
    basis[:] = wanted
    assert rootvalues == [xor(raw_truths[1:], m) for m in basis]
    return dict(index=index, new_parity=new_parity, basis=list(basis), owners=list(map(str, roots)),
                live_owners=b.num_allocated_qubits, products=charged, capture_index=[0, 1] if index == 4 else None,
                changed_q_and_r_capture=True, captured_truths_hex=list(map(hex, Gvalues[:2])))


def emit_phase_event(b, variables, values, target_value, event, outcome):
    phase = quadratic_value(values, event['quadratic_coefficient_hex'])
    for masks in event['CCZs']:
        phase ^= xor(values, masks[0]) & xor(values, masks[1]) & xor(values, masks[2])
    assert phase == target_value
    if event['CCZs']:
        b.push_condition(outcome)
        for masks in event['CCZs']:
            emit_ccz(b, variables, masks)
        b.pop_condition()
    emit_quadratic(b, variables, event['quadratic_coefficient_hex'], outcome)


# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Phase programs and shared owner retirement for conditional early q HMR."""


def emit_checked_phase_program(b, owners, truths, target_truth, program):
    phase_owners, phase_truths = list(owners), list(truths)
    helpers = []
    for left, right in program['ands']:
        helper = b.alloc_qubits(1)[0]
        emit_product(b, phase_owners, helper, left, right)
        helpers.append(helper)
        phase_truths.append(xor(phase_truths, left) & xor(phase_truths, right))
        phase_owners.append(helper)
    phase = quadratic_value(phase_truths, program['quad'])
    for masks in program['cczs']:
        factors = [xor(phase_truths, m) for m in masks]
        phase ^= factors[0] & factors[1] & factors[2]
    assert phase == target_truth
    for masks in program['cczs']:
        emit_ccz(b, phase_owners, masks)
    emit_quadratic(b, phase_owners, program['quad'])
    n = len(owners)
    for j in reversed(range(len(helpers))):
        outcome = b.alloc_bits(1)[0]
        b.hmr(helpers[j], outcome)
        b.free(helpers[j])
        b.push_condition(outcome)
        emit_cz_product(b, phase_owners[:n+j], *program['ands'][j])
        b.pop_condition()
        b.free(outcome)
    return len(program['ands']) + len(program['cczs'])


def emit_early_q_S9_event(b, owners, truths, target_truth, event, outcome):
    b.push_condition(outcome)
    charged = emit_checked_phase_program(b, owners, truths, target_truth, event['phase_program'])
    b.pop_condition()
    return charged


def erase_early_q_conditional_tail(b, raw, raw_truths, auxiliary, r_owner,
                                  htruth, qr_truths, mP, changed):
    # The auxiliary owner holds h in the active branch and q in the inactive
    # branch. Correct h immediately, while the required r value is still live.
    mAux = b.alloc_bits(1)[0]
    b.hmr(auxiliary, mAux)
    b.free(auxiliary)
    assert b.num_allocated_qubits == 27
    feedback = changed['helper_after_S9_phase']
    helper_controls, helper_values = raw + [r_owner], raw_truths + [qr_truths[1]]
    assert helper_values == [int(v, 16) for v in feedback['control_truths_hex']]
    assert quadratic_value(helper_values, feedback['quadratic_coefficient_hex']) == htruth
    b.push_condition(mP)
    emit_quadratic(b, helper_controls, feedback['quadratic_coefficient_hex'], mAux)
    b.pop_condition()
    mR = b.alloc_bits(1)[0]
    b.hmr(r_owner, mR)
    b.free(r_owner)
    assert b.num_allocated_qubits == 26
    ledger = []
    enter(b, [mP], 0)
    for name, program in changed['inactive_late_qr_programs'].items():
        branch = program['branch']
        target = (qr_truths[0] if branch & 1 else 0) ^ (qr_truths[1] if branch & 2 else 0)
        enter(b, [mAux, mR], branch)
        count = emit_checked_phase_program(b, raw, raw_truths, target, program)
        leave(b, [mAux, mR], branch)
        ledger.append(dict(pivot_branch=0, name=name, late_branch=branch, charged_gates=count))
    leave(b, [mP], 0)
    b.push_condition(mP)
    b.push_condition(mR)
    count = emit_checked_phase_program(b, raw, raw_truths, qr_truths[1], changed['active_late_r_program'])
    b.pop_condition()
    b.pop_condition()
    ledger.append(dict(pivot_branch=1, name='r', charged_gates=count))
    b.free(mAux)
    b.free(mR)
    return ledger


def apply(ctx):
    native=sys.modules['variant_patch_native64_q44_A10_swap']
    bundle_path=HERE/'omitted_row_bundle.json';bundle=json.loads(bundle_path.read_text());cap=bundle['capture'];physical=bundle['physical_frame'];tail=bundle['retained_S_tail'];fphase=bundle['finishing_phase']
    assert fphase['target_original_G_parity']==121 and tail['finishing_original18_mask']==121
    assert [int(x,16) for x in fphase['control_truths_hex']]==[int(x,16) for x in tail['retained_f_phase_control_truths_hex']]
    changed_path=HERE/'conditional_early_q_bundle_v1.json';changed=json.loads(changed_path.read_text())
    raw_truths=[int(x,16) for x in cap['raw_truths_hex']];G_truths=[int(x,16) for x in cap['garbage_truths_hex']]
    H=physical['remaining_garbage_basis'];initial_G_frame=physical['actual_targets']+H;assert len(Span(initial_G_frame).p)==18
    initial_G_ops=cnot_frame(initial_G_frame);Gspan=Span(initial_G_frame);record=dict(notice=NOTICE,status='NATIVE_CANDIDATE_EMISSION_AWAITING_FULL_PROOF',source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),bundle_sha256=hashlib.sha256(bundle_path.read_bytes()).hexdigest())

    record['changed_capture_bundle_sha256']=hashlib.sha256(changed_path.read_bytes()).hexdigest()
    record['changed_capture_ledger']=changed['exact_expected_ledger']

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
            if i in (4,5):
                variables=[v0]+Gowners+roots;values=[raw_truths[0]]+Gvalues+rootvalues
                entry=emit_changed_decoder_tail(b,i,variables,values,Gowners,Gvalues,roots,basis,rootvalues,raw_truths,changed,bundle['decoder_steps'][i]['after_basis'])
                if i==4:captured.append(1)
                steps.append(entry)
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
        assert sum(step['products'] for step in steps)==9
        assert Gvalues[2:]==[xor(G_truths,m) for m in H]
        STATE.update(Gowners=Gowners,Gvalues=Gvalues,raw=[v0]+roots)
        record['decoder']=dict(entry_owners=entry,exit_owners=b.num_allocated_qubits,helper_preparation_Toffolis=1,decoder_products=9,total_Toffolis=10,steps=steps,initial_G_frame_in_original18=initial_G_frame,initial_frame_CNOTs=initial_G_ops,capture_owner_names=list(map(str,Gowners[:2])),captured_truths_hex=list(map(hex,Gvalues[:2])),canonical_q_free_correction='X and CX from decoded root parities5,16,32 immediately after step3')
        return roots
    native.decode_seven_products=decode

    # Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
    # Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
    # Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
    # supporting the research.
    # Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
    # Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
    # Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
    # supporting the research.
    def cleanup(b, address, outputs, data, debts):
        assert not debts.pending and b.num_allocated_qubits == 44
        raw, Gowners, Gvalues = STATE['raw'], STATE['Gowners'], STATE['Gvalues']
        assert raw == [STATE['v0']] + list(address)
        # The double capture gives q=oldq+P and r=oldb+P. This CNOT makes qbar.
        b.cx(Gowners[1], Gowners[0])
        Gvalues[0] ^= Gvalues[1]
        frame_values = [int(v, 16) for v in changed['capture_frame_control_truths_hex']]
        affine_controls = raw + Gowners[2:]
        affine_values = raw_truths + Gvalues[2:]
        affine_span = Span([FULL128] + affine_values)
        capture_frames = []
        for index, key in enumerate(('q_capture_frame', 'r_capture_frame')):
            frame = changed[key]
            delta = xor(frame_values, frame['early_affine_mask_in_O'])
            delta ^= xor([FULL128] + raw_truths, frame['late_affine_mask_on_1_raw7'])
            physical_mask = affine_span.solve(delta)
            assert physical_mask is not None
            emit_affine_xor(b, affine_controls, Gowners[index], physical_mask)
            Gvalues[index] ^= delta
            assert Gvalues[index] == int(frame['truth_hex'], 16)
            capture_frames.append(dict(name=key, physical_affine_mask_on_1_raw7_G16=physical_mask,
                                       resulting_truth_hex=hex(Gvalues[index])))
        Howners, Hvalues = Gowners[2:], Gvalues[2:]
        emit_frame(b, Howners, tail['CNOTs_control_target_H16'])
        Htruths = [xor(Hvalues, m) for m in tail['physical_output_rows_in_H16']]
        assert Htruths == [int(v, 16) for v in changed['H16_truths_hex']]
        outer = changed['outer_H_frame_and_free_closure']
        rows = outer['H16_basis_masks']
        assert len(rows) == 16 and len(Span(rows).p) == 16
        emit_frame(b, Howners, cnot_frame(rows))
        owners_by_mask = dict(zip(rows, Howners))
        base_owners = raw + Gowners[:2]
        base_truths = raw_truths + Gvalues[:2]
        assert base_truths == [int(v, 16) for v in changed['base_control_truths_hex']]
        retirements = []
        for event in reversed(outer['free_steps']):
            target_mask = event['target_H16_mask']
            previous = event['previous_H16_masks']
            variables = base_owners + [owners_by_mask[m] for m in previous]
            values = base_truths + [xor(Htruths, m) for m in previous]
            target = owners_by_mask.pop(target_mask)
            assert target not in variables
            m = b.alloc_bits(1)[0]
            b.hmr(target, m)
            b.free(target)
            free_event = dict(event, CCZs=[])
            emit_phase_event(b, variables, values, xor(Htruths, target_mask), free_event, m)
            b.free(m)
            retirements.append(dict(H16_mask=target_mask, kind='outer_free', live_owners=b.num_allocated_qubits))
        assert b.num_allocated_qubits == 38
        pivot = changed['pivot_H16_mask']
        target = owners_by_mask.pop(pivot)
        mP = b.alloc_bits(1)[0]
        b.hmr(target, mP)
        b.free(target)
        assert b.num_allocated_qubits == 37
        Sowners = [owners_by_mask[1 << j] for j in range(9)]
        assert len(owners_by_mask) == 9
        Eowners, Etruths = base_owners + Sowners, base_truths + Htruths[:9]
        helper = b.alloc_qubits(1)[0]
        hp = changed['active_helper']
        htruth = int(hp['helper_truth_hex'], 16)
        assert htruth == (xor(Etruths, hp['preparation_factor_masks'][0]) & xor(Etruths, hp['preparation_factor_masks'][1])) ^ xor([FULL128] + Etruths, hp['preparation_affine_mask_on_1_E'])
        b.push_condition(mP)
        emit_product(b, Eowners, helper, *hp['preparation_factor_masks'])
        emit_affine_xor(b, Eowners, helper, hp['preparation_affine_mask_on_1_E'])
        pivot_controls, pivot_values = Eowners + [helper], Etruths + [htruth]
        phase = quadratic_value(pivot_values, changed['active_pivot_quadratic_coefficient_hex'])
        factors = [xor(pivot_values, m) for m in changed['active_pivot_CCZ_masks']]
        assert phase ^ (factors[0] & factors[1] & factors[2]) == xor(Htruths, pivot)
        emit_ccz(b, pivot_controls, changed['active_pivot_CCZ_masks'])
        emit_quadratic(b, pivot_controls, changed['active_pivot_quadratic_coefficient_hex'])
        b.pop_condition()
        assert b.num_allocated_qubits == 38
        # Reuse the allocated helper owner as q storage on the inactive branch.
        # The original q owner can then undergo one unconditional early HMR.
        enter(b, [mP], 0)
        b.cx(Gowners[0], helper)
        b.cx(helper, Gowners[0])
        b.cx(Gowners[0], helper)
        leave(b, [mP], 0)
        mEarly = b.alloc_bits(1)[0]
        b.hmr(Gowners[0], mEarly)
        b.free(Gowners[0])
        assert b.num_allocated_qubits == 37
        inactive_base_owners = raw + [helper, Gowners[1]]
        inactive_base_truths = base_truths
        active_base_owners = raw + [Gowners[1], helper]
        active_base_truths = raw_truths + [Gvalues[1], htruth]
        assert active_base_truths == [int(v, 16) for v in changed['active_base_after_q_truths_hex']]
        early = changed['early_q_HMR']
        early_owners, early_truths = active_base_owners + Sowners, active_base_truths + Htruths[:9]
        assert early_truths == [int(v, 16) for v in early['control_truths_hex']]
        assert quadratic_value(early_truths, early['quadratic_coefficient_hex']) == Gvalues[0]
        b.push_condition(mP)
        emit_quadratic(b, early_owners, early['quadratic_coefficient_hex'], mEarly)
        b.pop_condition()
        b.free(mEarly)
        retirements.append(dict(kind='shared_early_q_HMR', active_target='q', inactive_target='zero', live_owners=37))
        # Both branches still use the same nine physical S9 measurements. Their
        # base controls now have different meanings in the common auxiliary owner.
        branch_events = changed['native_early_q_S9_events']
        branch_owners = []
        for branch in (0, 1):
            events = branch_events[str(branch)]
            Srows = [event['target_H16_mask'] for event in events]
            assert len(Srows) == 9 and len(Span(Srows).p) == 9 and max(Srows) < 512
            enter(b, [mP], branch)
            emit_frame(b, Sowners, cnot_frame(Srows))
            leave(b, [mP], branch)
            branch_owners.append(dict(zip(Srows, Sowners)))
        for j in reversed(range(9)):
            m = b.alloc_bits(1)[0]
            b.hmr(Sowners[j], m)
            b.free(Sowners[j])
            branch_record = []
            for branch in (0, 1):
                event = branch_events[str(branch)][j]
                target_mask = event['target_H16_mask']
                assert branch_owners[branch].pop(target_mask) == Sowners[j]
                previous = event['previous_H16_masks']
                if branch:
                    variables, values = list(active_base_owners), list(active_base_truths)
                else:
                    variables, values = list(inactive_base_owners), list(inactive_base_truths)
                variables += [branch_owners[branch][p] for p in previous]
                values += [xor(Htruths, p) for p in previous]
                assert Sowners[j] not in variables
                enter(b, [mP], branch)
                charged = emit_early_q_S9_event(b, variables, values, xor(Htruths, target_mask), event, m)
                leave(b, [mP], branch)
                branch_record.append(dict(branch=branch, H16_mask=target_mask, charged_phase_gates=charged))
            b.free(m)
            retirements.append(dict(kind='shared_S9_HMR', physical_index=j, branches=branch_record,
                                    live_owners=b.num_allocated_qubits))
        assert not any(branch_owners) and b.num_allocated_qubits == 28
        joint = erase_early_q_conditional_tail(b, raw, raw_truths, helper, Gowners[1],
                                              htruth, Gvalues[:2], mP, changed)
        b.free(mP)
        assert b.num_allocated_qubits == 26 and not debts.pending
        STATE.clear()
        record['cleanup'] = dict(entry_owners=44, after_outer_six_HMR=38, after_pivot_HMR=37,
                                 conditional_helper_allocated_peak=38, after_early_q_HMR=37,
                                 after_nine_S9_HMR=28, after_auxiliary_HMR=27, exit_owners=26,
                                 capture_frames=capture_frames, H16_frame_rows=rows, pivot_H16_mask=pivot,
                                 retirements=retirements, helper_quadratic_mask=hp['mask'],
                                 shared_S9_HMR_count=9, shared_early_q_HMR_count=1,
                                 H_cleanup_expected_Toffolis='2', joint_qr_cases=joint,
                                 joint_qr_expected_Toffolis='15/8', total_expected_Toffolis='31/8',
                                 maximum_seed_phase_owners=30, maximum_late_joint_phase_owners=29,
                                 value_and_phase_scope='unchanged double capture, helper541184, active early q HMR, seed467, shared inactive q/helper owner')
        Path(os.environ['OMITTED_ROW_LEDGER']).write_text(json.dumps(record, indent=2) + '\n')
    native.cleanup_loader=cleanup


def emit_body(*args,**kwargs):
    return sys.modules['variant_patch_native64_q44_A10_swap'].emit_body(*args,**kwargs)
