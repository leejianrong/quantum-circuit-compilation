# Isolated post-v3 sibling; exact joint norm phase and unchanged rare branch.
# Credits: Opus and Astra.
# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""Separate joint-norm quotient phase with the checked rare classical branch.

The main quantum-numerator branch uses the new62-T exact phase. The unchanged
classical-only branch uses27 T and skips its own zero mask. Static89 includes
both exclusive branches. Fresh independent masks give the exact expectation
62-35/2**24-27/2**36. The phase caller has22 helpers; source division and
consuming multiplication interfaces retain their original implementations.
No accepted or previous prepared provider is modified.
"""
from gauge_park_lender import compact_inverse_twelve
from projective_carry import erase_inverse_word
from monic_forney import scale
from low_cached_arithmetic import scale_words
from functools import cache
import kickmix as km
from field_tensor import apply_linear,invert_binary_columns,parity_pivot
from quantum_reciprocal import xor_linear
from tower_inverse import quadratic_basis,xor_product,kernel
from quotient_phase62 import phase_inverse_trace_twelve
import phase_inverse12 as Phase27
from fractions import Fraction

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


def record_uniform_hmr_event(name, conditional_t, mask_bits):
    """Exact source-expectation hook; no emitted operation or sample."""
    return None


def phase_trace_classical27(builder, factor, alpha):
    """Phase Tr(alpha*inv0(factor)); alpha is classical polynomial data.

    At alpha=0 every phase is absent. The existing12-helper trace primitive
    is applied to factor/alpha on the nonzero branch, then source is restored.
    This helper deliberately has no unconditional fresh-mask expectation hook:
    its caller nests it in a24-bit mask-zero branch.
    """
    assert len(factor) == len(alpha) == 12
    reciprocal, owned = classical_inverse(builder, alpha)
    active = classical_word(builder, 1)
    builder.bit_store(active[0], True, control=alpha)
    builder.push_condition(active[0])
    classical_scale(builder, factor, reciprocal, alpha)
    Phase27.fixed_inverse_trace12(builder, factor)
    classical_scale(builder, factor, alpha, reciprocal)
    builder.pop_condition()
    for word in owned:
        builder.free(word)
    builder.free(active)


def expected_fresh_T():
    return Fraction(62)-Fraction(35, 1 << 24)-Fraction(27, 1 << 36)


def quotient_phases(builder,factor,targets,inverse_mask):
    """Same zero-safe quotient phase with a joint norm/relative-trace product.

    Static89 includes both exclusive62/27 branches. For three fresh
    independent12-bit masks, exact expectation is62-35/2**24-27/2**36.
    Every source/target/mask is preserved. Peak22 helpers suffices for this phase.
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
    phase_trace_classical27(builder,factor,alpha)
    builder.pop_condition()
    for word in (swap,first_active,active,alpha,nu,mu):builder.free(word)
    # These events jointly price the nested classical guards; charging an
    # unconditional27/4096 discount here would be incorrect.
    record_uniform_hmr_event('paired_dual62_exclusive_overlap', 27, 0)
    record_uniform_hmr_event('paired_dual62_rhs_zero', 35, 24)
    record_uniform_hmr_event('paired_dual62_all_masks_zero', 27, 36)


def divide_prefix(builder,words,factor):
    reciprocal=compact_inverse_twelve(builder,factor)
    scale(builder,words,factor,reciprocal,True)
    return erase_inverse_word(builder,factor,reciprocal,True)


def multiply_closing(builder,words,factor,inverse_mask):
    masks=scale_words(builder,words,factor,defer=True)
    quotient_phases(builder,factor,list(zip(words,masks)),inverse_mask)
    for mask in masks:builder.free(mask)
    builder.free(inverse_mask)
