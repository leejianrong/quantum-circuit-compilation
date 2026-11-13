# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Root-mask phase using ten clean qubits and a restored classical parity view.

This contains no degree/count controller. Inputs are the same physical
fixed-degree scan chart as inplace_scan_gauge135. The point cell preserves
all quantum inputs and the classical mask and has T=10+[mask!=0].
"""
from narrow_field130 import _selected_parity_ccz
from quantum_reciprocal import xor_linear
from inplace_scan import known_reweight, fixed_scale


def point_cell(builder, locator_value, value, mask, ladder):
    assert len(locator_value)==len(value)==len(mask)==12 and len(ladder)==10
    builder.x(locator_value)
    builder.init_and(locator_value[0],locator_value[1],ladder[0])
    for i in range(1,10):
        builder.init_and(ladder[i-1],locator_value[i+1],ladder[i])
    _selected_parity_ccz(builder,ladder[-1],locator_value[11],[value],mask)
    for i in reversed(range(1,10)):
        builder.del_and(ladder[i-1],locator_value[i+1],ladder[i])
    builder.del_and(locator_value[0],locator_value[1],ladder[0])
    builder.x(locator_value)


def emit(builder,locator,values,masks,field,nodes=(),leading=None,skip_points=()):
    degree=len(locator)
    assert field.degree==12 and degree==len(values) and len(masks)==4095
    skipped=frozenset(skip_points)
    assert all(0<x<4096 for x in skipped)
    ladder=builder.alloc_qubits(10)
    previous=[1]+[0]*degree
    def move(point):
        nonlocal previous
        powers=[1]
        for _ in range(degree):powers.append(field.mul(powers[-1],point))
        for i in range(1,degree):
            coefficient=powers[i]^previous[i]
            columns=tuple(field.mul(coefficient,1<<bit) for bit in range(12))
            xor_linear(builder,locator[i],locator[0],columns)
            xor_linear(builder,values[i],values[0],columns)
        coefficient=powers[degree]^previous[degree]
        if leading is None:
            for bit in range(12):
                if coefficient>>bit&1:builder.x(locator[0][bit])
        else:
            columns=tuple(field.mul(coefficient,1<<bit) for bit in range(12))
            xor_linear(builder,leading,locator[0],columns)
        previous=powers
    point=1
    for mask in masks:
        move(point)
        if point not in skipped:
            factor=known_reweight(point,field,nodes) if nodes else 1
            fixed_scale(builder,values[0],factor,field)
            point_cell(builder,locator[0],values[0],mask,ladder)
            fixed_scale(builder,values[0],field.invert(factor),field)
        point=field.mul(point,field.primitive_element)
    assert point==1
    move(0)
    builder.free(ladder)
