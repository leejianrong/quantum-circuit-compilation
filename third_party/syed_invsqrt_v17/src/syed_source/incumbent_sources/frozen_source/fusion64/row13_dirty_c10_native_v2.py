# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Cascade with outcome-selected quadratic row12 bank and one-CCZ phase.

The root-owned phase helper is imported only when its exact path is supplied.
All source owners, old CarryDebt records, and new HMR outcomes stay explicit.
"""
from fractions import Fraction
from pathlib import Path
import hashlib,importlib.util,json,os,sys
from row12_dirty_top import initial_plan
NOTICE='Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.'

class DebtBuilder:
    def __init__(self,base,kept):
        self.base=base;self.kept=kept;self.live=set();self.protected=set();self.conditions=[];self.hoisted=[];self.guarded=[]
    def __getattr__(self,name):return getattr(self.base,name)
    def alloc_bits(self,count):
        result=self.base.alloc_bits(count);self.kept.update(result);return result
    def alloc_qubits(self,count):
        result=self.base.alloc_qubits(count);self.live.update(result);return result
    def free(self,wire):
        if wire not in self.kept:self.live.discard(wire);self.base.free(wire)
    def push_condition(self,bit):self.conditions.append(bit);self.base.push_condition(bit)
    def pop_condition(self):self.conditions.pop();self.base.pop_condition()
    def del_and(self,a,c,target):
        result=self.alloc_bits(1)[0];self.hmr(target,result)
        self.push_condition(result);self.base.cz(a,c);self.pop_condition();self.free(result)
    def hmr(self,wire,outcome):
        if self.conditions and wire in self.live and wire not in self.protected:
            guards=list(self.conditions)
            for _ in guards:self.base.pop_condition()
            self.base.hmr(wire,outcome)
            for bit in guards:self.base.push_condition(bit)
            self.hoisted.append(dict(owner=str(wire),outcome=str(outcome),guards=list(map(str,guards)),invariant='new branch-local owner, zero for every inactive guard'))
        else:
            self.base.hmr(wire,outcome)
            if self.conditions:self.guarded.append(dict(owner=str(wire),outcome=str(outcome),protected=wire in self.protected,branch_local=wire in self.live))

def inverse_prefixes(d,b,source,target,debt,carry,dirty,lifecycle,sizes,terminal):
    import paired_arithmetic as pa
    from fusion.arithmetic import _phase_borrow
    a,target,preserve=pa._inputs(source,target,carry,False);assert preserve is None
    assert debt.width==13 and not debt.consumed and sorted(debt.measurements)==list(range(1,12))
    debt.consumed=True;b.x(d.array(target));boundaries=[];start=0;incoming=carry
    for number,length in enumerate(sizes):
        aa=a[start:start+length];bb=target[start:start+length]
        if number==len(sizes)-1:terminal(aa,bb,incoming,start,boundaries)
        else:
            outgoing=pa._segment_repay(b,aa,bb,incoming,retain_outgoing=True,preserve=None,start=start,debt=debt)
            recorded=incoming
            if number==0:lifecycle[0](carry);recorded=None
            boundaries.append((aa,bb,recorded,outgoing));incoming=outgoing
        start+=length
    for aa,bb,incoming,outgoing in reversed(boundaries):
        outcome=b.alloc_bits(1)[0];b.hmr(outgoing,outcome);b.free(outgoing)
        b.push_condition(outcome);recreated=incoming is None
        if recreated:incoming=lifecycle[1]()
        _phase_borrow(b,aa,bb,incoming)
        if recreated:lifecycle[0](incoming)
        b.pop_condition();b.free(outcome)
    b.x(d.array(target));assert not debt.measurements

def cleanup_missing_two(d,b,v,P,u):
    assert len(u)==14 and u[11]is None and u[12]is None and b.num_allocated_qubits==40
    P=list(P);P[13],P[14]=list(b.alloc_qubits(2))
    variables=[v[0],v[1],P[12],u[0],u[1]]
    d.cb.emit_xor(b,variables,P[13],d.P13);d.cb.emit_xor(b,variables,P[14],d.P14)
    outcome=b.alloc_bits(1)[0];b.hmr(u[13],outcome);b.free(u[13])
    b.push_condition(outcome);b.z(v[11])
    h11=b.alloc_qubits(1)[0];p11=initial_plan(d,11);d.cb.emit_xor(b,list(v)+[u[10]],h11,p11)
    h12=b.alloc_qubits(1)[0];p12=initial_plan(d,12);d.cb.emit_xor(b,list(v)+[h11],h12,p12)
    b.cz(v[10],h12)
    d._erase(b,h12,list(v)+[h11],p12);d._erase(b,h11,list(v)+[u[10]],p11)
    b.pop_condition();b.free(outcome)
    for i in reversed(range(4,11)):d._erase(b,u[i],list(v)+[u[i-1]],initial_plan(d,i))
    for i in reversed(range(4)):
        item=d.LOCAL['low_cleanup'][i];env={f'v{j}':v[j]for j in range(i+1)}
        env.update(p12=P[12],p13=P[13],p14=P[14]);env.update({f'u{j}':u[j]for j in range(i)})
        d._erase(b,u[i],[env[name]for name in item['inputs']],d.plan_from_json(item['plan']))
    assert b.num_allocated_qubits==30 and P[0]is None
    return P

def apply(ctx):
    from branch_prover import generated_text
    from fourier_resource_expectation import exact_expectation
    from dirty_terminal import terminal_add
    from fusion.compiler import phase_quadratic,MAJORITY_TRUTH
    d=ctx.old.divider;hret=sys.modules['variant_patch_precision_hret'];precision=sys.modules['variant_patch_patch_divider_precision']
    helper_path=Path(os.environ['JOINT_DIRTY_PHASE_HELPER'])
    assert hashlib.sha256(helper_path.read_bytes()).hexdigest()=='1f29eea84f5bf07c588ea199968a3be64f5fc2f829ff6005d004f68102a123ed'
    spec=importlib.util.spec_from_file_location('root_owned_joint_dirty_phase_helper',helper_path);phase=importlib.util.module_from_spec(spec);spec.loader.exec_module(phase)
    coupled_path=Path(os.environ['ROW14_COUPLED_PHASE_HELPER'])
    assert hashlib.sha256(coupled_path.read_bytes()).hexdigest()==os.environ['ROW14_COUPLED_PHASE_SHA256']
    spec=importlib.util.spec_from_file_location('cleanup_owned_row14_coupled_phase',coupled_path);coupled=importlib.util.module_from_spec(spec);spec.loader.exec_module(coupled)
    early_path=Path(os.environ['ROW12_EARLY_PHASE_HELPER'])
    assert hashlib.sha256(early_path.read_bytes()).hexdigest()==os.environ['ROW12_EARLY_PHASE_SHA256']
    spec=importlib.util.spec_from_file_location('cleanup_owned_row12_early_phase',early_path);early=importlib.util.module_from_spec(spec);spec.loader.exec_module(early)
    ledger={}
    def snap(b):
        text=generated_text(b.finish_circuit())
        return dict(owners=b.num_allocated_qubits,instructions=len(text.splitlines()),mean=exact_expectation(text)['mean'])
    def delta(before,after):return{k:str(Fraction(after['mean'][k])-Fraction(v))for k,v in before['mean'].items()}
    def row14(b,token,debt):
        before=snap(b);assert before['owners']==40
        v=token.v;u=token.u;low=u[0];target=u[1:];sign=token.history[14];cur=token.P[9]
        carry=d._feed_carry(b,v,low,cur,sign);d._frame(b,sign,target);d._leading_offset(b,target,inverse=True)
        r=b.alloc_bits(1)[0];b.hmr(target[-1],r);b.free(target[-1]);retained=target[:-1]
        def terminal(aa,bb,incoming,start,boundaries):
            assert aa==[False] and len(bb)==1 and start==11 and b.num_allocated_qubits==44
            terminal_add(b,aa,bb,incoming,dirty=d._dirty(token),debt=debt,start=start,overflow_phase=r)
        inverse_prefixes(d,b,v[1:],retained,debt,carry,d._dirty(token),
            (lambda value:d._feed_erase(b,value,v,low,cur,sign),lambda:d._feed_carry(b,v,low,cur,sign)),[4,3,2,1,1,1],terminal)
        d._frame(b,sign,retained)
        b.z(r);b.push_condition(r);b.z(sign);b.pop_condition()
        b.cx(cur,low);b.cx(sign,low);b.cx(v[0],low)
        token.P[10]=low;token.u=retained+[None,sign];del token.history[14]
        initial=list(token.initial_u);initial[10]=None;token.initial_u=tuple(initial);token._joint14_top=r
        after=snap(b);change=delta(before,after)
        assert change==dict(toffoli_like='31/2',T='0',generic_rotations='0'),change
        ledger.update(row14_before=before,row14_after=after,row14_delta=change)
    # Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
    # Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
    # Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
    # supporting the research.
    def row13(b,token,debt):
        import row13_dirty_c10_phase_v2 as dirty_c10
        before=snap(b);assert before['owners']==40
        v=token.v;u=token.u;assert u[12]is None
        low=u[0];retained=u[1:12];sign=token.history[13];cur=token.P[10];r=token._joint14_top
        outcome=b.alloc_bits(1)[0];b.hmr(u[13],outcome);b.free(u[13]);d._frame(b,sign,retained)
        def terminal_active(aa,bb,incoming,start,boundaries):
            assert aa==[v[11]]and len(bb)==1 and start==10 and b.num_allocated_qubits==44
            assert len(boundaries)==5
            last_a,last_b,c9,c10=boundaries.pop()
            assert last_a==[v[10]]and last_b==[retained[9]]and c10==incoming
            assert boundaries[-1][3]==c9
            z,q=aa[0],bb[0]
            old11=debt.measurements.pop(11)
            for bit in(old11,r):
                b.push_condition(bit);phase_quadratic(b,[z,q,c10],MAJORITY_TRUTH);b.pop_condition()
            b.free(old11)
            # Preserve the raw high-bit phase convention and finish the value SUM.
            b.z(sign);b.cx(z,q);b.cx(c10,q)
            r9=last_b[0];r10=q
            b.cx(sign,r9);b.cx(sign,r10)
            # The paid C10 owner is recoded in place; no new owner is allocated.
            dirty_c10.before(b,v,r9,r10,sign,c9,c10)
            dirty_c10.capture(b,v,r10,c10)
            dirty_c10.phase(b,v,r9,r10,sign,c9,c10)
            mh=b.alloc_bits(1)[0];b.hmr(c10,mh);b.free(c10)
            b.push_condition(mh);dirty_c10.feedback(b,v,r9,r10,sign,c9);b.pop_condition();b.free(mh)
            b.cx(sign,r10);b.cx(sign,r9)
            # C9 remains live for the Clifford HMR correction above. The ordinary
            # inverse-prefix loop now retires C9,C8,C6,C3 exactly as before.
        def terminal_inactive(aa,bb,incoming,start,boundaries):
            assert aa==[v[11]]and len(bb)==1 and start==10 and b.num_allocated_qubits==44
            old11=branch_debt.measurements.pop(11)
            for bit in(old11,r):
                b.push_condition(bit);phase_quadratic(b,[aa[0],bb[0],incoming],MAJORITY_TRUTH);b.pop_condition()
            b.free(old11);b.cx(aa[0],bb[0]);b.cx(incoming,bb[0])
        from types import SimpleNamespace
        original_builder=b;original_debt=debt;kept=set(debt.measurements.values());saved_measurements=dict(debt.measurements)
        b=DebtBuilder(original_builder,kept)
        b.push_condition(outcome)
        debt=SimpleNamespace(width=13,consumed=False,measurements=dict(saved_measurements));carry=d._feed_carry(b,v,low,cur,sign)
        inverse_prefixes(d,b,v[1:],retained,debt,carry,d._dirty(token),
            (lambda value:d._feed_erase(b,value,v,low,cur,sign),lambda:d._feed_carry(b,v,low,cur,sign)),[3,3,2,1,1,1],terminal_active)
        b.pop_condition();b.live.clear();b.x(outcome);b.push_condition(outcome)
        branch_debt=SimpleNamespace(width=13,consumed=False,measurements=dict(saved_measurements));carry=d._feed_carry(b,v,low,cur,sign)
        inverse_prefixes(d,b,v[1:],retained,branch_debt,carry,d._dirty(token),
            (lambda value:d._feed_erase(b,value,v,low,cur,sign),lambda:d._feed_carry(b,v,low,cur,sign)),[3,3,2,1,1,1],terminal_inactive)
        b.pop_condition();b.x(outcome)
        for bit in kept:original_builder.free(bit)
        assert not b.guarded,b.guarded
        ledger['row13_hmr_hoisting']=dict(hoisted=b.hoisted,guarded=b.guarded,proof_status='AWAITING_ORIGINAL_ALL_HMR_PROOF')
        original_debt.measurements.clear();original_debt.consumed=True;debt=original_debt;b=original_builder
        d._frame(b,sign,retained);b.z(r);b.z(outcome)
        b.cx(cur,low);b.cx(sign,low);b.cx(v[0],low)
        token.P[11]=low;token.u=retained+[None,None,sign];del token.history[13]
        initial=list(token.initial_u);initial[11]=None;token.initial_u=tuple(initial)
        b.cx(outcome,r);token._joint13_low=r;token._joint13_top=outcome;del token._joint14_top
        after=snap(b);change=delta(before,after)
        assert change==dict(toffoli_like='31/2',T='0',generic_rotations='0'),change
        ledger.update(row13_before=before,row13_after=after,row13_delta=change,
            row13_dirty_c10=dict(status='LITERAL_EMITTED_RESOURCE_PASS_NATIVE_PROOF_OWED',arithmetic_base='14',bank_recoding='1/2',F_phase='1',retained_C9=True,bank_HMR_feedback_CCX='0',extra_quantum_owners='0',old11_and_r_K_debts='unchanged pre-SUM majority',raw_sign_and_outcome_constants_preserved=True))
    def row12(b,token,debt):
        before=snap(b);assert before['owners']==40
        v=token.v;u=token.u;assert u[11]is None and u[12]is None
        low=u[0];retained=u[1:11];sign=token.history[12];cur=token.P[11];mA=token._joint13_top
        mB=b.alloc_bits(1)[0];b.hmr(u[13],mB);b.free(u[13])
        mC=token._joint13_low;del token._joint13_low
        d._frame(b,sign,retained)
        recovered10=[]
        def majority(a,q,c,target):
            b.cx(c,a);b.cx(c,q);b.ccx(a,q,target);b.cx(c,target);b.cx(c,q);b.cx(c,a)
        def terminal(aa,bb,incoming,start,boundaries):
            assert len(aa)==len(bb)==1 and start==9 and aa[0]is v[10]
            assert b.num_allocated_qubits==43 and len(boundaries)==4
            a,q,c=aa[0],bb[0],incoming
            old10=debt.measurements.pop(10)
            for outcome in(old10,mC):
                b.push_condition(outcome);phase_quadratic(b,[a,q,c],MAJORITY_TRUTH);b.pop_condition()
            b.free(old10)
            parity=debt.measurements.pop(11);b.cx(mA,parity)
            bank=b.alloc_qubits(1)[0];early.capture(b,v,q,c,sign,bank,parity)
            # The complete Hq phase includes q*C11, with only the constant1
            # omitted to cancel the raw measured-high-bit mB constant.
            raw8=retained[8];b.cx(sign,raw8)
            early.emit_early(b,v,raw8,q,c,sign,bank,parity)
            b.cx(sign,raw8)
            # The q0 bank is C10, the q1 bank is a different quadratic.
            # Both have exact Clifford HMR correction at this early cut.
            measurement=b.alloc_bits(1)[0];b.hmr(bank,measurement);b.free(bank)
            b.push_condition(measurement);early.phase_bank(b,v,q,c,sign,parity);b.pop_condition();b.free(measurement)
            b.cx(a,q);b.cx(c,q);b.cx(sign,q)
            i10=b.alloc_qubits(1)[0];d.cb.emit_xor(b,list(v)+[q],i10,initial_plan(d,10));recovered10.append(i10)
            for outcome in(mA,mB):d.cb.emit_phase(b,list(v)+[i10],outcome,initial_plan(d,11))
            b.push_condition(mC);b.z(i10);b.z(v[11]);b.pop_condition();b.z(mA)
            b.push_condition(mB);b.z(sign);b.pop_condition()
            b.cx(sign,raw8);early.emit_late(b,v,raw8,q,i10,c,sign,parity);b.cx(sign,raw8)
            b.free(parity);b.cx(sign,q)
        def terminal_no_bank(aa,bb,incoming,start,boundaries):
            assert len(aa)==len(bb)==1 and start==9 and b.num_allocated_qubits==44
            a,q,c=aa[0],bb[0],incoming
            old10=branch_debt.measurements.pop(10)
            for outcome in(old10,mC):
                b.push_condition(outcome);phase_quadratic(b,[a,q,c],MAJORITY_TRUTH);b.pop_condition()
            b.free(old10)
            parity=branch_debt.measurements.pop(11);b.cx(mA,parity)
            b.cx(a,q);b.cx(c,q);b.cx(sign,q)
            i10=shared_i10;d.cb.emit_xor(b,list(v)+[q],i10,initial_plan(d,10));recovered10.append(i10)
            b.cx(sign,q);b.push_condition(parity)
            phase.phase_carry11_from_final_sum(b,a,q,c,v[11],i10,sign)
            b.pop_condition();b.cx(sign,q)
            d.cb.emit_phase(b,list(v)+[i10],mA,initial_plan(d,11))
            b.push_condition(mC);b.z(i10);b.z(v[11]);b.pop_condition();b.z(mA)
            b.free(parity);b.cx(sign,q)
        # A shared old-debt bit is freed only after both complementary bodies.
        from types import SimpleNamespace
        original_builder=b;original_debt=debt;kept=set(debt.measurements.values());saved_measurements=dict(debt.measurements)
        b=DebtBuilder(original_builder,kept)
        b.push_condition(mB)
        debt=SimpleNamespace(width=13,consumed=False,measurements=dict(saved_measurements))
        carry=d._feed_carry(b,v,low,cur,sign)
        inverse_prefixes(d,b,v[1:],retained,debt,carry,d._dirty(token),
            (lambda value:d._feed_erase(b,value,v,low,cur,sign),lambda:d._feed_carry(b,v,low,cur,sign)),[3,3,2,1,1],terminal)
        b.pop_condition();shared_i10=recovered10.pop()
        b.live.clear();b.protected={shared_i10}
        b.x(mB);b.push_condition(mB)
        branch_debt=SimpleNamespace(width=13,consumed=False,measurements=dict(saved_measurements))
        carry=d._feed_carry(b,v,low,cur,sign)
        inverse_prefixes(d,b,v[1:],retained,branch_debt,carry,d._dirty(token),
            (lambda value:d._feed_erase(b,value,v,low,cur,sign),lambda:d._feed_carry(b,v,low,cur,sign)),[3,3,2,1,1],terminal_no_bank)
        other_i10=recovered10.pop()
        if other_i10!=shared_i10:
            pool=list(b.alloc_qubits(b.num_free_qubits));assert shared_i10 in pool
            b.swap(other_i10,shared_i10)
            b.free(other_i10)
            for q in pool:
                if q!=shared_i10:b.free(q)
        recovered10.append(shared_i10)
        b.pop_condition();b.x(mB)
        for bit in kept:original_builder.free(bit)
        assert not b.guarded,b.guarded
        ledger['row12_hmr_hoisting']=dict(hoisted=b.hoisted,guarded=b.guarded,protected_output=str(shared_i10),proof_status='AWAITING_ORIGINAL_ALL_HMR_PROOF')
        original_debt.measurements.clear();original_debt.consumed=True;debt=original_debt;b=original_builder
        d._frame(b,sign,retained);b.free(mA);b.free(mB);b.free(mC);del token._joint13_top
        b.cx(cur,low);b.cx(sign,low);b.cx(v[0],low)
        assert len(recovered10)==1
        token.P[12]=low;token.u=retained+recovered10+[None,None,sign];del token.history[12]
        initial=list(token.initial_u);initial[10]=recovered10[0];initial[12]=None;token.initial_u=tuple(initial)
        after=snap(b);change=delta(before,after)
        assert change==dict(toffoli_like='61/4',T='0',generic_rotations='0'),change
        ledger.update(row12_before=before,row12_after=after,row12_delta=change)
    def cleanup(b,token):
        assert token.half_zero_feed and b.max_qubits==44 and b.num_allocated_qubits==43
        assert not token.consumed and len(token.rows)==24
        token.consumed=True;v=token.v;old=token.history.pop(12);following=token.history[13]
        outcome=b.alloc_bits(1)[0];b.hmr(old,outcome);b.free(old)
        b.push_condition(outcome);b.z(v[11]);b.z(v[10]);b.cz(v[10],following);b.pop_condition();b.free(outcome)
        outcomes={}
        for j in hret.RETIRE:
            q=token.history.pop(j);m=b.alloc_bits(1)[0];b.hmr(q,m);b.free(q);outcomes[j]=m
        retired24=token.history.pop(24);outcome24=b.alloc_bits(1)[0];b.hmr(retired24,outcome24);b.free(retired24)
        data=41-len(hret.RETIRE);assert b.num_allocated_qubits==data
        for j,k,debt in reversed(token.rows):
            if j in outcomes:
                if j in hret._SAT:hret.restore_sat(d,b,token,j,outcomes.pop(j))
                else:hret.restore(d,b,token,j,outcomes.pop(j))
                data+=1;assert b.num_allocated_qubits==data
            if j==12:
                assert not token.history and not outcomes and data==39
                rebuilt=b.alloc_qubits(1)[0];b.cx(v[11],rebuilt);b.cx(v[10],rebuilt);b.ccx(v[10],token.u[-1],rebuilt)
                token.history[12]=rebuilt;initial=list(token.initial_u);assert initial[13]==old;initial[13]=rebuilt;token.initial_u=tuple(initial)
                row12(b,token,debt)
                assert debt.consumed and not debt.measurements and tuple(token.u)==token.initial_u and not token.history
                before=snap(b);token.P=cleanup_missing_two(d,b,v,token.P,token.u);after=snap(b);change=delta(before,after)
                assert change==dict(toffoli_like='2',T='0',generic_rotations='0'),change
                assert token.P[0]is None and b.num_allocated_qubits==30
                assert all(row.consumed and not row.measurements for _,_,row in token.rows)
                ledger.update(notice=NOTICE,status='COMPLETE_ROW13_DIRTY_C10_BANK_NATIVE_RESOURCE_GATE_AWAITING_PROOF',source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    phase_helper_path=str(helper_path),phase_helper_sha256=hashlib.sha256(helper_path.read_bytes()).hexdigest(),coupled_phase_helper_path=str(coupled_path),coupled_phase_helper_sha256=hashlib.sha256(coupled_path.read_bytes()).hexdigest(),cleanup_before=before,cleanup_after=after,cleanup_delta=change,
                    early_phase_helper_path=str(early_path),early_phase_helper_sha256=hashlib.sha256(early_path.read_bytes()).hexdigest(),H12_rebuild_Toffolis='1',old_joint_scope_vs_qualified_Toffolis='50',new_joint_scope_Toffolis='197/4',saving_vs_qualified_Toffolis='3/4',saving_vs_delivered1439_Toffolis='3/2',all_original_debts_consumed=True)
                Path(os.environ['ROW13_ROW12_JOINT_LEDGER']).write_text(json.dumps(ledger,indent=2)+'\n')
                return list(token.P)
            if j==24:
                sign=token.u[0];target=token.u[1:];b.cx(v[0],sign)
                b.push_condition(outcome24);b.z(sign);b.pop_condition();b.free(outcome24)
                initial=list(token.initial_u);assert initial[1]==retired24;initial[1]=sign;token.initial_u=tuple(initial)
                assert 24 not in token.history and token.P[0]is None
                d._frame(b,sign,target);d._leading_offset(b,target,inverse=True)
                d.inverse_add(b,v[1:],target,debt,carry_in=v[0],dirty_wires=d._dirty(token))
                d._frame(b,sign,target);token.u=target+[sign]
            elif j==14:row14(b,token,debt);data-=1
            elif j==13:row13(b,token,debt);data-=1
            elif j<24:token._debt=debt;hret._feed_row(d,b,token,j)
            else:
                u=token.u;b.cx(v[0],u[0]);sign=u[0];target=u[k+1:]
                d._frame(b,sign,target);d._leading_offset(b,target,inverse=True);carry=v[k]
                if j in precision.UP_ROWS:carry=b.alloc_qubits(1)[0];b.x(carry)
                d.inverse_add(b,v[k+1:],target,debt,carry_in=carry,dirty_wires=d._dirty(token))
                if j in precision.UP_ROWS:b.x(carry);b.free(carry)
                d._frame(b,sign,target);token.u=u[1:]+u[:1]
            assert debt.consumed and not debt.measurements and b.num_allocated_qubits==data,(j,data,b.num_allocated_qubits)
        raise AssertionError('Last feed not reached')
    d.cleanup_divider=cleanup
