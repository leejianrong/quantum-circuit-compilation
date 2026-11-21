# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Version3: restore H24 in the consumed P0 owner and borrow its affine carry.

Delay the known-zero dividend owner until the final feed row.

P0=0 is guaranteed by the half-numerator product. Feed row23 reads its
literal value through the three-input carry plan. Row24 allocates its
owner, preserving the incumbent endpoint chart exactly. The inverse frees
that zero immediately after row24 and recreates it at divider return.
"""
import sys

ABSENT_OUTSIDE=False
EARLY_HISTORY12=False


def apply(ctx):
    d=ctx.old.divider;precision=sys.modules['variant_patch_patch_divider_precision']
    hret=sys.modules['variant_patch_precision_hret'];kernel=d.forward_add.__globals__
    def disposable(b,source,target,carry,erase):
        aa,bb,preserve=kernel['_inputs'](source,target,carry,False);assert preserve is None
        incoming=carry;debts={}
        for pos,(a,q) in enumerate(zip(aa[:-2],bb[:-2])):
            frame=kernel['_compute_carry'](b,a,q,incoming,preserve=None);kernel['_sum_keep_carry'](b,frame)
            if pos==0:erase(incoming)
            else:
                outcome=b.alloc_bits(1)[0];b.hmr(incoming,outcome);b.free(incoming);debts[pos]=outcome
            incoming=frame.outgoing
        kernel['_finish_top'](b,aa,bb,incoming,None)
        outcome=b.alloc_bits(1)[0];b.hmr(incoming,outcome);b.free(incoming);debts[len(bb)-2]=outcome
        return kernel['CarryDebt'](debts,len(bb))
    def compute(b,v12,P15,flags4):
        v=list(v12);P=list(P15);flags=list(flags4)
        assert b.num_allocated_qubits==31-int(ABSENT_OUTSIDE) and (P[0] is None)==ABSENT_OUTSIDE
        u=list(b.alloc_qubits(14));initial=tuple(u);P=d.initialize_u12(b,v,P,u)
        assert b.num_allocated_qubits==43-int(ABSENT_OUTSIDE)
        if P[0] is not None:b.free(P[0]);P[0]=None
        token=d.DividerToken(v,P,flags,u,initial);token._precision_up_rows=set(precision.UP_ROWS)
        token.half_zero_feed=True
        retired_h12=None
        for j in range(12,36):
            u=token.u
            if j<=24:
                if j==24:
                    if EARLY_HISTORY12:
                        retired_h12=token.history.pop(12)
                        outcome=b.alloc_bits(1)[0];b.hmr(retired_h12,outcome);b.free(retired_h12)
                        b.push_condition(outcome);b.z(v[11]);b.z(v[10]);b.cz(v[10],token.history[13]);b.pop_condition();b.free(outcome)
                    assert token.P[0] is None;token.P[0]=b.alloc_qubits(1)[0]
                prev=token.P[24-j];cur=token.P[23-j] if j<24 else None
                sign=u[-1];target=u[:-1];carry=d._feed_carry(b,v,prev,cur,sign)
                d._frame(b,sign,target)
                debt=disposable(b,v[1:],target,carry,lambda value:d._feed_erase(b,value,v,prev,cur,sign))
                d._leading_offset(b,target);d._frame(b,sign,target)
                b.cx(v[0],prev);b.cx(sign,prev)
                if cur is not None:b.cx(cur,prev)
                token.u=[prev]+target;token.history[j]=sign;token.P[24-j]=None;k=0
            else:
                k=precision.row_k(j);u=[u[-1]]+u[:-1];sign=u[0];target=u[k+1:]
                d._frame(b,sign,target);carry=v[k]
                if j in precision.UP_ROWS:carry=b.alloc_qubits(1)[0];b.x(carry)
                debt=d.forward_add(b,v[k+1:],target,carry_in=carry)
                if j in precision.UP_ROWS:b.x(carry);b.free(carry)
                d._leading_offset(b,target);d._frame(b,sign,target);b.cx(v[0],u[0]);token.u=u
            token.rows.append((j,k,debt));assert b.num_allocated_qubits==42+int(j>=24)-int(EARLY_HISTORY12 and j>=24)
        if EARLY_HISTORY12:
            restored=b.alloc_qubits(1)[0];b.cx(v[11],restored);b.cx(v[10],restored);b.ccx(v[10],token.history[13],restored)
            token.history[12]=restored;initial=list(token.initial_u);assert initial[13]==retired_h12
            initial[13]=restored;token.initial_u=tuple(initial)
        assert b.num_allocated_qubits==43
        return token
    def cleanup(b,token):
        assert token.half_zero_feed and b.max_qubits in (44,45,46) and b.num_allocated_qubits==43
        assert not token.consumed and len(token.rows)==24
        token.consumed=True;v=token.v
        old=token.history.pop(12);following=token.history[13]
        outcome=b.alloc_bits(1)[0];b.hmr(old,outcome);b.free(old)
        b.push_condition(outcome);b.z(v[11]);b.z(v[10]);b.cz(v[10],following);b.pop_condition();b.free(outcome)
        outcomes={}
        for j in hret.RETIRE:
            q=token.history.pop(j);m=b.alloc_bits(1)[0];b.hmr(q,m);b.free(q);outcomes[j]=m
        # The final feed consumed the known-zero P0, so at the actual
        # inverse24 restore point H24 equals u0 XORv0. Its phase debt is
        # retained classically while the later inverse rows use the clean wire.
        retired24=token.history.pop(24)
        outcome24=b.alloc_bits(1)[0];b.hmr(retired24,outcome24);b.free(retired24)
        data=41-len(hret.RETIRE);assert b.num_allocated_qubits==data
        for j,k,debt in reversed(token.rows):
            if j in outcomes:
                if j in hret._SAT:hret.restore_sat(d,b,token,j,outcomes.pop(j))
                else:hret.restore(d,b,token,j,outcomes.pop(j))
                data+=1;assert b.num_allocated_qubits==data
            if j==12:
                assert not token.history and not outcomes
                rebuilt=b.alloc_qubits(1)[0];b.cx(v[11],rebuilt);b.cx(v[10],rebuilt);b.ccx(v[10],token.u[-1],rebuilt)
                token.history[12]=rebuilt;initial=list(token.initial_u);assert initial[13]==old
                initial[13]=rebuilt;token.initial_u=tuple(initial);token._debt=debt
                hret._feed_row(d,b,token,12)
                assert debt.consumed and not debt.measurements and tuple(token.u)==token.initial_u and not token.history
                token.P=d.cleanup_u12(b,v,token.P,token.u)
                assert token.P[0] is None and b.num_allocated_qubits==30
                if not ABSENT_OUTSIDE:token.P[0]=b.alloc_qubits(1)[0]
                assert b.num_allocated_qubits==31-int(ABSENT_OUTSIDE)
                assert all(row.consumed and not row.measurements for _,_,row in token.rows)
                return list(token.P)
            if j==24:
                # The known-zero consumed P0 means old low = v0 XOR H24.
                # Reuse that owner for H24; the reconstructed P0 stays absent.
                sign=token.u[0];target=token.u[1:]
                b.cx(v[0],sign)
                b.push_condition(outcome24);b.z(sign);b.pop_condition();b.free(outcome24)
                initial=list(token.initial_u);assert initial[1]==retired24
                initial[1]=sign;token.initial_u=tuple(initial)
                assert 24 not in token.history and token.P[0] is None
                # FEED3(v0, low, H24) = v0 on low = v0 XOR H24.
                d._frame(b,sign,target);d._leading_offset(b,target,inverse=True)
                d.inverse_add(b,v[1:],target,debt,carry_in=v[0],dirty_wires=d._dirty(token))
                d._frame(b,sign,target)
                token.u=target+[sign]
            elif j<24:
                token._debt=debt;hret._feed_row(d,b,token,j)
            else:
                u=token.u;b.cx(v[0],u[0]);sign=u[0];target=u[k+1:]
                d._frame(b,sign,target);d._leading_offset(b,target,inverse=True);carry=v[k]
                if j in precision.UP_ROWS:carry=b.alloc_qubits(1)[0];b.x(carry)
                d.inverse_add(b,v[k+1:],target,debt,carry_in=carry,dirty_wires=d._dirty(token))
                if j in precision.UP_ROWS:b.x(carry);b.free(carry)
                d._frame(b,sign,target);token.u=u[1:]+u[:1]
            assert debt.consumed and not debt.measurements and b.num_allocated_qubits==data
        raise AssertionError('The final feed was not reached')
    d.compute_divider=compute;d.cleanup_divider=cleanup
