# Copyright 2026 Syed Asad Ali (team syed3000)
# SPDX-License-Identifier: Apache-2.0
"""Erase binary leading-zero-pair counts through a small thermometer basis.

For k in0..m, the m nonconstant monomials with masks1..m and the m threshold
functions [k>=j] are two linear bases of the same Boolean function space.
Only m-bit_length(m) monomials need AND gates; the other monomials are input
flags. An invertible CNOT/SWAP frame converts those wires into thresholds.

After the original input is restored, t_j=t_(j-1)*(1-a_j)*(1-b_j).
Measure thresholds top-down. Their exact measurement signs are a conditioned
CCZ for j>=2, and a conditioned CZ for j=1. This is valid for both outcomes
at every step and never assumes that an observed outcome remains absent.
"""
from __future__ import annotations

import kickmix as km


def thermometer_matrix(maximum):
    """Return the exact threshold basis in monomial coordinates1..maximum."""
    if maximum<1:
        raise ValueError('The maximum pair count must be positive.')
    size=1 << maximum.bit_length()
    rows=[]
    for threshold in range(1,maximum+1):
        values=[int(k>=threshold) for k in range(size)]
        for bit in range(maximum.bit_length()):
            for k in range(size):
                if k >> bit&1:values[k]^=values[k^(1 << bit)]
        row=sum(values[mask] << (mask-1) for mask in range(1,maximum+1))
        for k in range(maximum+1):
            value=sum((row >> (mask-1)&1)*int(k&mask==mask)
                      for mask in range(1,maximum+1))&1
            if value!=int(k>=threshold):
                raise AssertionError('A threshold basis row failed an exact valid-k check.')
        rows.append(row)
    return rows


def linear_frame(rows):
    """Compile an invertible row matrix into an exact CNOT/SWAP sequence."""
    rows=list(map(int,rows));n=len(rows);operations=[]
    if any(row<0 or row >> n for row in rows):
        raise ValueError('Linear matrix dimensions do not match.')
    for column in range(n):
        pivot=next((row for row in range(column,n) if rows[row] >> column&1),None)
        if pivot is None:raise ValueError('The threshold basis is not invertible.')
        if pivot!=column:
            rows[column],rows[pivot]=rows[pivot],rows[column]
            operations.append(('swap',column,pivot))
        for row in range(n):
            if row!=column and rows[row] >> column&1:
                rows[row]^=rows[column]
                operations.append(('cx',column,row))
    if rows != [1 << index for index in range(n)]:
        raise AssertionError('Linear matrix elimination failed.')
    return list(reversed(operations))


def binary_to_thermometer(builder,flags,maximum):
    """Consume the binary data frame, returning thresholds and owned helpers.

    Original flag wires remain allocated. The returned threshold wires are a
    permutation of those wires plus the newly allocated helper wires. The
    caller must finish the cleanup before reusing the original flag frame.
    """
    flags=list(flags)
    if len(flags)!=maximum.bit_length() or len(set(flags))!=len(flags):
        raise ValueError('Binary flag width does not match the maximum count.')
    monomials={1 << bit:wire for bit,wire in enumerate(flags)}
    helpers=[]
    for mask in range(1,maximum+1):
        if mask in monomials:continue
        bit=mask&-mask
        parent=mask^bit
        if parent not in monomials:
            raise AssertionError('Monomial computation is not topologically ordered.')
        wire=builder.alloc_qubits(1)[0]
        builder.ccx(monomials[parent],monomials[bit],wire)
        monomials[mask]=wire;helpers.append(wire)
    wires=[monomials[mask] for mask in range(1,maximum+1)]
    rows=thermometer_matrix(maximum)
    for operation,left,right in linear_frame(rows):
        if operation=='cx':builder.cx(wires[left],wires[right])
        else:builder.swap(wires[left],wires[right])
    return wires,helpers


def erase_pair_count_thermometer(builder,x,flags):
    """Reset the binary pair count, preserving its four allocated flag wires."""
    x,flags=list(x),list(flags)
    if len(x)<4 or len(x)%2:
        raise ValueError('Pair normalization needs a positive even input width.')
    maximum=(len(x)-2)//2
    if len(set(x+flags))!=len(x)+len(flags):
        raise ValueError('Input and count wires must be distinct.')
    thermometer,helpers=binary_to_thermometer(builder,flags,maximum)
    for index in reversed(range(maximum)):
        wire=thermometer[index]
        outcome=builder.alloc_bits(1)[0]
        builder.hmr(wire,outcome)
        a,b=x[-2*index-1],x[-2*index-2]
        if not index:
            # (1-a)(1-b)=1+a+b+ab over GF(2); keep its branch
            # constant phase, which is observable in an exact branch proof.
            builder.z(outcome)
        builder.push_condition(outcome)
        if index:
            previous=thermometer[index-1]
            builder.z(previous)
            builder.cz(previous,a)
            builder.cz(previous,b)
            builder.ccz(previous,a,b)
        else:
            builder.z(a);builder.z(b)
            builder.cz(a,b)
        builder.pop_condition()
        builder.free(outcome)
    builder.free(km.array(helpers))
    return dict(and_count=maximum-len(flags),conditioned_ccz_count=maximum-1,
                 expected_toffolis=maximum-len(flags)+(maximum-1)/2,
                 temporary_qubits=len(helpers),threshold_count=maximum,
                 exact_for_all_measurement_outcomes=True)
