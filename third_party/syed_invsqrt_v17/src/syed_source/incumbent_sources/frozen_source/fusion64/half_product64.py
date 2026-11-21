# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Half-scale consuming product with unchanged coefficient, seed and divider.

The incumbent seed LSB is erased by its affine formula and restored before
the incumbent seed inverse. A literal-zero P0 keeps the divider interface
unchanged. All three SEEDINV root retirements and H2 retirement are retained.
Numerical accuracy is a separate mandatory full-domain phase gate.
"""
import sys

ROUNDING_MASK=0
LAST_ZERO=False
ABSENT_ZERO=False


def apply(ctx):
    base=ctx.baseline;ar=base.product_ar;seedinv=sys.modules['variant_patch_patch_seedinv']
    h2ret=sys.modules['variant_patch_patch_h2ret']
    def carry(b,C,q,i):
        if i==9:
            if LAST_ZERO:return False
            b.cx(C[8],q);b.x(q);return q
        value=b.alloc_qubits(1)[0]
        if i==8:
            b.cx(C[8],q);b.ccx(C[0],q,value);b.cx(C[8],q)
        else:
            shift=8-i;upper=C[shift];index=shift-1-int(bool(ROUNDING_MASK>>i&1));lower=C[index] if index>=0 else False
            if lower is False:b.cx(C[8],q);b.ccx(upper,q,value);b.cx(C[8],q)
            else:
                b.cx(upper,lower);b.cx(C[8],q);b.x(q);b.ccx(lower,q,value)
                b.x(q);b.cx(C[8],q);b.cx(upper,lower);b.cx(upper,value)
        return value
    def clear(b,C,q,i,value):
        if i==9:
            if LAST_ZERO:assert value is False;return
            b.x(q);b.cx(C[8],q);return
        if i==8:
            b.cx(C[8],q);b.del_and(C[0],q,value);b.cx(C[8],q)
        else:
            shift=8-i;upper=C[shift];index=shift-1-int(bool(ROUNDING_MASK>>i&1));lower=C[index] if index>=0 else False
            if lower is False:b.cx(C[8],q);b.del_and(upper,q,value);b.cx(C[8],q)
            else:
                b.cx(upper,value);b.cx(upper,lower);b.cx(C[8],q);b.x(q)
                b.del_and(lower,q,value);b.x(q);b.cx(C[8],q);b.cx(upper,lower)
        b.free(value)
    def disposable(b,source,target,incoming,erase):
        aa,bb,preserve=ar._inputs(source,target,incoming,False);assert preserve is None;debts={}
        for pos,(a,q) in enumerate(zip(aa[:-2],bb[:-2])):
            frame=ar._compute_carry(b,a,q,incoming,preserve=None);ar._sum_keep_carry(b,frame)
            if pos==0:erase(incoming)
            else:
                outcome=b.alloc_bits(1)[0];b.hmr(incoming,outcome);b.free(incoming);debts[pos]=outcome
            incoming=frame.outgoing
        ar._finish_top(b,aa,bb,incoming,None)
        outcome=b.alloc_bits(1)[0];b.hmr(incoming,outcome);b.free(incoming);debts[len(bb)-2]=outcome
        return ar.CarryDebt(debts,len(bb))
    def forward(b,D,seed,h):
        assert len(D)==13 and len(seed)==6 and len(h)==10
        m=b.alloc_bits(1)[0];b.hmr(seed[0],m)
        b.push_condition(m);b.z(True);b.z(D[11]);b.z(D[8]);b.pop_condition();b.free(m);b.free(seed[0])
        C=list(D);word=list(seed[1:])+list(h);rows=[];b.x(word[14])
        for i in range(10):
            q=word[5+i];target=word[:5+i];source=C[9-i:] if i<9 else C
            for t in target:b.cx(q,t)
            incoming=carry(b,C,q,i)
            if i<9:debt=disposable(b,source,target,incoming,lambda value,i=i,q=q:clear(b,C,q,i,value))
            else:debt=ar.forward_add(b,source,target,carry_in=incoming);clear(b,C,q,i,incoming)
            rows.append(debt)
            for t in target:b.cx(q,t)
        b.x(word[14]);zero=None if ABSENT_ZERO else b.alloc_qubits(1)[0]
        token=base.ProductToken(rows);token.half_numerator=True
        token.half_rounding_mask=ROUNDING_MASK;token.half_last_zero=LAST_ZERO
        token.half_absent_zero=ABSENT_ZERO
        return [zero]+word,token
    def inverse(b,v,D,word,token,dirty):
        assert token.half_numerator and len(word)==16
        assert token.half_rounding_mask==ROUNDING_MASK and token.half_last_zero==LAST_ZERO
        assert token.half_absent_zero==ABSENT_ZERO and (word[0] is None)==ABSENT_ZERO
        entry=b.num_allocated_qubits;C=list(D);word=list(word);dirty=list(dirty)
        if word[0] is not None:b.free(word[0])
        word=word[1:]
        outcomes={}
        for index in (0,1,3):
            q=v[index];assert q is not None and dirty.count(q)==1
            m=b.alloc_bits(1)[0];b.hmr(q,m);b.free(q);outcomes[index]=m;v[index]=None;dirty.remove(q)
        assert b.num_allocated_qubits==entry-4+int(ABSENT_ZERO)
        b.x(word[14])
        for i in reversed(range(10)):
            q=word[5+i];target=word[:5+i];source=C[9-i:] if i<9 else C
            for t in target:b.cx(q,t)
            incoming=carry(b,C,q,i)
            def erase(value,i=i,q=q):clear(b,C,q,i,value)
            def regenerate(i=i,q=q):return carry(b,C,q,i)
            released=ar.inverse_add(b,source,target,token.rows[i],carry_in=incoming,
                dirty_wires=dirty+word[5:],carry_lifecycle=(erase,regenerate) if i<9 else None)
            if not released:clear(b,C,q,i,incoming)
            for t in target:b.cx(q,t)
            assert token.rows[i].consumed and not token.rows[i].measurements
        b.x(word[14]);low=b.alloc_qubits(1)[0];b.x(low);b.cx(C[11],low);b.cx(C[8],low)
        seedinv.STATE['outcomes']=outcomes
        assert b.num_allocated_qubits==entry-3+int(ABSENT_ZERO)
        return [low]+word[:5],word[5:]
    base.product_forward=forward;ctx.components['lifecycle'].product_inverse=inverse
