# Separate local-continuation mask repayment at existing window gap queries.
# Credits: Opus and Astra.
# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""Fixed preimage window with explicit transpose-output flag ownership.

The preceding masked parked-phase and retained-forward provider changes are
preserved. Each transpose returns its last live third-source zero predicate;
the caller adopts that exact bit and skips only an immediately repeated query.
All accumulated source and local masks are paid on the same restored witness.
"""
import transpose_handoff_core as C
from gauge_park_lender import deferred_scale, repay_scale
from masked_parked_scale_phase import repay_parked_scale
import window_forward_retained_flag as tensor
import window_transpose_handoff as transpose_tensor
from monic_forney import evaluate_low,high_terms,scale,add_scaled,F,flat
from tower_inverse import xor_product,apply_inplace_linear

WINDOWS={17,14}
TRANSPOSE_WINDOWS={17}

class Step:
    def __init__(self,b,A,B,rhss,previous,context,closing):
        self.b=b;self.A=A;self.B=B;self.rhss=rhss;self.previous=previous
        self.context=context;self.closing=closing;self.n=len(B);self.virtual=self.n>4
        self.low=A[:self.n-1];self.heads=[r[-1] for r in rhss]
        self.flag=None;self.flagmask=None;self.debt=None;self.shared_top=False;self.shared_lower=True
        self.quotient=(self.heads,A[self.n-1],A[self.n],False)
    def merge(self,name,mask):
        old=getattr(self,name)
        if old is None:setattr(self,name,mask)
        else:self.b.cx(mask,old);self.b.free(mask)
    def query(self,consume=False,pay=False):
        assert self.flag is None
        b=self.b;self.flag=b.alloc_qubits(1);C.toggle_zero(b,self.B[-1],self.flag[0])
        if consume and self.context is not None and self.closing:
            incoming=self.context.flags.pop(self.n);b.cz(incoming,self.flag);b.free(incoming)
        if pay:C.pay_local_flag(b,self.B[-1],self.flag,self.n,self.context,self.closing)
        if pay and self.flagmask is not None:
            b.cz(self.flagmask,self.flag);b.free(self.flagmask);self.flagmask=None
    def adopt(self,handoff,pay=False):
        assert self.flag is None
        self.flag=handoff.claim(self.b,self.B[-1])
        # Exactly the repayment portion of query(pay=True), with no query
        # or new allocation. It precedes every later source mutation.
        if pay:C.pay_local_flag(self.b,self.B[-1],self.flag,self.n,self.context,self.closing)
        if pay and self.flagmask is not None:
            self.b.cz(self.flagmask,self.flag);self.b.free(self.flagmask);self.flagmask=None
    def release(self):
        mask=self.b.alloc_bits(1);self.b.hmr(self.flag,mask);self.b.free(self.flag);self.flag=None
        self.merge('flagmask',mask)
    def route(self,right):
        if self.virtual:self.b.cswap(self.flag[0],self.B[-1],self.B[-2])
        else:C.rotate(self.b,self.B,self.flag[0],right)
    def border(self,inverse,partial=None,skip_top=False):
        if partial is None:
            if self.virtual:
                (C.virtual.lower if inverse else C.virtual.upper)(self.b,self.B[:-1],self.rhss,self.flag[0])
            else:(C.lower_border if inverse else C.upper_border)(self.b,self.B,self.rhss)
            return
        for k in range(self.n-1-partial,self.n-1-int(skip_top)):
            coefficient=self.B[k];masked=None
            if self.virtual:
                masked=self.b.alloc_qubits(12)
                # v_k=C_k+g(C_k+C_(k-1)); the top C_k is0 on g.
                self.b.cx(self.B[k-1],coefficient)
                self.b.init_and(self.flag[0],coefficient,masked)
                self.b.cx(self.B[k-1],coefficient);self.b.cx(masked,coefficient)
            for r in self.rhss:
                xor_product(self.b,coefficient,r[-1] if inverse else r[k],r[k] if inverse else r[-1])
            if masked is not None:
                self.b.cx(masked,coefficient);self.b.cx(self.B[k-1],coefficient)
                self.b.del_and(self.flag[0],coefficient,masked)
                self.b.cx(self.B[k-1],coefficient);self.b.free(masked)
    def header(self,inverse,partial,consume=True):
        self.query(consume=consume);self.route(True)
        reciprocal=C.compact_inverse_twelve(self.b,self.B[-1])
        if consume:C.accept_debt(self.b,reciprocal,self.n,self.context,self.closing)
        scale(self.b,self.heads,self.B[-1],reciprocal,inverse)
        self.shared_top=bool(partial and self.virtual);self.shared_lower=inverse
        self.border(inverse,partial,self.shared_top)
        return reciprocal
    def shared_neighbor(self,q0,q1,low):
        b=self.b;coefficients=self.B[:-1];g=self.flag[0]
        masked=b.alloc_qubits(12);b.init_and(g,coefficients[-2],masked)
        b.cx(masked,coefficients[-1])
        for point,target in enumerate(low):add_scaled(b,q0,target,F.pow(point,len(low)))
        xor_product(b,q1,coefficients[-1],q0)
        for point,target in enumerate(low):add_scaled(b,q0,target,F.pow(point,len(low)))
        for r in self.rhss:
            xor_product(b,coefficients[-1],r[-1] if self.shared_lower else r[-2],
                        r[-2] if self.shared_lower else r[-1])
        b.cx(masked,coefficients[-1]);b.del_and(g,coefficients[-2],masked);b.free(masked)
    def shared_source(self,reciprocal=None,reverse=False):
        if self.n==17:
            return self.gauge_shared_source(reciprocal,reverse)
        b=self.b;beta=self.B[-1];q0=self.A[-2];q1=self.A[-1];low=self.A[:-2]
        evaluate_low(b,low)
        if reverse:
            C.virtual.products(b,self.B[:-1],low,q0,q1,self.flag[0])
            reciprocal=C.compact_inverse_twelve(b,beta)
            scale(b,[q0],beta,reciprocal,False)
            self.shared_neighbor(q0,q1,low)
            scale(b,[q1],beta,reciprocal,False)
        else:
            scale(b,[q1],beta,reciprocal,True)
            self.shared_neighbor(q0,q1,low)
            scale(b,[q0],beta,reciprocal,True)
            debt=C.erase_inverse_word(b,beta,reciprocal,True)
            C.virtual.products(b,self.B[:-1],low,q0,q1,self.flag[0])
        evaluate_low(b,low,True)
        return reciprocal if reverse else debt
    def gauge_shared_source(self,reciprocal=None,reverse=False):
        """Top source map with a parked gauge and deferred old-head masks.

        No operation reads the parked beta or reciprocal. Both exact old
        target masks are paid at the handoff where their inverse multiplier
        and the new target are simultaneously restored.
        """
        assert self.n==17 and self.shared_top
        b=self.b;beta=self.B[-1];q0=self.A[-2];q1=self.A[-1];low=self.A[:-2]
        carrier=self.context.gauge_carrier
        carrier.assert_anchor(q1)
        carrier.move(beta, 'top17 source: leader to selected beta')
        evaluate_low(b,low)
        if not reverse:
            m1=deferred_scale(b,q1,reciprocal)
            self.shared_neighbor(q0,q1,low)
            m0=deferred_scale(b,q0,reciprocal)
            debt=C.erase_inverse_word(b,beta,reciprocal,True)
            C.virtual.products(b,self.B[:-1],low,q0,q1,self.flag[0])
            evaluate_low(b,low,True)
            def pay():
                repay_scale(b,q1,beta,m1)
                repay_scale(b,q0,beta,m0)
            carrier.move(q1, 'top17 source: beta to quotient leader', pay)
            return debt
        C.virtual.products(b,self.B[:-1],low,q0,q1,self.flag[0])
        # A compact22 reciprocal plus the local gap bit fits while the
        # gauge is decoded. Then move its sentinel directly to that unit.
        carrier.unpark('top17 return: expose selected beta')
        reciprocal=C.compact_inverse_twelve(b,beta)
        carrier.park(reciprocal, 'top17 return: reciprocal sentinel')
        m0=deferred_scale(b,q0,beta)
        # Neighbor changes q0. Pay its exact old-target debt now, using
        # the sparse parked reciprocal chart without moving the anchor.
        # The helper restores the clean gauge wire and merges its HMR mask.
        repay_parked_scale(b,carrier,q0,m0,
                           'top17 return: pay old constant quotient while parked')
        self.shared_neighbor(q0,q1,low)
        m1=deferred_scale(b,q1,beta)
        evaluate_low(b,low,True)
        def pay():
            repay_scale(b,q1,reciprocal,m1)
        carrier.move(q1, 'top17 return: reciprocal to restored leader', pay)
        return reciprocal

    def source(self,reciprocal):
        if self.shared_top:debt=self.shared_source(reciprocal)
        elif self.virtual:debt=C.virtual.source_forward(self.b,self.A,self.B,reciprocal,self.flag[0],True)
        else:
            C.source_division(self.b,self.A,self.B,reciprocal,False)
            debt=C.erase_inverse_word(self.b,self.B[-1],reciprocal,True)
        self.merge('debt',debt);self.route(False)
        C.swap_low(self.b,self.low,self.B[:-1],self.flag[0]);self.release()
    def source_only(self):
        self.query();self.route(True)
        self.source(C.compact_inverse_twelve(self.b,self.B[-1]))
    def undo_source(self,shared_partial=None,lower=True):
        self.query(pay=True);C.swap_low(self.b,self.low,self.B[:-1],self.flag[0]);self.route(True)
        self.shared_top=bool(shared_partial and self.virtual);self.shared_lower=lower
        if self.shared_top:reciprocal=self.shared_source(reverse=True)
        elif self.virtual:reciprocal=C.virtual.source_reverse(self.b,self.A,self.B,self.flag[0])
        else:
            reciprocal=C.compact_inverse_twelve(self.b,self.B[-1])
            C.source_division(self.b,self.A,self.B,reciprocal,False,True)
        C.repay_inverse_mask(self.b,reciprocal,self.debt);self.debt=None
        return reciprocal
    def finish(self,reciprocal,inverse,partial):
        self.border(not inverse,partial,self.shared_top and partial is not None)
        scale(self.b,self.heads,self.B[-1],reciprocal,inverse)
        C.finish_reciprocal(self.b,self.B[-1],reciprocal,self.n,self.context,self.closing)
        self.route(False)
        if self.context is not None and not self.closing:
            mask=self.b.alloc_bits(1);self.b.hmr(self.flag,mask);self.context.flags[self.n]=mask
        else:C.erase_zero(self.b,self.B[-1],self.flag)
        self.b.free(self.flag);self.flag=None
    def local(self,inverse):
        C.local(self.b,self.A,self.B,self.rhss,self.previous,inverse,self.context,self.closing)


def emit(builder,A,B,rhss,inverse,previous,context,closing):
    n=len(B);assert n>=4 and context is not None
    m=n-3;steps=[];a=A;b=B;rs=rhss;prior=previous
    fuse_upper=n in TRANSPOSE_WINDOWS
    def low_basis(reverse=False,transpose=False):
        for rhs in rhss:
            if transpose:apply_inplace_linear(builder,flat(rhs[:m]),C.virtual.dual_evaluation_rows(m,reverse))
            else:evaluate_low(builder,rhs[:m],reverse)
    def overflow(transpose=False):
        for rhs in rhss:
            if transpose:
                for point,value in enumerate(rhs[:m]):
                    for degree,target in enumerate(rhs[m:],m):add_scaled(builder,value,target,F.pow(point,degree))
            else:high_terms(builder,rhs[:m],list(enumerate(rhs[m:],m)))
    if inverse or fuse_upper:low_basis(transpose=not inverse);overflow(transpose=not inverse)
    for j in range(3):
        step=Step(builder,a,b,rs,prior,context,closing);steps.append(step)
        reciprocal=step.header(inverse,2-j if inverse or fuse_upper else None)
        if (inverse or fuse_upper) and j==2:
            step.merge('debt',C.erase_inverse_word(builder,step.B[-1],reciprocal,True))
            step.route(False)
            if inverse:
                # The physical third source witness is already queried.
                # Keep its quantum flag through the forward tensor; that
                # tensor does not release or return a mask for this bit.
                assert tuple(step.B[-1]) == tuple(B[n-3])
                tensor.emit(builder,A[:n-1],B[:n-2],B[n-2],B[n-1],rhss,
                            lambda slot,mask:steps[slot].merge('flagmask',mask),step.flag)
                low_basis(True,False)
                # Exactly source_only(), with its duplicate query removed.
                # No extra bit survives into the old source arithmetic.
                step.route(True)
                step.source(C.compact_inverse_twelve(builder,step.B[-1]))
            else:
                step.release()
                handoff=transpose_tensor.emit(builder,A[:n-1],B[:n-2],B[n-2],B[n-1],rhss,
                            lambda slot,mask:steps[slot].merge('flagmask',mask))
                step.adopt(handoff)
                low_basis(True,True)
                # Exactly source_only(), with its duplicate query removed.
                step.route(True)
                step.source(C.compact_inverse_twelve(builder,step.B[-1]))
        else:step.source(reciprocal)
        a,b,rs,prior=step.B,step.low,[r[:-1] for r in rs],step.quotient
    if inverse:
        for step in steps:
            if n==17 and step.n==17:
                context.gauge_carrier.unpark('top17 and16 prefix locals')
            step.local(True)
            if n==17 and step.n==16:
                context.gauge_carrier.park(A[-1], 'park during lower recursion')
    C.frame(builder,a,b,rs,False,inverse,prior,context,closing)
    if not inverse:
        for step in reversed(steps):
            if n==17 and step.n==16:
                context.gauge_carrier.unpark('top16 and17 closing locals')
            step.local(False)
            if n==17 and step.n==17:
                context.gauge_carrier.park(A[-1], 'park through source restoration')
    if not inverse or fuse_upper:
        step=steps[2];reciprocal=step.undo_source()
        step.merge('debt',C.erase_inverse_word(builder,step.B[-1],reciprocal,True))
        step.route(False)
        if not inverse:
            assert tuple(step.B[-1]) == tuple(B[n-3])
            # undo_source().query(pay=True) already retired every old mask
            # for this witness. No new third mask is created in the tensor.
            assert step.flagmask is None and step.n not in context.local_flags
            low_basis(transpose=False)
            tensor.emit(builder,A[:n-1],B[:n-2],B[n-2],B[n-1],rhss,
                        lambda slot,mask:steps[slot].merge('flagmask',mask),step.flag)
            assert step.flagmask is None and step.n not in context.local_flags
        else:
            step.release()
            low_basis(transpose=True)
            handoff=transpose_tensor.emit(builder,A[:n-1],B[:n-2],B[n-2],B[n-1],rhss,
                        lambda slot,mask:steps[slot].merge('flagmask',mask))
            step.adopt(handoff,pay=True)
        step.route(True)
        reciprocal=C.compact_inverse_twelve(builder,step.B[-1])
        C.repay_inverse_mask(builder,reciprocal,step.debt);step.debt=None
        step.finish(reciprocal,inverse,0)
        for j in (1,0):
            step=steps[j];step.finish(step.undo_source(2-j,not inverse),inverse,2-j)
        overflow(transpose=inverse);low_basis(True,inverse)
    else:
        for step in reversed(steps):step.finish(step.undo_source(),True,None)
    assert all(s.flag is None and s.flagmask is None and s.debt is None for s in steps)
