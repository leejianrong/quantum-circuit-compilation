# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""Virtual divisor borders and a reciprocal-lifetime-aware source map."""
from functools import cache
import kickmix as km
from monic_forney import (F,flat,constant_columns,add_scaled,evaluation_rows,
                         evaluate_low,scale)
from field_tensor import invert_field_matrix
from tower_inverse import apply_inplace_linear,rows_from_columns,xor_product,phase_product,kernel
from compact_inverse import compact_inverse_twelve
from projective_carry import erase_inverse_word

@cache
def dual_evaluation_rows(size,inverse=False):
    E=[[F.pow(x,k) for k in range(size)] for x in range(size)]
    if not inverse:E=invert_field_matrix(E,F)
    E=[list(row) for row in zip(*E)]
    cols=tuple(sum(F.mul(E[i][j],1<<bit)<<(12*i) for i in range(size))
               for j in range(size) for bit in range(12))
    return rows_from_columns(cols)

def lower(builder,C,rhss,g):
    evaluate_low(builder,C)
    for rhs in rhss:
        h=rhs[-1];low=rhs[:-1];assert len(low)==len(C)
        evaluate_low(builder,low)
        masked=builder.alloc_qubits(12);builder.init_and(g,h,masked)
        for point,(coefficient,target) in enumerate(zip(C,low)):
            add_scaled(builder,masked,h,point^1)
            xor_product(builder,coefficient,h,target)
            add_scaled(builder,masked,h,point^1)
        builder.del_and(g,h,masked);builder.free(masked)
        evaluate_low(builder,low,True)
    evaluate_low(builder,C,True)

def upper(builder,C,rhss,g):
    evaluate_low(builder,C)
    for rhs in rhss:
        h=rhs[-1];low=rhs[:-1];assert len(low)==len(C)
        apply_inplace_linear(builder,flat(low),dual_evaluation_rows(len(low)))
        moment=builder.alloc_qubits(12)
        for point,(coefficient,source) in enumerate(zip(C,low)):
            add_scaled(builder,h,moment,point^1)
            xor_product(builder,coefficient,source,h)
            add_scaled(builder,h,moment,point^1)
        builder.ccx(g,moment,h)
        mask=builder.alloc_bits(12);builder.hmr(moment,mask);builder.free(moment)
        for point,(coefficient,source) in enumerate(zip(C,low)):
            factor=point^1
            if not factor:continue
            apply_inplace_linear(builder,coefficient,rows_from_columns(constant_columns(factor)))
            phase_product(builder,coefficient,source,mask,kernel(12))
            apply_inplace_linear(builder,coefficient,rows_from_columns(constant_columns(F.invert(factor))))
        builder.free(mask)
        apply_inplace_linear(builder,flat(low),dual_evaluation_rows(len(low),True))
    evaluate_low(builder,C,True)

def neighbor_product(builder,C,q1,q0,low,g):
    """Fan out the leading-quotient times neighbor product, including evaluation lanes."""
    assert len(C)>=2
    masked=builder.alloc_qubits(12);builder.init_and(g,C[-2],masked)
    builder.cx(masked,C[-1])
    for point,target in enumerate(low):add_scaled(builder,q0,target,F.pow(point,len(low)))
    xor_product(builder,q1,C[-1],q0)
    for point,target in enumerate(low):add_scaled(builder,q0,target,F.pow(point,len(low)))
    builder.cx(masked,C[-1]);builder.del_and(g,C[-2],masked);builder.free(masked)

def products(builder,C,low,q0,q1,g):
    masked0=builder.alloc_qubits(12);masked1=builder.alloc_qubits(12)
    builder.init_and(g,q0,masked0);builder.init_and(g,q1,masked1)
    evaluate_low(builder,C)
    for point,(coefficient,target) in enumerate(zip(C,low)):
        def expose():
            add_scaled(builder,q1,q0,point)
            add_scaled(builder,masked0,q0,point^1)
            add_scaled(builder,masked1,q0,F.mul(point,point^1))
        expose();xor_product(builder,coefficient,q0,target);expose()
    evaluate_low(builder,C,True)
    builder.del_and(g,q1,masked1);builder.del_and(g,q0,masked0)
    builder.free(masked1);builder.free(masked0)

def source_forward(builder,A,B,reciprocal,g,defer_reciprocal=False):
    """Consume and clean the supplied reciprocal after dividing the two heads."""
    b=len(B)-1;assert len(A)==b+2 and b>=2
    low=A[:b];q0=A[b];q1=A[b+1];C=B[:-1];beta=B[-1]
    evaluate_low(builder,low)
    scale(builder,[q1],beta,reciprocal,True)
    neighbor_product(builder,C,q1,q0,low,g)
    scale(builder,[q0],beta,reciprocal,True)
    debt=erase_inverse_word(builder,beta,reciprocal,defer=defer_reciprocal)
    products(builder,C,low,q0,q1,g)
    evaluate_low(builder,low,True)
    return debt

def source_reverse(builder,A,B,g):
    """Create the returning reciprocal only after both mask words are erased."""
    b=len(B)-1;assert len(A)==b+2 and b>=2
    low=A[:b];q0=A[b];q1=A[b+1];C=B[:-1];beta=B[-1]
    evaluate_low(builder,low)
    products(builder,C,low,q0,q1,g)
    reciprocal=compact_inverse_twelve(builder,beta)
    scale(builder,[q0],beta,reciprocal,False)
    neighbor_product(builder,C,q1,q0,low,g)
    scale(builder,[q1],beta,reciprocal,False)
    evaluate_low(builder,low,True)
    return reciprocal
