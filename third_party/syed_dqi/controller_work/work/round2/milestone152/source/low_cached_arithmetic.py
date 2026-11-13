# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""Low-space scaling/folds using72T kernels, with the original mask contracts."""
from norm_cached_field import invert_twelve as invert,phase_quotients
from projective_carry import power_rows
from tower_inverse import apply_inplace_linear,xor_product,phase_product,kernel
from normal_fold import shift,add_linear_product
from low_pipeline import repay

def scale_words(builder,words,source,powers=None,defer=False):
    powers=[1]*len(words) if powers is None else powers
    temporary=builder.alloc_qubits(12);masks=[]
    for word,power in zip(words,powers):
        exponent=power.bit_length()-1;assert power==1<<exponent
        if exponent:apply_inplace_linear(builder,source,power_rows(power))
        xor_product(builder,word,source,temporary)
        if exponent:apply_inplace_linear(builder,source,power_rows(1<<((12-exponent)%12)))
        builder.swap(word,temporary)
        mask=builder.alloc_bits(12);builder.hmr(temporary,mask);masks.append(mask)
    builder.free(temporary)
    if defer:return masks
    phase_quotients(builder,source,list(zip(words,masks,powers)))
    for mask in masks:builder.free(mask)

def fold_forward(builder,P,N,D,node):
    shift(builder,P,node);shift(builder,N,node);shift(builder,D,node)
    add_linear_product(builder,P,D[2:],N)
    xor_product(builder,P[1],D[1],N[0])
    bmask=scale_words(builder,[P[1]],D[0],defer=True)
    xor_product(builder,P[0],D[1],P[1])
    amask=scale_words(builder,[P[0]],D[0],defer=True)
    shift(builder,D,node);shift(builder,P+N,node)
    return amask+bmask

def fold_reverse(builder,P,N,D,node,masks):
    shift(builder,P+N,node);shift(builder,D,node)
    invert(builder,D[0])
    amask=scale_words(builder,[P[0]],D[0],defer=True)
    xor_product(builder,P[0],D[1],P[1])
    bmask=scale_words(builder,[P[1]],D[0],defer=True)
    invert(builder,D[0])
    for word,mask in zip(P,amask+bmask):
        phase_product(builder,word,D[0],mask,kernel(12));builder.free(mask)
    repay(builder,P,masks)
    xor_product(builder,P[1],D[1],N[0])
    add_linear_product(builder,P,D[2:],N)
    shift(builder,D,node);shift(builder,N,node);shift(builder,P,node)
