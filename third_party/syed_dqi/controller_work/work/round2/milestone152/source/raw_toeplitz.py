# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""Triangular Toeplitz map with a preserved unit quantum diagonal.

The supplied reciprocal remains live throughout this recursion. Each leaf
uses the established locally phase-clean scale; no RHS mask debt escapes.
"""
from monic_forney import scale
from unit_toeplitz import cross

def emit(builder,coefficients,vector,diagonal,reciprocal,inverse=False):
    if not vector:return
    if len(vector)==1:
        scale(builder,vector,diagonal,reciprocal,inverse);return
    mid=len(vector)//2
    if inverse:
        emit(builder,coefficients,vector[:mid],diagonal,reciprocal,True)
        cross(builder,coefficients,vector)
        emit(builder,coefficients,vector[mid:],diagonal,reciprocal,True)
    else:
        emit(builder,coefficients,vector[mid:],diagonal,reciprocal)
        cross(builder,coefficients,vector)
        emit(builder,coefficients,vector[:mid],diagonal,reciprocal)
