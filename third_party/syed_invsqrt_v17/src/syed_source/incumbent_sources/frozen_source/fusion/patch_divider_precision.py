# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Release owned feed carries after the first sum, reducing forward peak by one."""

EXTRA=0
EXTRA_START=25
K_OVERRIDES={}
UP_ROWS=set()

def row_k(j):
    k=min(11,max(0,j-26)+EXTRA) if EXTRA and j>=EXTRA_START else (j-26 if j>=28 else 0)
    return K_OVERRIDES.get(j,k)

def apply(ctx):
    d=ctx.old.divider
    kernel=d.forward_add.__globals__

    def disposable(b,source,target,carry,erase):
        a,word,preserve=kernel['_inputs'](source,target,carry,False)
        width=len(word);debts={};released=False
        assert width>2 and preserve is None
        incoming=carry
        for index,(aa,bb) in enumerate(zip(a[:-2],word[:-2])):
            frame=kernel['_compute_carry'](b,aa,bb,incoming,preserve=None)
            kernel['_sum_keep_carry'](b,frame)
            if index==0:
                assert frame.incoming==carry and frame.outgoing is not False
                erase(carry);released=True
            else:
                outcome=b.alloc_bits(1)[0];b.hmr(incoming,outcome);b.free(incoming);debts[index]=outcome
            incoming=frame.outgoing
        kernel['_finish_top'](b,a,word,incoming,None)
        outcome=b.alloc_bits(1)[0];b.hmr(incoming,outcome);b.free(incoming);debts[width-2]=outcome
        return kernel['CarryDebt'](debts,width),released

    def compute(b,v12,P15,flags4):
        v=list(v12);P=list(P15);flags=list(flags4)
        assert len(set(v+P+flags))==31 and b.num_allocated_qubits==31
        u=list(b.alloc_qubits(14));initial_u=tuple(u)
        P=d.initialize_u12(b,v,P,u)
        token=d.DividerToken(v,P,flags,u,initial_u);token._precision_up_rows=set(UP_ROWS)
        assert b.num_allocated_qubits==43
        for j in range(12,36):
            u=token.u
            if j<=24:
                prev=token.P[24-j];cur=token.P[23-j] if j<24 else None
                sign=u[-1];target=u[:-1]
                carry=d._feed_carry(b,v,prev,cur,sign)
                d._frame(b,sign,target)
                debt,released=disposable(b,v[1:],target,carry,
                    lambda q:d._feed_erase(b,q,v,prev,cur,sign))
                assert released
                d._leading_offset(b,target);d._frame(b,sign,target)
                b.cx(v[0],prev);b.cx(sign,prev)
                if cur is not None:b.cx(cur,prev)
                token.u=[prev]+target;token.history[j]=sign;token.P[24-j]=None;k=0
            else:
                k=row_k(j)
                u=[u[-1]]+u[:-1];sign=u[0];target=u[k+1:]
                d._frame(b,sign,target)
                carry=v[k]
                if j in UP_ROWS:carry=b.alloc_qubits(1)[0];b.x(carry)
                debt=d.forward_add(b,v[k+1:],target,carry_in=carry)
                if j in UP_ROWS:b.x(carry);b.free(carry)
                d._leading_offset(b,target);d._frame(b,sign,target)
                b.cx(v[0],u[0]);token.u=u
            token.rows.append((j,k,debt))
            assert b.num_allocated_qubits==43
        assert sorted(token.history)==list(range(12,25)) and all(q is None for q in token.P)
        return token
    d.compute_divider=compute
    if EXTRA or K_OVERRIDES:
        # Reconstruct the exact two oldest late history signs. Only row27
        # can put a nonlinear carry into s25; all later affected positions
        # are the low sum bit and therefore contribute affine masks.
        def sigma25(b,v,u,inverse=False):
            ops=[];mask={0};constant=False
            def term(i):
                nonlocal constant
                if i is None:constant=not constant
                elif i in mask:mask.remove(i)
                else:mask.add(i)
            def carry(j,k):return None if j in UP_ROWS else k
            if row_k(26)==0:term(1);term(carry(26,0))
            k27=row_k(27)
            mask26={0}
            if k27==0:
                term(2)
                if 27 in UP_ROWS:
                    # carry = (v1 XOR 1)*(u9 XOR u8 XOR v0) XOR v1.
                    ops.extend([('x',v[1]),('cx',u[8],u[9]),('cx',v[0],u[9]),('ccx',v[1],u[9],u[10]),('cx',v[0],u[9]),('cx',u[8],u[9]),('x',v[1])]);term(1)
                    mask26^={1};mask26.add(None)
                else:
                    # carry = (v0 XOR v1)*(u9 XOR u8) XOR v0.
                    ops.extend([('cx',v[1],v[0]),('cx',u[8],u[9]),('ccx',v[0],u[9],u[10]),('cx',u[8],u[9]),('cx',v[1],v[0])]);term(0)
                    mask26^={1,0}
            elif k27==1:term(2);term(carry(27,1))
            for j in range(28,36):
                k=row_k(j);assert k>=j-26, (j,k)
                if k==j-26:term(k+1);term(carry(j,k))
            for i in sorted(mask):ops.append(('cx',v[i],u[10]))
            if constant:ops.append(('x',u[10]))
            mask26^={1}
            for i in sorted(x for x in mask26 if x is not None):ops.append(('cx',v[i],u[9]))
            if None in mask26:ops.append(('x',u[9]))
            # Affine-only cases commute; preserve the banked source ordering.
            for op in reversed(ops) if inverse and k27==0 else ops:getattr(b,op[0])(*op[1:])
        d._sigma25_frame=sigma25
