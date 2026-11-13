# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""Paired unit division with source-only reciprocal phase debt.

The prefix leaves only a random classical mask of inverse(factor), never
of a target. The matching multiplication folds its repayment into the
already required quotient-phase pass. The factor must have its original
value at both calls; all target-dependent phases are paid locally.
"""
from compact_inverse import compact_inverse_twelve
from projective_carry import erase_inverse_word
from monic_forney import scale
from low_cached_arithmetic import scale_words
from functools import cache
import kickmix as km
from field_tensor import apply_linear,invert_binary_columns,parity_pivot
from quantum_reciprocal import xor_linear
from tower_inverse import quadratic_basis,xor_product,kernel
from cubic_inverse130 import phase_inverse_trace_twelve,phase_inverse_twelve_35

FIELD=km.GF2Field(12)


def trace(value):
    result=0
    for _ in range(12):result^=value;value=FIELD.mul(value,value)
    assert result in (0,1)
    return result


@cache
def trace_columns():
    columns=tuple(sum(trace(FIELD.mul(1<<j,1<<k))<<k for k in range(12)) for j in range(12))
    inverse_rows=invert_binary_columns(columns)
    polynomial=tuple(apply_linear(inverse_rows,1<<j) for j in range(12))
    tower=tuple(apply_linear(inverse_rows,row) for row in quadratic_basis(12)['to_tower'])
    assert all(trace(FIELD.mul(polynomial[i],1<<j))==int(i==j) for i in range(12) for j in range(12))
    assert all(trace(FIELD.mul(tower[i],1<<j))==((quadratic_basis(12)['to_tower'][i]>>j)&1)
               for i in range(12) for j in range(12))
    return polynomial,tower


def classical_word(builder,width=12,value=False):
    word=builder.alloc_bits(width);builder.bit_store(word,value);return word


def classical_inverse(builder,source):
    """Classical exponentiation; allocates no quantum workspace or T gates."""
    value=source;owned=[]
    square_columns=tuple(FIELD.mul(1<<j,1<<j) for j in range(12))
    for bit in bin(4094)[3:]:
        squared=classical_word(builder);owned.append(squared)
        xor_linear(builder,value,squared,square_columns);value=squared
        if bit=='1':
            product=classical_word(builder);owned.append(product)
            for a,b,output in kernel(12):
                first=parity_pivot(builder,value,a);second=parity_pivot(builder,source,b)
                builder.push_condition(first)
                builder.cx(second,km.array([product[j] for j in range(12) if output>>j&1]))
                builder.pop_condition()
                parity_pivot(builder,source,b);parity_pivot(builder,value,a)
            value=product
    return value,owned


def classical_scale(builder,word,multiplier,inverse_multiplier):
    temporary=builder.alloc_qubits(12)
    xor_product(builder,word,multiplier,temporary);builder.swap(word,temporary)
    xor_product(builder,word,inverse_multiplier,temporary);builder.free(temporary)


def quotient_phases(builder,factor,targets,inverse_mask):
    """Repay two quotient masks and inverse debt with a65/35-T branch.

    For fresh independent12-bit RHS masks, exact expected T is
    65-30/2**24. Static count100 includes both exclusive branches. The
    all-zero-RHS-mask branch is exact and never an excluded input class.
    Every input word and mask is preserved; peak scratch22.
    """
    assert len(targets)==2 and len(factor)==len(inverse_mask)==12
    (x,xmask),(y,ymask)=targets
    assert all(len(w)==12 for w in (x,xmask,y,ymask))
    assert len(set(factor)|set(x)|set(y))==36
    polynomial,tower=trace_columns()
    mu=classical_word(builder);nu=classical_word(builder);alpha=classical_word(builder)
    xor_linear(builder,xmask,mu,polynomial);xor_linear(builder,ymask,nu,polynomial)
    xor_linear(builder,inverse_mask,alpha,tower)
    active=classical_word(builder,1)
    builder.bit_store(active[0],True,control=km.array(list(mu)+list(nu)))
    first_active=classical_word(builder,1);builder.bit_store(first_active[0],True,control=mu)
    swap=classical_word(builder,1,True);builder.cx(first_active,swap)
    builder.push_condition(active[0])
    builder.push_condition(swap[0]);builder.swap(x,y);builder.swap(mu,nu);builder.pop_condition()
    reciprocal,owned=classical_inverse(builder,mu)
    classical_scale(builder,x,mu,reciprocal)
    xor_product(builder,y,nu,x);builder.cx(alpha,x)
    phase_inverse_trace_twelve(builder,factor,x)
    builder.cx(alpha,x);xor_product(builder,y,nu,x)
    classical_scale(builder,x,reciprocal,mu)
    for word in owned:builder.free(word)
    builder.push_condition(swap[0]);builder.swap(mu,nu);builder.swap(x,y);builder.pop_condition()
    builder.pop_condition()
    builder.x(active)
    builder.push_condition(active[0])
    phase_inverse_twelve_35(builder,factor,inverse_mask)
    builder.pop_condition()
    for word in (swap,first_active,active,alpha,nu,mu):builder.free(word)


def divide_prefix(builder,words,factor):
    reciprocal=compact_inverse_twelve(builder,factor)
    scale(builder,words,factor,reciprocal,True)
    return erase_inverse_word(builder,factor,reciprocal,True)


def multiply_closing(builder,words,factor,inverse_mask):
    masks=scale_words(builder,words,factor,defer=True)
    quotient_phases(builder,factor,list(zip(words,masks)),inverse_mask)
    for mask in masks:builder.free(mask)
    builder.free(inverse_mask)
