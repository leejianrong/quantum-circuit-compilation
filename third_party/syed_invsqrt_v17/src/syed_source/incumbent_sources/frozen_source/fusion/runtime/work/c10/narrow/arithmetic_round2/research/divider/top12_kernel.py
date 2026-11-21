# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Paper candidate: exact final-feed top measurement and source-aware cleanup.

This module writes no circuit or artifact and installs no global hooks.
The parent must separately approve a complete paper gate before native use.
"""
import paired_arithmetic as pa
from fusion.arithmetic import _compute_carry,_erase_carry,_phase_borrow
from fusion.compiler import phase_quadratic,MAJORITY_TRUTH


def initial_bit_plan(d,i):
    def aa(j):return (1,1<<j)if 0<=j<12 else(0,0)
    def bb(j):return (1,0)if j in(0,13)else(1,1<<(j-1))
    return d._compose(d.HIGH,[aa(i),bb(i),aa(i-2),aa(i-3),aa(i-1),(0,1<<12)],13)


def _phase_terminal(b,a,target,incoming,*,start,debt,top_outcome):
    """Write the low sum and phase its exact final carry, with no data top."""
    frames=[];carry=incoming
    for i,(aa,bb)in enumerate(zip(a[:-1],target[:-1])):
        frame=_compute_carry(b,aa,bb,carry)
        outcome=debt.measurements.pop(start+i+1,None)
        if outcome is not None:
            if frame.outgoing is not False:
                b.push_condition(outcome);b.z(frame.outgoing);b.pop_condition()
            b.free(outcome)
        frames.append(frame);carry=frame.outgoing
    # The measured original top is y12=b12 XOR c12. This repays c12.
    b.push_condition(top_outcome)
    phase_quadratic(b,[a[-1],target[-1],carry],MAJORITY_TRUTH)
    b.pop_condition()
    assert start+len(target)not in debt.measurements
    b.cx(a[-1],target[-1]);b.cx(carry,target[-1])
    for frame in reversed(frames):_erase_carry(b,frame,write_sum=True)


def inverse_lower12(d,b,source,target,debt,carry,top_outcome,lifecycle):
    """Exact14E Pauli-terminal inverse; all original11 debt positions paid."""
    a,target,preserve=pa._inputs(source,target,carry,False)
    assert len(target)==12 and len(source)==11 and preserve is None
    assert debt.width==13 and not debt.consumed
    assert sorted(debt.measurements)==list(range(1,12))
    assert b.max_qubits==48 and b.num_allocated_qubits==43
    debt.consumed=True;b.x(d.array(target))
    boundaries=[];start=0;incoming=carry
    for number,length in enumerate((3,4,5)):
        aa=a[start:start+length];bb=target[start:start+length]
        if number==2:
            _phase_terminal(b,aa,bb,incoming,start=start,debt=debt,top_outcome=top_outcome)
        else:
            outgoing=pa._segment_repay(b,aa,bb,incoming,retain_outgoing=True,
                preserve=None,start=start,debt=debt)
            recorded=incoming
            if number==0:
                lifecycle[0](carry);recorded=None
            boundaries.append((aa,bb,recorded,outgoing));incoming=outgoing
        start+=length
    for aa,bb,incoming,outgoing in reversed(boundaries):
        outcome=b.alloc_bits(1)[0];b.hmr(outgoing,outcome);b.free(outgoing)
        b.push_condition(outcome)
        rebuilt=incoming is None
        if rebuilt:incoming=lifecycle[1]()
        _phase_borrow(b,aa,bb,incoming)
        if rebuilt:lifecycle[0](incoming)
        b.pop_condition();b.free(outcome)
    b.x(d.array(target))
    assert not debt.measurements and b.num_allocated_qubits==42


def cleanup_initial_missing12(d,b,v,P,u,*,omit_sigma_phase=False):
    """1.5E, with one measured absent top; return fresh P13/P14 owners."""
    assert len(u)==14 and u[12]is None and b.num_allocated_qubits==42
    P=list(P);P[13],P[14]=list(b.alloc_qubits(2))
    variables=[v[0],v[1],P[12],u[0],u[1]]
    d.cb.emit_xor(b,variables,P[13],d.P13)
    d.cb.emit_xor(b,variables,P[14],d.P14)
    # u12[13] = v11 XOR v10*u12[12]. The missing bit's exact quadratic
    # reconstruction is needed only in this fresh outcome-one branch.
    outcome=b.alloc_bits(1)[0];b.hmr(u[13],outcome);b.free(u[13])
    b.push_condition(outcome)
    b.z(v[11])
    helper=b.alloc_qubits(1)[0];plan=initial_bit_plan(d,12)
    d.cb.emit_xor(b,list(v)+[u[11]],helper,plan)
    if not omit_sigma_phase:b.cz(v[10],helper)
    d._erase(b,helper,list(v)+[u[11]],plan)
    b.pop_condition();b.free(outcome)
    for i in reversed(range(4,12)):
        d._erase(b,u[i],list(v)+[u[i-1]],initial_bit_plan(d,i))
    for i in reversed(range(4)):
        item=d.LOCAL['low_cleanup'][i]
        env={f'v{j}':v[j]for j in range(i+1)}
        env.update(p12=P[12],p13=P[13],p14=P[14])
        env.update({f'u{j}':u[j]for j in range(i)})
        d._erase(b,u[i],[env[name]for name in item['inputs']],d.plan_from_json(item['plan']))
    assert b.num_allocated_qubits==31
    return P


def last_feed_and_initial(d,b,token,debt,*,omit_top_phase=False,omit_sigma_phase=False):
    """Replace only inverse j12 plus cleanup_u12; forward remains unchanged."""
    assert b.max_qubits==48 and b.num_allocated_qubits==43
    assert sorted(token.history)==[12]
    v=token.v;u=token.u;low=u[0];target=u[1:];sign=token.history[12];cur=token.P[11]
    assert len(target)==13 and cur is not None
    carry=d._feed_carry(b,v,low,cur,sign)
    d._frame(b,sign,target);d._leading_offset(b,target,inverse=True)
    top_outcome=b.alloc_bits(1)[0];b.hmr(target[-1],top_outcome);b.free(target[-1])
    retained=target[:-1]
    inverse_lower12(d,b,v[1:],retained,debt,carry,top_outcome,
        (lambda value:d._feed_erase(b,value,v,low,cur,sign),
         lambda:d._feed_carry(b,v,low,cur,sign)))
    d._frame(b,sign,retained)
    if not omit_top_phase:
        # The saved result-top phase still owes its original framed data top.
        d.cb.emit_phase(b,list(v)+[retained[11]],top_outcome,initial_bit_plan(d,12))
        b.z(top_outcome)
        b.push_condition(top_outcome);b.z(sign);b.pop_condition()
    b.free(top_outcome)
    b.cx(cur,low);b.cx(sign,low);b.cx(v[0],low)
    token.P[12]=low;token.u=retained+[None,sign];del token.history[12]
    assert tuple(token.u[:12])==token.initial_u[:12]
    assert sign==token.initial_u[13]
    token.P=cleanup_initial_missing12(d,b,v,token.P,token.u,omit_sigma_phase=omit_sigma_phase)
    token.u=[]
    return list(token.P)


def cleanup_divider(d,b,token):
    """The complete inverse, with23 unchanged rows and one source-aware row."""
    assert b.max_qubits==48 and b.num_allocated_qubits==43
    assert not token.consumed and len(token.rows)==24
    token.consumed=True;v=token.v
    for j,k,debt in reversed(token.rows):
        if j==12:
            result=last_feed_and_initial(d,b,token,debt)
            assert all(x.consumed and not x.measurements for _,_,x in token.rows)
            return result
        u=token.u
        if j<=24:
            low=u[0];target=u[1:];sign=token.history[j];cur=token.P[23-j]if j<24 else None
            carry=d._feed_carry(b,v,low,cur,sign)
            d._frame(b,sign,target);d._leading_offset(b,target,inverse=True)
            released=d.inverse_add(b,v[1:],target,debt,carry_in=carry,dirty_wires=d._dirty(token),
                carry_lifecycle=(lambda value:d._feed_erase(b,value,v,low,cur,sign),
                                 lambda:d._feed_carry(b,v,low,cur,sign)))
            d._frame(b,sign,target)
            assert released
            if cur is not None:b.cx(cur,low)
            b.cx(sign,low);b.cx(v[0],low)
            token.P[24-j]=low;token.u=target+[sign];del token.history[j]
        else:
            b.cx(v[0],u[0]);sign=u[0];target=u[k+1:]
            d._frame(b,sign,target);d._leading_offset(b,target,inverse=True)
            d.inverse_add(b,v[k+1:],target,debt,carry_in=v[k],dirty_wires=d._dirty(token))
            d._frame(b,sign,target);token.u=u[1:]+u[:1]
        assert debt.consumed and not debt.measurements and b.num_allocated_qubits==43
    raise AssertionError('The final row was not reached')
