# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""27-T classical-mask GF4096 inverse phase, with 13 clean scratch.

Original circuit code from the supplied code-free GF4096_PHASE27_RECIPE53.
The polynomial core preserves z and a CLASSICAL mask m and applies
(-1)**dot(m,inv0(z)) in the official 0x1053 polynomial field. The public
tower-mask adapter matches compact_inverse.phase_inverse_twelve.
No quantum-numerator or quantum-mask interface is implied.
"""
from functools import cache
import kickmix as km
from field_tensor import (apply_linear,invert_binary_columns,parity_pivot,
                          accumulate_product)
from quantum_reciprocal import xor_linear,xor_same_source_product
from tower_inverse import (apply_inplace_linear,rows_from_columns,
                           quadratic_basis,kernel,xor_product,phase_product,
                           phase_linear)

FIELD=km.GF2Field(12)
SMALL=km.GF2Field(4)
JOINT_GATES=((3,48),(13,208),(14,224),(28,205),(31,225),(52,71),
             (40,138),(46,194),(77,148),(91,190),(127,135),(120,143),(121,158))
JOINT_OUTPUTS=((8,2383),(27,4535),(20,7604),(7,6094),
               (1,5274),(154,554),(69,2108),(247,4115))
LEAF_GATES=((2,13),(4,21),(50,57),(10,111),(1,119))
LEAF_OUTPUTS=(43,281,162,244)
GRAM_ROWS=(8,4,2,9)


def _combine(items,mask):
    result=0
    for j,value in enumerate(items):
        if mask>>j&1:result^=value
    return result


def _trace(value):
    result=0
    for _ in range(12):result^=value;value=FIELD.mul(value,value)
    assert result in (0,1)
    return result


@cache
def trace_dual_columns():
    columns=tuple(sum(_trace(FIELD.mul(1<<j,1<<k))<<k for k in range(12)) for j in range(12))
    inverse_rows=invert_binary_columns(columns)
    return tuple(apply_linear(inverse_rows,1<<j) for j in range(12))


@cache
def cubic_basis():
    assert FIELD.modulus==0x1053 and SMALL.modulus==0x13
    beta,theta=1970,937
    assert FIELD.pow(beta,4)^beta^1==0 and FIELD.pow(theta,3)^theta^1==0
    columns=tuple(FIELD.mul(FIELD.pow(theta,i),FIELD.pow(beta,j)) for i in range(3) for j in range(4))
    return dict(columns=columns,to_cubic=invert_binary_columns(columns),from_cubic=rows_from_columns(columns))


@cache
def gf16_kernel():
    """Nine products from the supplied quadratic-over-GF4 Karatsuba recipe."""
    columns=(1,6,2,SMALL.mul(6,2))
    rows=invert_binary_columns(columns)
    assert SMALL.mul(6,6)^6^1==0 and SMALL.mul(2,2)^2==6
    gf4_terms=((1,1,3),(2,2,1),(3,3,2))
    terms=[]
    # t0 contributes (1+tau)*t0; t1 contributes beta4*t1; t2 tau*t2.
    for forms,weight in ((rows[:2],3),(rows[2:],6),
                         ((rows[0]^rows[2],rows[1]^rows[3]),2)):
        for left,right,output in gf4_terms:
            embedded=(output&1)^(6 if output&2 else 0)
            terms.append((_combine(forms,left),_combine(forms,right),SMALL.mul(weight,embedded)))
    assert len(terms)==9
    return tuple(terms)


def _independent(rows):
    pivots={}
    for value in rows:
        while value:
            bit=value.bit_length()-1
            if bit not in pivots:pivots[bit]=value;break
            value^=pivots[bit]
        if not value:return False
    return True


@cache
def _operand_basis(width,left,right):
    rows=[left,right];assert _independent(rows)
    for j in range(width):
        if _independent(rows+[1<<j]):rows.append(1<<j)
    assert len(rows)==width
    return tuple(rows),invert_binary_columns(rows_from_columns(rows))


def _view_pair(builder,signals,left,right):
    rows,undo=_operand_basis(len(signals),left,right)
    view=km.array(signals);apply_inplace_linear(builder,view,rows)
    return view,undo


def _joint_terms():
    return tuple((left,right,sum(((mask>>j)&1)<<out for out,(_,mask) in enumerate(JOINT_OUTPUTS)))
                 for j,(left,right) in enumerate(JOINT_GATES))


def _joint_init(builder,bc,B,C):
    target=km.array([*B,*C])
    xor_same_source_product(builder,bc,target,_joint_terms())
    for output,(linear,_) in enumerate(JOINT_OUTPUTS):
        for bit,source in enumerate(bc):
            if linear>>bit&1:builder.cx(source,target[output])


def _joint_phase(builder,bc,mask,offset):
    """Repay a selected four-bit half of the joint map at zero T."""
    for output,(linear,_) in enumerate(JOINT_OUTPUTS[offset:offset+4]):
        for bit,source in enumerate(bc):
            if linear>>bit&1:builder.cz(mask[output],source)
    for left,right,output in _joint_terms():
        weight=(output>>offset)&15
        if not weight:continue
        view,undo=_view_pair(builder,list(bc),left,right)
        selected=parity_pivot(builder,mask,weight)
        builder.ccz(selected,view[0],view[1])
        parity_pivot(builder,mask,weight)
        apply_inplace_linear(builder,view,undo)


def _leaf_phase(builder,C,B):
    """Phase by Tr(B/C), retaining five leaf ANDs until their HMR erasure."""
    apply_inplace_linear(builder,B,GRAM_ROWS)
    signals=list(C);records=[]
    for left,right in LEAF_GATES:
        view,undo=_view_pair(builder,signals,left,right)
        target=builder.alloc_qubits(1);builder.init_and(view[0],view[1],target[0])
        apply_inplace_linear(builder,view,undo)
        records.append((tuple(signals),left,right,target));signals.append(target[0])
    for bit,form in enumerate(LEAF_OUTPUTS):
        for j,signal in enumerate(signals):
            if form>>j&1:builder.cz(B[bit],signal)
    for parents,left,right,target in reversed(records):
        view,undo=_view_pair(builder,parents,left,right)
        builder.del_and(view[0],view[1],target[0]);builder.free(target)
        apply_inplace_linear(builder,view,undo)
    apply_inplace_linear(builder,B,invert_binary_columns(rows_from_columns(GRAM_ROWS)))


def fixed_inverse_trace(builder,source):
    """Apply Tr(inv0(source)) in 27 T, preserving source, with 13 scratch."""
    assert len(source)==12
    info=cubic_basis();apply_inplace_linear(builder,source,info['to_cubic'])
    a,b,c=source[:4],source[4:8],source[8:];bc=source[4:]
    B=builder.alloc_qubits(4);C=builder.alloc_qubits(4)
    _joint_init(builder,bc,B,C)
    squares=tuple(SMALL.mul(1<<j,1<<j) for j in range(4))
    for word in (a,b,c):xor_linear(builder,word,B,squares)
    accumulate_product(builder,a,B,C,gf16_kernel())
    _leaf_phase(builder,C,B)
    # C must be repaid while B is still available.
    measured=builder.alloc_bits(4);builder.hmr(C,measured)
    phase_product(builder,a,B,measured,gf16_kernel());_joint_phase(builder,bc,measured,4)
    builder.free(measured);builder.free(C)
    measured=builder.alloc_bits(4);builder.hmr(B,measured)
    for word in (a,b,c):phase_linear(builder,word,measured,squares)
    _joint_phase(builder,bc,measured,0)
    builder.free(measured);builder.free(B)
    apply_inplace_linear(builder,source,info['from_cubic'])


def _classical_word(builder,width=12):
    word=builder.alloc_bits(width);builder.bit_store(word,False);return word


def _classical_inverse(builder,source):
    """Existing field arithmetic lowered with classical conditions only."""
    value=source;owned=[]
    squares=tuple(FIELD.mul(1<<j,1<<j) for j in range(12))
    for bit in bin(4094)[3:]:
        squared=_classical_word(builder);owned.append(squared)
        xor_linear(builder,value,squared,squares);value=squared
        if bit=='1':
            product=_classical_word(builder);owned.append(product)
            for a,b,output in kernel(12):
                first=parity_pivot(builder,value,a);second=parity_pivot(builder,source,b)
                builder.push_condition(first)
                builder.cx(second,km.array([product[j] for j in range(12) if output>>j&1]))
                builder.pop_condition()
                parity_pivot(builder,source,b);parity_pivot(builder,value,a)
            value=product
    return value,owned


def _classical_scale(builder,source,multiplier,inverse_multiplier):
    temporary=builder.alloc_qubits(12)
    xor_product(builder,source,multiplier,temporary);builder.swap(source,temporary)
    xor_product(builder,source,inverse_multiplier,temporary);builder.free(temporary)


def phase_inverse_twelve_polynomial(builder,source,mask):
    """Preserve source and classical polynomial mask; phase dot(mask,inv0).

    Exactly 27 T for a nonzero mask and zero T for a zero mask. The static
    circuit contains 27 T. Only for a fresh uniform 12-bit HMR mask is its
    exact expected count 27*(4095/4096). Peak quantum scratch is 13.
    """
    assert len(source)==len(mask)==12
    alpha=_classical_word(builder);xor_linear(builder,mask,alpha,trace_dual_columns())
    reciprocal,owned=_classical_inverse(builder,alpha)
    active=_classical_word(builder,1);builder.bit_store(active[0],True,control=alpha)
    builder.push_condition(active[0])
    _classical_scale(builder,source,reciprocal,alpha)
    fixed_inverse_trace(builder,source)
    _classical_scale(builder,source,alpha,reciprocal)
    builder.pop_condition()
    for word in owned:builder.free(word)
    builder.free(active);builder.free(alpha)


def phase_inverse_twelve(builder,source,mask_in_tower_basis):
    """Compatible legacy adapter: inverse is measured in quadratic tower basis."""
    assert len(source)==len(mask_in_tower_basis)==12
    mask=_classical_word(builder)
    # t=L*p implies m_tower dot t = (L^T*m_tower) dot p.
    xor_linear(builder,mask_in_tower_basis,mask,quadratic_basis(12)['to_tower'])
    phase_inverse_twelve_polynomial(builder,source,mask)
    builder.free(mask)
