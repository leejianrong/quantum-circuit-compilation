# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""Field transpose of the raw three-border evaluation tensor.

Only a development candidate until its complete caller is measured. The
one-bit m+t bridge records correlated random masks in both source ledgers.
"""
import kickmix as km
from raw_window_tensor import evaluate
from monic_forney import add_scaled
from coherent_border import toggle_zero
from tower_inverse import xor_product,phase_product,kernel
FIELD=km.GF2Field(12)

def emit(builder,F,G,q0,q1,rhss,record_flag):
    m=len(G)-1;witnesses=(q1,F[-1],G[-1])
    def query(slot):
        flag=builder.alloc_qubits(1);toggle_zero(builder,witnesses[slot],flag[0]);return flag
    def release(slot,flag):
        mask=builder.alloc_bits(1);builder.hmr(flag,mask);builder.free(flag);record_flag(slot,mask)
    def phase_moment(moment,coefficients,low,power):
        mask=builder.alloc_bits(12);builder.hmr(moment,mask);builder.free(moment)
        for point,(c,y) in enumerate(zip(coefficients,low)):
            factor=FIELD.pow(point,power)
            if factor:phase_product(builder,c,y,mask,tuple((a,b,FIELD.mul(out,factor)) for a,b,out in kernel(12)))
        builder.free(mask)
    def source_form(h2,h1):
        f=query(0);masked=builder.alloc_qubits(12);builder.init_and(f[0],q0,masked)
        builder.cx(masked,q0);xor_product(builder,q0,h2,h1);builder.cx(masked,q0)
        builder.del_and(f[0],q0,masked);builder.free(masked);release(0,f)
    evaluate(builder,F,m);evaluate(builder,G,m)
    for rhs in rhss:
        low=rhs[:m];h3,h2,h1=rhs[m:]
        source_form(h2,h1)
        middle=query(1)
        x0=builder.alloc_qubits(12);x1=builder.alloc_qubits(12)
        for point,(c,y) in enumerate(zip(F[:m],low)):
            add_scaled(builder,x0,x1,point);xor_product(builder,c,y,x0);add_scaled(builder,x0,x1,point)
        builder.cx(x0,h2);builder.ccx(middle[0],x0,h1);builder.ccx(middle[0],x0,h2)
        phase_moment(x0,F[:m],low,0)
        masked=builder.alloc_qubits(12);builder.init_and(middle[0],q1,masked)
        builder.cx(masked,q1);xor_product(builder,q1,x1,h1);builder.cx(masked,q1)
        builder.del_and(middle[0],q1,masked);builder.free(masked);release(1,middle)
        f=query(0);builder.ccx(f[0],x1,h1);release(0,f)
        phase_moment(x1,F[:m],low,1)
        # P routes the Y0 direction to h3. A further middle swap routes
        # either m*Y1 or t*Y1 into the same h1 coordinate.
        middle=query(1);third=query(2);f=query(0)
        builder.cswap(third[0],h1,h3)
        builder.cx(h3,h1);builder.ccx(f[0],h3,h1)
        builder.ccx(middle[0],h3,h1);builder.ccx(third[0],h3,h1)
        release(0,f);builder.cswap(middle[0],h1,h2)
        builder.cx(middle,third);release(1,middle) # third is now k=m+t.
        y1=builder.alloc_qubits(12);y2=builder.alloc_qubits(12)
        for point,(c,y) in enumerate(zip(G[:m],low)):
            square=FIELD.mul(point,point)
            add_scaled(builder,h3,y1,point);add_scaled(builder,h3,y2,square)
            xor_product(builder,c,y,h3)
            add_scaled(builder,h3,y2,square);add_scaled(builder,h3,y1,point)
        builder.ccx(third[0],y1,h1)
        phase_moment(y1,G[:m],low,1)
        shared=builder.alloc_bits(1);builder.hmr(third,shared);builder.free(third)
        duplicate=builder.alloc_bits(1);builder.bit_store(duplicate,False);builder.cx(shared,duplicate)
        record_flag(1,shared);record_flag(2,duplicate)
        middle=query(1);masked=builder.alloc_qubits(12);builder.init_and(middle[0],q1,masked)
        xor_product(builder,masked,y2,h2)
        builder.del_and(middle[0],q1,masked);builder.free(masked)
        builder.cswap(middle[0],h1,h2);release(1,middle)
        phase_moment(y2,G[:m],low,2)
        # Undo P now that both moment words are gone.
        middle=query(1);f=query(0);third=query(2)
        builder.ccx(third[0],h3,h1);builder.ccx(middle[0],h3,h1)
        builder.ccx(f[0],h3,h1);builder.cx(h3,h1)
        builder.cswap(third[0],h1,h3)
        release(2,third);release(0,f);release(1,middle)
        source_form(h2,h1)
    evaluate(builder,G,m,True);evaluate(builder,F,m,True)
