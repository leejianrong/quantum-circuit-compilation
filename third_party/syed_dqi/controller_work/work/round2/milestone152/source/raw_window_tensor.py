# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""Forward three-border tensor in the explicit raw source chart.

At the post-two-source boundary F=A[:a-1], G=B[:a-2], low_head=B[a-2],
high_head=B[a-1]. Flags are zero(high_head), zero(F[-1]), zero(G[-1]). This differs
from the source-head packing in the supplied monic prose. Flags 000,
100,010,001 are admitted. 101 is an explicit exclusion, never inferred
to be rare for a padded locator distribution.
"""
import kickmix as km
from monic_forney import evaluate_low,high_terms,add_scaled
from coherent_border import toggle_zero
from tower_inverse import xor_product,phase_product,kernel


def evaluate(builder,words,m,reverse=False):
    low=words[:m];high=list(enumerate(words[m:],m))
    if reverse:high_terms(builder,low,high);evaluate_low(builder,low,True)
    else:evaluate_low(builder,low);high_terms(builder,low,high)


def emit(builder,F,G,q0,q1,rhss,record_flag):
    """XOR F*P+G*Q evaluations into each low vector, preserving sources.

The caller owns the random zero-predicate masks via record_flag(slot,mask)
and repays them against the matching restored source frame. Every
RHS-dependent phase is cleared here. Exactly25 scratch bits suffice.
"""
    m=len(G)-1;assert len(F)==m+2 and all(len(r)==m+3 for r in rhss)
    witnesses=(q1,F[-1],G[-1])
    def query(slot):
        flag=builder.alloc_qubits(1);toggle_zero(builder,witnesses[slot],flag[0]);return flag
    def release(slot,flag):
        mask=builder.alloc_bits(1);builder.hmr(flag,mask);builder.free(flag);record_flag(slot,mask)
    def source_form(f,head,target):
        # target += (1+f)*q0*head; restore every source operand.
        masked=builder.alloc_qubits(12);builder.init_and(f[0],q0,masked)
        builder.cx(masked,q0);xor_product(builder,q0,head,target);builder.cx(masked,q0)
        builder.del_and(f[0],q0,masked);builder.free(masked)
    evaluate(builder,F,m);evaluate(builder,G,m)
    f=query(0);middle=query(1)
    for rhs in rhss:
        low=rhs[:m];h3,h2,h1=rhs[m:]
        source_form(f,h1,h2)
        product=builder.alloc_qubits(12);xor_product(builder,q1,h1,product)
        builder.ccx(f[0],h1,product)
        # A=middle*q1*h1. Borrow f as its missing bit: middle*f=0.
        upper=builder.alloc_qubits(11);builder.init_and(middle[0],product[1:],upper)
        builder.ccx(middle[0],product[0],f[0])
        builder.cx(upper,product[1:]);builder.ccx(middle[0],f[0],product[0])
        builder.cswap(middle[0],h1,h2)
        for point,(coefficient,target) in enumerate(zip(F[:m],low)):
            add_scaled(builder,product,h2,point);xor_product(builder,coefficient,h2,target)
            add_scaled(builder,product,h2,point)
        builder.cswap(middle[0],h1,h2)
        product_mask=builder.alloc_bits(12);builder.hmr(product,product_mask);builder.free(product)
        first=builder.alloc_qubits(1);builder.init_and(middle[0],f[0],first[0]);builder.cx(first,f)
        A=km.array(list(first)+list(upper))
        phase_product(builder,q1,h1,product_mask,kernel(12));builder.cz(product_mask,A)
        for bit in range(12):builder.ccz(product_mask[bit],f[0],h1[bit])
        builder.free(product_mask)
        # h3 temporarily holds h3+(1+f+middle)*h1.
        builder.cx(h1,h3);builder.ccx(f[0],h1,h3);builder.ccx(middle[0],h1,h3)
        release(0,f);third=query(2)
        linear_upper=builder.alloc_qubits(11)
        builder.init_and(middle[0],h2[1:],linear_upper)
        builder.cx(h1,h3);builder.ccx(third[0],h3[1:],linear_upper);builder.cx(h1,h3)
        # Missing bit B0=middle*h2[0]+third*(h3[0]+h1[0]).
        # Stage Z into A0, release third, and separate A and Z with3 ANDs.
        builder.cx(h1[0],h3[0]);builder.ccx(third[0],h3[0],A[0]);builder.cx(h1[0],h3[0])
        release(2,third)
        linear_first=builder.alloc_qubits(1);builder.init_and(middle[0],A[0],linear_first[0])
        builder.cx(linear_first[0],A[0]);builder.swap(linear_first[0],A[0])
        builder.ccx(middle[0],h2[0],linear_first[0])
        B=km.array(list(linear_first)+list(linear_upper))
        builder.cx(B,h3);builder.ccx(middle[0],h2,h3)
        for point,(coefficient,target) in enumerate(zip(G[:m],low)):
            add_scaled(builder,B,h3,point);add_scaled(builder,A,h3,km.GF2Field(12).mul(point,point))
            xor_product(builder,coefficient,h3,target)
            add_scaled(builder,A,h3,km.GF2Field(12).mul(point,point));add_scaled(builder,B,h3,point)
        builder.ccx(middle[0],h2,h3);builder.cx(B,h3)
        bmask=builder.alloc_bits(12);builder.hmr(B,bmask);builder.free(linear_upper);builder.free(linear_first)
        third=query(2)
        for bit in range(12):
            builder.ccz(bmask[bit],middle[0],h2[bit])
            builder.ccz(bmask[bit],third[0],h3[bit]);builder.ccz(bmask[bit],third[0],h1[bit])
        builder.free(bmask);release(2,third)
        amask=builder.alloc_bits(12);builder.hmr(A,amask);builder.free(upper);builder.free(first)
        masked=builder.alloc_qubits(12);builder.init_and(middle[0],q1,masked)
        phase_product(builder,masked,h1,amask,kernel(12));builder.free(amask)
        builder.del_and(middle[0],q1,masked);builder.free(masked)
        f=query(0)
        builder.ccx(middle[0],h1,h3);builder.ccx(f[0],h1,h3);builder.cx(h1,h3)
        source_form(f,h1,h2)
    release(0,f);release(1,middle)
    evaluate(builder,G,m,True);evaluate(builder,F,m,True)
