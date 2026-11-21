# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Paper-only post-endpoint retirement; no forward or phase changes."""
import top12_kernel as base


def cleanup_divider(d,b,token,*,trace=None):
    assert b.max_qubits==48 and b.num_allocated_qubits==43
    assert not token.consumed and len(token.rows)==24
    assert sorted(token.history)==list(range(12,25))
    token.consumed=True;v=token.v
    old_sign=token.history.pop(12);next_sign=token.history[13]
    outcome=b.alloc_bits(1)[0];b.hmr(old_sign,outcome);b.free(old_sign)
    b.push_condition(outcome);b.z(v[11]);b.z(v[10]);b.cz(v[10],next_sign);b.pop_condition()
    b.free(outcome)
    assert b.num_allocated_qubits==42
    if trace:trace('retired_history12',None,None)
    for j,k,debt in reversed(token.rows):
        if j==12:
            assert not token.history and token.u[-1]==next_sign
            rebuilt=b.alloc_qubits(1)[0]
            b.cx(v[11],rebuilt);b.cx(v[10],rebuilt);b.ccx(v[10],token.u[-1],rebuilt)
            token.history[12]=rebuilt
            initial=list(token.initial_u);assert initial[13]==old_sign
            initial[13]=rebuilt;token.initial_u=tuple(initial)
            if trace:trace('rebuilt_history12',j,None)
            result=base.last_feed_and_initial(d,b,token,debt)
            assert all(x.consumed and not x.measurements for _,_,x in token.rows)
            if trace:trace('last_feed_and_initial',j,None)
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
            if not released:d._feed_erase(b,carry,v,low,cur,sign)
            if cur is not None:b.cx(cur,low)
            b.cx(sign,low);b.cx(v[0],low)
            token.P[24-j]=low;token.u=target+[sign];del token.history[j]
        else:
            b.cx(v[0],u[0]);sign=u[0];target=u[k+1:]
            d._frame(b,sign,target);d._leading_offset(b,target,inverse=True)
            d.inverse_add(b,v[k+1:],target,debt,carry_in=v[k],dirty_wires=d._dirty(token))
            d._frame(b,sign,target);token.u=u[1:]+u[:1]
        assert debt.consumed and not debt.measurements and b.num_allocated_qubits==42
        if trace:trace('inverse_row',j,k)
    raise AssertionError('The final feed was not reached')
