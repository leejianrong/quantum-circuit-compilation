# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Q44 last-feed top retirement with a one-zero-source dirty terminal.

The last inverse add returns twelve lower bits. Its omitted high bit is
measured; a sparse terminal phases the exact final borrow by CZ before its
one-bit zero-source increment. All eleven original carry debts are consumed.
"""
from fractions import Fraction
from pathlib import Path
import hashlib,json,os,sys
NOTICE='Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.'

def initial_plan(d,i):
    def aa(j):return(1,1<<j)if 0<=j<12 else(0,0)
    def bb(j):return(1,0)if j in(0,13)else(1,1<<(j-1))
    return d._compose(d.HIGH,[aa(i),bb(i),aa(i-2),aa(i-3),aa(i-1),(0,1<<12)],13)

def inverse_low12(d,b,source,target,debt,carry,top_outcome,dirty,lifecycle):
    import paired_arithmetic as pa
    from dirty_terminal import terminal_add
    from fusion.arithmetic import _phase_borrow
    a,target,preserve=pa._inputs(source,target,carry,False)
    assert len(target)==12 and len(source)==11 and preserve is None
    assert debt.width==13 and not debt.consumed
    assert sorted(debt.measurements)==list(range(1,12))
    clean=b.max_qubits-b.num_allocated_qubits
    sizes,pool=pa._terminal_partition(a,target,carry,clean,dirty,
        release_input=True,ordinary_final=False,allow_dirty_terminal=True,overflow_phase=True)
    assert sizes==[2,2,1,7],(clean,sizes)
    debt.consumed=True;b.x(d.array(target))
    boundaries=[];start=0;incoming=carry
    for number,length in enumerate(sizes):
        aa=a[start:start+length];bb=target[start:start+length]
        if number==len(sizes)-1:
            terminal_add(b,aa,bb,incoming,dirty=pool,debt=debt,start=start,overflow_phase=top_outcome)
        else:
            outgoing=pa._segment_repay(b,aa,bb,incoming,retain_outgoing=True,preserve=None,start=start,debt=debt)
            recorded=incoming
            if number==0:lifecycle[0](carry);recorded=None
            boundaries.append((aa,bb,recorded,outgoing));incoming=outgoing
        start+=length
    for aa,bb,incoming,outgoing in reversed(boundaries):
        outcome=b.alloc_bits(1)[0];b.hmr(outgoing,outcome);b.free(outgoing)
        b.push_condition(outcome)
        recreated=incoming is None
        if recreated:incoming=lifecycle[1]()
        _phase_borrow(b,aa,bb,incoming)
        if recreated:lifecycle[0](incoming)
        b.pop_condition();b.free(outcome)
    b.x(d.array(target));assert not debt.measurements
    return sizes

def cleanup_missing12(d,b,v,P,u):
    assert len(u)==14 and u[12]is None and b.num_allocated_qubits==41
    P=list(P);P[13],P[14]=list(b.alloc_qubits(2))
    variables=[v[0],v[1],P[12],u[0],u[1]]
    d.cb.emit_xor(b,variables,P[13],d.P13);d.cb.emit_xor(b,variables,P[14],d.P14)
    outcome=b.alloc_bits(1)[0];b.hmr(u[13],outcome);b.free(u[13])
    b.push_condition(outcome);b.z(v[11])
    helper=b.alloc_qubits(1)[0];plan=initial_plan(d,12)
    d.cb.emit_xor(b,list(v)+[u[11]],helper,plan)
    b.cz(v[10],helper)
    d._erase(b,helper,list(v)+[u[11]],plan)
    b.pop_condition();b.free(outcome)
    for i in reversed(range(4,12)):
        d._erase(b,u[i],list(v)+[u[i-1]],initial_plan(d,i))
    for i in reversed(range(4)):
        item=d.LOCAL['low_cleanup'][i]
        env={f'v{j}':v[j]for j in range(i+1)}
        env.update(p12=P[12],p13=P[13],p14=P[14])
        env.update({f'u{j}':u[j]for j in range(i)})
        d._erase(b,u[i],[env[name]for name in item['inputs']],d.plan_from_json(item['plan']))
    assert b.num_allocated_qubits==30 and P[0]is None
    return P

def apply(ctx):
    from branch_prover import generated_text
    from fourier_resource_expectation import exact_expectation
    d=ctx.old.divider;hret=sys.modules['variant_patch_precision_hret']
    oldfeed=hret._feed_row;oldcleanup=d.cleanup_u12;record={}
    def snap(b):
        text=generated_text(b.finish_circuit())
        return dict(owners=b.num_allocated_qubits,instructions=len(text.splitlines()),mean=exact_expectation(text)['mean'])
    def delta(before,after):return{k:str(Fraction(after['mean'][k])-Fraction(v))for k,v in before['mean'].items()}
    def feed(d,b,token,j):
        if j!=12:return oldfeed(d,b,token,j)
        before=snap(b);assert before['owners']==42
        v=token.v;u=token.u;low=u[0];target=u[1:];sign=token.history[12];cur=token.P[11];debt=token._debt
        carry=d._feed_carry(b,v,low,cur,sign)
        d._frame(b,sign,target);d._leading_offset(b,target,inverse=True)
        m=b.alloc_bits(1)[0];b.hmr(target[-1],m);b.free(target[-1])
        retained=target[:-1]
        sizes=inverse_low12(d,b,v[1:],retained,debt,carry,m,d._dirty(token),
            (lambda value:d._feed_erase(b,value,v,low,cur,sign),lambda:d._feed_carry(b,v,low,cur,sign)))
        d._frame(b,sign,retained)
        d.cb.emit_phase(b,list(v)+[retained[11]],m,initial_plan(d,12))
        b.z(m);b.push_condition(m);b.z(sign);b.pop_condition();b.free(m)
        b.cx(cur,low);b.cx(sign,low);b.cx(v[0],low)
        token.P[12]=low;token.u=retained+[None,sign];del token.history[12]
        initial=list(token.initial_u);initial[12]=None;token.initial_u=tuple(initial)
        after=snap(b);change=delta(before,after)
        assert change==dict(toffoli_like='39/2',T='0',generic_rotations='0'),change
        record.update(row_before=before,row_after=after,row_delta=change,partition=sizes,
                      original_carry_debts_consumed=11,top_measurement_phase_paid=True)
    def cleanup(b,v,P,u):
        if u[12]is not None:return oldcleanup(b,v,P,u)
        before=snap(b);result=cleanup_missing12(d,b,v,P,u);after=snap(b)
        change=delta(before,after)
        assert change==dict(toffoli_like='3/2',T='0',generic_rotations='0'),change
        record.update(notice=NOTICE,status='COMPLETE_NATIVE_RESOURCE_GATE_AWAITING_ALL_DOMAIN_PROOF',
            source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),cleanup_before=before,cleanup_after=after,cleanup_delta=change,
            unchanged_H12_reconstruction_Toffolis='1',complete_old_suffix_Toffolis='49/2',complete_new_suffix_Toffolis='22',
            raw_expected_saving_Toffolis='5/2',original_forward_and_endpoint_unchanged=True,phase_precision_and_rotations_unchanged=True)
        Path(os.environ['ROW12_DIRTY_TOP_LEDGER']).write_text(json.dumps(record,indent=2)+'\n')
        return result
    hret._feed_row=feed;d.cleanup_u12=cleanup
