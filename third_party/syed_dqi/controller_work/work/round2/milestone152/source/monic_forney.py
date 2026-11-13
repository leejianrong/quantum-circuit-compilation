# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""Monic odd-degree Forney conversion on the normal half-Euclidean profile.

All words are 12-bit polynomial-basis views. No data-dependent profile is
selected here. D is preserved; its leading one is implicit. Every reciprocal
lifetime and measurement phase is closed within the call.
"""
from functools import cache
import kickmix as km
from field_tensor import invert_field_matrix
from tower_inverse import apply_inplace_linear,rows_from_columns,xor_product
from quantum_reciprocal import xor_linear
from compact_inverse import compact_inverse_twelve
from projective_carry import erase_inverse_word,power_rows
from dual_scale import scale_word
import unit_toeplitz

F=km.GF2Field(12)
def flat(words):return km.array([q for w in words for q in w])

@cache
def constant_columns(c):return tuple(F.mul(c,1<<j) for j in range(12))
def add_constant(builder,word,value):
    for j in range(12):
        if value>>j&1:builder.x(word[j])
def add_scaled(builder,source,target,c):
    if c:xor_linear(builder,source,target,constant_columns(c))

@cache
def evaluation_rows(size,inverse=False):
    matrix=[[F.pow(x,k) for k in range(size)] for x in range(size)]
    if inverse:matrix=invert_field_matrix(matrix,F)
    columns=[]
    for k in range(size):
        for bit in range(12):
            columns.append(sum(F.mul(matrix[j][k],1<<bit)<<(12*j) for j in range(size)))
    return rows_from_columns(columns)
def evaluate_low(builder,words,inverse=False):
    if words:apply_inplace_linear(builder,flat(words),evaluation_rows(len(words),inverse))
def high_terms(builder,low,high,implicit_degree=None):
    for point,target in enumerate(low):
        for degree,source in high:add_scaled(builder,source,target,F.pow(point,degree))
        if implicit_degree is not None:add_constant(builder,target,F.pow(point,implicit_degree))

def scale(builder,words,b,reciprocal,divide):
    temporary=builder.alloc_qubits(12)
    for word in words:
        scale_word(builder,word,reciprocal if divide else b,b if divide else reciprocal,temporary)
    builder.free(temporary)

def source_division(builder,A,B,reciprocal,monic=False,reverse=False):
    """A(degree b+1) <-> (C in low b words,Q in upper words).

    For monic A the implicit leading quotient is the supplied reciprocal.
    The low coefficient words first carry evaluations of the FULL dividend,
    so one point product suffices per remainder word despite truncation.
    """
    b=len(B)-1;assert b>=1 and len(A)==b+2-int(monic)
    low=A[:b];q0=A[b];q1=reciprocal if monic else A[b+1]
    high=[(b,A[b])]+([] if monic else [(b+1,A[b+1])])
    evaluate_low(builder,low)
    if not reverse:
        high_terms(builder,low,high,b+1 if monic else None)
        if not monic:scale(builder,[q1],B[-1],reciprocal,True)
        xor_product(builder,B[-2],q1,q0)
        scale(builder,[q0],B[-1],reciprocal,True)
    evaluate_low(builder,B[:-1]);high_terms(builder,B[:-1],[(b,B[-1])])
    for point,target in enumerate(low):
        add_scaled(builder,q1,q0,point)
        xor_product(builder,q0,B[point],target)
        add_scaled(builder,q1,q0,point)
    high_terms(builder,B[:-1],[(b,B[-1])]);evaluate_low(builder,B[:-1],True)
    if reverse:
        scale(builder,[q0],B[-1],reciprocal,False)
        xor_product(builder,B[-2],q1,q0)
        if not monic:scale(builder,[q1],B[-1],reciprocal,False)
        high_terms(builder,low,high,b+1 if monic else None)
    evaluate_low(builder,low,True)

def lower_border(builder,B,rhss):
    for rhs in rhss:
        for coefficient,target in zip(B[:-1],rhs[:-1]):xor_product(builder,coefficient,rhs[-1],target)
def upper_border(builder,B,rhss):
    for rhs in rhss:
        for coefficient,source in zip(B[:-1],rhs[:-1]):xor_product(builder,coefficient,source,rhs[-1])

def bezout_map(builder,A,B,rhss,monic=False,inverse=True):
    """Apply Bez(A,B)^(-1) or Bez(A,B), for successive degree drops one."""
    n=len(B);assert len(A)==n+1-int(monic) and all(len(y)==n for y in rhss)
    heads=[rhs[-1] for rhs in rhss]
    if n==1:
        # Bez_1(A,b) is the scalar a1*b, independent of a0.
        for factor in ([B[0]] if monic else [A[-1],B[0]]):
            reciprocal=compact_inverse_twelve(builder,factor)
            scale(builder,heads,factor,reciprocal,inverse)
            erase_inverse_word(builder,factor,reciprocal)
        return
    reciprocal=compact_inverse_twelve(builder,B[-1])
    if inverse:
        scale(builder,heads,B[-1],reciprocal,True)
        lower_border(builder,B,rhss)
    else:
        scale(builder,heads,B[-1],reciprocal,False)
        upper_border(builder,B,rhss)
    source_division(builder,A,B,reciprocal,monic)
    if monic:
        # q1=1/b. Its inverse block multiplies the RHS heads by b.
        scale(builder,heads,B[-1],reciprocal,not inverse)
    erase_inverse_word(builder,B[-1],reciprocal)
    if not monic:
        q1=A[-1];reciprocal=compact_inverse_twelve(builder,q1)
        scale(builder,heads,q1,reciprocal,inverse)
        erase_inverse_word(builder,q1,reciprocal)
    bezout_map(builder,B,A[:-1] if monic else A[:-2],[y[:-1] for y in rhss],False,inverse)
    reciprocal=compact_inverse_twelve(builder,B[-1])
    source_division(builder,A,B,reciprocal,monic,True)
    if inverse:
        upper_border(builder,B,rhss)
        scale(builder,heads,B[-1],reciprocal,True)
    else:
        lower_border(builder,B,rhss)
        scale(builder,heads,B[-1],reciprocal,False)
    erase_inverse_word(builder,B[-1],reciprocal)

def half_stage(builder,A,B,rhss,inverse):
    """Equal degree A and implicit-monic B. Initial quotient may be zero."""
    assert len(A)==len(B)+1
    for a,b in zip(A[:-1],B):xor_product(builder,A[-1],b,a)
    bezout_map(builder,B,A[:-1],rhss,monic=True,inverse=inverse)
    for a,b in zip(A[:-1],B):xor_product(builder,A[-1],b,a)

def parity_map(builder,D,O,inverse):
    n=len(D)//2;even=O[::2][:-1];odd=O[1::2];h=O[-1]
    # Inverse reverses the complementary border and parity exchange first.
    if inverse:
        for coefficient,value in zip(D[1::2],even):xor_product(builder,coefficient,value,h)
        for a,b in zip(even,odd):builder.swap(a,b)
    else:
        for coefficient,value in zip(D[1::2],even):xor_product(builder,h,coefficient,value)
    for word in D+even+odd:apply_inplace_linear(builder,word,power_rows(2048))
    half_stage(builder,D[::2],D[1::2],[even,odd],not inverse)
    for word in D+even+odd:apply_inplace_linear(builder,word,power_rows(2))
    if inverse:
        for coefficient,value in zip(D[1::2],even):xor_product(builder,h,coefficient,value)
    else:
        for a,b in zip(even,odd):builder.swap(a,b)
        for coefficient,value in zip(D[1::2],even):xor_product(builder,coefficient,value,h)

def emit(builder,locator,numerator,inverse=False):
    D=list(locator);O=list(numerator)
    assert len(D)==len(O) and len(D)>=3 and len(D)%2
    coefficients=list(reversed(D[1:]))
    if inverse:
        for i in range(len(O)//2):builder.swap(O[i],O[-1-i])
        unit_toeplitz.emit(builder,coefficients,O,True)
        parity_map(builder,D,O,True)
    else:
        parity_map(builder,D,O,False)
        unit_toeplitz.emit(builder,coefficients,O)
        for i in range(len(O)//2):builder.swap(O[i],O[-1-i])
