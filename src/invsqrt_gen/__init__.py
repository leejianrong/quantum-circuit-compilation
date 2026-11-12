"""Our own invsqrt circuit generator (QCC-12, ADR-0009 stage 1).

Table lookup of the top bits, a low-degree polynomial in the remaining bits by Horner's rule in
truncated fixed point, binary-coded normalisation and de-normalisation shifts, phase by `Z_POW` per
bit, and a mirrored uncompute. Built from the benchmark paper and standard numerics only.
"""
