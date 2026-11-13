# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""Explicit-unit-leading top frame for the raw Forney interface.

Inputs are a degree-n A (unit leading stored), proper coprime B in n
words, and independent n-word right-hand sides. Source polynomials and all
scratch are restored. Larger degree drops are outside this emitter's domain.
"""
from coherent_border import toggle_zero
from compact_inverse import compact_inverse_twelve
from projective_carry import erase_inverse_word,repay_inverse_mask
from monic_forney import source_division,scale,lower_border,upper_border
from norm_division import divide
from sized_field130 import invert_twelve18 as invert_twelve
from low_cached_arithmetic import scale_words
from tower_inverse import xor_product
import virtual_divisor as virtual
import paired_converter_scale as paired_scale
from zero_erasure import erase as erase_zero

class PhaseContext:
    """Classical inverse-beta and padding-predicate masks, keyed by logical frame."""
    def __init__(self,builder):
        self.builder_id=id(builder);self.beta={};self.flags={};self.quotients={};self.outer={}

def accept_debt(builder,reciprocal,n,context,closing):
    if context is not None and closing:repay_inverse_mask(builder,reciprocal,context.beta.pop(n))

def finish_reciprocal(builder,beta,reciprocal,n,context,closing):
    if context is not None and not closing:
        assert n not in context.beta
        context.beta[n]=erase_inverse_word(builder,beta,reciprocal,True)
    else:erase_inverse_word(builder,beta,reciprocal)

def rotate(builder,words,flag,right):
    indices=range(len(words)-1)
    if right:indices=reversed(indices)
    for i in indices:builder.cswap(flag,words[i],words[i+1])

def swap_low(builder,A,B,flag):
    for a,b in zip(A,B):builder.cswap(flag,a,b)

def local(builder,A,B,rhss,previous,inverse,context=None,closing=False):
    """The explicit quotient head is zero exactly on a continuation slot."""
    q1=A[-1];heads=[r[-1] for r in rhss]
    def apply_factor():
        if context is None:
            if inverse:divide(builder,heads,q1)
            else:scale_words(builder,heads,q1)
        elif closing:
            assert not inverse
            paired_scale.multiply_closing(builder,heads,q1,context.quotients.pop(len(B)))
        else:
            assert inverse and len(B) not in context.quotients
            context.quotients[len(B)]=paired_scale.divide_prefix(builder,heads,q1)
    if previous is None:
        # The outer quotient lead is a unit; there is no preceding frame.
        apply_factor()
        return
    h=builder.alloc_qubits(1);toggle_zero(builder,q1,h[0])
    prior_heads,prior_q0,prior_q1,prior_monic=previous
    def cross():
        masked=builder.alloc_qubits(12)
        builder.init_and(h[0],prior_q0,masked)
        for head,old_head in zip(heads,prior_heads):xor_product(builder,masked,old_head,head)
        builder.del_and(h[0],prior_q0,masked);builder.free(masked)
    def exchange():
        for head,old_head in zip(heads,prior_heads):builder.cswap(h[0],head,old_head)
    if inverse:cross()
    else:exchange()
    if prior_monic:
        # f=1/q1 on a normal slot, beta on the zero continuation. Both are
        # units. The zero-aware inversion and controls leave the raw tag intact.
        invert_twelve(builder,q1)
        builder.ccx(h[0],B[-1],q1)
        if inverse:scale_words(builder,heads,q1)
        else:divide(builder,heads,q1)
        builder.ccx(h[0],B[-1],q1)
        invert_twelve(builder,q1)
    else:
        builder.cswap(h[0],q1,prior_q1)
        apply_factor()
        builder.cswap(h[0],q1,prior_q1)
    if inverse:exchange()
    else:cross()
    erase_zero(builder,q1,h);builder.free(h)

def scalar_slot(builder,A,B,rhss,monic,inverse,previous,context=None,closing=False):
    heads=[r[0] for r in rhss];beta=B[0]
    if monic:
        if inverse:divide(builder,heads,beta)
        else:scale_words(builder,heads,beta)
        return
    reciprocal=compact_inverse_twelve(builder,beta)
    accept_debt(builder,reciprocal,1,context,closing)
    scale(builder,heads,beta,reciprocal,inverse)
    scale(builder,[A[-1]],beta,reciprocal,True)
    debt=erase_inverse_word(builder,beta,reciprocal,True)
    local(builder,A,B,rhss,previous,inverse,context,closing)
    reciprocal=compact_inverse_twelve(builder,beta)
    repay_inverse_mask(builder,reciprocal,debt)
    scale(builder,[A[-1]],beta,reciprocal,False)
    scale(builder,heads,beta,reciprocal,inverse)
    finish_reciprocal(builder,beta,reciprocal,1,context,closing)

def frame(builder,A,B,rhss,monic,inverse,previous=None,context=None,closing=False):
    n=len(B);assert len(A)==n+1-int(monic) and all(len(r)==n for r in rhss)
    import raw_lower_window
    if not monic and context is not None and n in raw_lower_window.WINDOWS:
        return raw_lower_window.emit(builder,A,B,rhss,inverse,previous,context,closing)
    if n==1:return scalar_slot(builder,A,B,rhss,monic,inverse,previous,context,closing)
    flag=builder.alloc_qubits(1);toggle_zero(builder,B[-1],flag[0])
    if context is not None and closing:
        incoming=context.flags.pop(n);builder.cz(incoming,flag);builder.free(incoming)
    use_virtual=(not monic and n>4)
    def route(right):
        if use_virtual:builder.cswap(flag[0],B[-1],B[-2])
        else:rotate(builder,B,flag[0],right)
    def lower():
        if use_virtual:virtual.lower(builder,B[:-1],rhss,flag[0])
        else:lower_border(builder,B,rhss)
    def upper():
        if use_virtual:virtual.upper(builder,B[:-1],rhss,flag[0])
        else:upper_border(builder,B,rhss)
    route(True)
    beta=B[-1];heads=[r[-1] for r in rhss]
    reciprocal=compact_inverse_twelve(builder,beta)
    accept_debt(builder,reciprocal,n,context,closing)
    scale(builder,heads,beta,reciprocal,inverse)
    if inverse:lower()
    else:upper()
    if use_virtual:
        debt=virtual.source_forward(builder,A,B,reciprocal,flag[0],True)
    else:
        source_division(builder,A,B,reciprocal,monic)
        if inverse and monic:scale(builder,heads,beta,reciprocal,False)
        debt=erase_inverse_word(builder,beta,reciprocal,True)
    # A local paired reciprocal needs 24 arithmetic bits. With a previous
    # frame it also needs a second predicate. Return B to its raw chart
    # early, erase this frame's flag, and reconstruct it from that raw top
    # after the local action. The raw (nonmonic) local action does not read B.
    early_route=bool(inverse and not monic and previous is not None and context is not None)
    if early_route:
        route(False)
        local_flag_mask=builder.alloc_bits(1);builder.hmr(flag,local_flag_mask);builder.free(flag)
        local(builder,A,B,rhss,previous,True,context,closing)
        flag=builder.alloc_qubits(1);toggle_zero(builder,B[-1],flag[0])
        builder.cz(local_flag_mask,flag);builder.free(local_flag_mask)
    elif inverse and not monic:local(builder,A,B,rhss,previous,True,context,closing)
    quotient=(heads,A[n-1],None if monic else A[n],monic)
    low=A[:n-1]
    if not early_route:route(False)
    swap_low(builder,low,B[:-1],flag[0])
    flag_debt=builder.alloc_bits(1);builder.hmr(flag,flag_debt);builder.free(flag)
    frame(builder,B,low,[r[:-1] for r in rhss],False,inverse,quotient,context,closing)
    flag=builder.alloc_qubits(1);toggle_zero(builder,B[-1],flag[0])
    builder.cz(flag_debt,flag);builder.free(flag_debt)
    swap_low(builder,low,B[:-1],flag[0])
    route(True)
    if not inverse and not monic:local(builder,A,B,rhss,previous,False,context,closing)
    if use_virtual:
        reciprocal=virtual.source_reverse(builder,A,B,flag[0])
    else:
        reciprocal=compact_inverse_twelve(builder,beta)
        if not inverse and monic:scale(builder,heads,beta,reciprocal,True)
        source_division(builder,A,B,reciprocal,monic,True)
    repay_inverse_mask(builder,reciprocal,debt)
    if inverse:upper()
    else:lower()
    scale(builder,heads,beta,reciprocal,inverse)
    finish_reciprocal(builder,beta,reciprocal,n,context,closing)
    route(False)
    if context is not None and not closing:
        assert n not in context.flags
        mask=builder.alloc_bits(1);builder.hmr(flag,mask);context.flags[n]=mask
    else:erase_zero(builder,B[-1],flag)
    builder.free(flag)

def emit(builder,A,B,rhss,inverse=True,context=None,closing=False):
    A,B=list(A),list(B);rhss=[list(r) for r in rhss]
    assert len(A)==len(B)+1 and len(rhss)==2
    assert len(set(q for word in A+B+sum(rhss,[]) for q in word))==48*len(B)+12
    if context is not None:assert context.builder_id==id(builder)
    frame(builder,A,B,rhss,False,inverse,context=context,closing=closing)
    if context is not None:
        assert not context.beta if closing else set(context.beta)==set(range(1,len(B)+1))
        assert not context.flags if closing else set(context.flags)==set(range(2,len(B)+1))
        assert not context.quotients if closing else set(context.quotients)==set(range(1,len(B)+1))

def legacy_monic_model(n,inverse=True):
    """Historical comparison only; NOT a model of this explicit-top emitter."""
    assert n>=1
    if n==1:return dict(T=199 if inverse else 154,expected_T=(199 if inverse else 154)-4/64,scratch=18)
    ordinary=365 if inverse else 320
    special=460 if inverse else 505
    total=668+324*(n-1)
    for size in range(n-1,1,-1):total+=668+324*(size-1)+(special if size==n-1 else ordinary)
    total+=456+(special if n==2 else ordinary)
    # One six-bit masked phase per explicit local unit, plus two extra in the
    # fixed frame immediately below the implicit-monic head.
    phases=n+1
    total-=sum(48*size-216 for size in range(5,n))
    total-=36*n+11*(n-1)
    return dict(T=total,expected_T=total-phases*4/64,scratch=25,conditional_four_T_phases=phases)
