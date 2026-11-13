"""Scan stage with a per-position division: phase `<mask_j, e_j>` from `(N, D)` (QCC-19, E041).

For every scanned position `j` (`a = alpha^j`), with the registers `N` (35 words) and `D` (36 words)
held in place:
the root flag `z = [D(a) == 0]` (a 12-bit zero test), `od = a D'(a)` (the odd-degree words summed), `om
= N(a) / M(a)`
(`M` the public degree-70 modulus, `M(a)` a constant per position), and the phase `<mask_j, om / od>`
gated by `z` by
the GF(2^6) tower division of `bm.BMDecoder` (about 96 Toffolis per position). The error value is
`e = N(a) / (a M(a) D'(a)) = om / od` (`thiele.amplitude`).

The coefficient words are rotated in place between positions (word `k` times `alpha^k`, constant
multiplications, i.e.
CNOT networks) and rotated back at the end. This is the plain scan; the amplitude-polynomial scan (11
Toffolis per
position) needs the convert stage.
"""

from __future__ import annotations

from typing import Any

import kickmix as km  # type: ignore[import-not-found,unused-ignore]

from dqi_gen import thiele as T
from dqi_gen.bm import BMDecoder
from dqi_gen.tower import Tower, apply_matrix_inplace, xor_linear


def _fanin(builder: Any, words: list[list[Any]], target: Any, which: list[int] | None = None) -> None:
    for k, w in enumerate(words):
        if which is None or k in which:
            builder.cx(km.array(w), target)


def scan(
    builder: Any,
    n_words: list[list[Any]],
    d_words: list[list[Any]],
    masks: list[Any],
    positions: list[int],
) -> None:
    """Scan `positions` (the K-positions `j`, `a = alpha^j`), `masks[j]` the 12 classical bits of
    position `j`."""
    gf = T.field()
    dec = BMDecoder(2, gf)
    deg = 12
    h = deg // 2
    alpha = int(gf.primitive_element)
    gf_h = km.GF2Field(h)
    tw = Tower.build(gf, gf_h)
    norm_b = [gf_h.mul(tw.b, gf_h.square(1 << i)) for i in range(h)]
    inv_compute, inv_uncompute = dec._subfield_inverse(builder, gf_h, True)
    mul = dec._mul
    modulus = T.modulus(gf)
    odd = [k for k in range(len(d_words)) if k % 2 == 1]

    def division(od: Any, om: Any, z: Any, mask: Any) -> None:
        apply_matrix_inplace(builder, list(od), tw.to_tower)
        a_, b_ = od[:h], od[h:]
        norm = mul(builder, a_, b_, gf_h, fast=True)
        xor_linear(builder, a_, norm, tw.square)
        xor_linear(builder, b_, norm, norm_b)
        ninv, state = inv_compute(norm)
        gated = builder.alloc_qubits(h)
        builder.init_and(z, ninv, gated)
        builder.cx(b_, a_)
        e_ = a_
        rhs = builder.alloc_qubits(deg)
        mul(builder, e_, gated, gf_h, rhs[:h], True)
        mul(builder, b_, gated, gf_h, rhs[h:], True)
        apply_matrix_inplace(builder, list(rhs), tw.from_tower)
        builder.gf2_phase_by_product(om, rhs, mask=mask, field=gf)
        apply_matrix_inplace(builder, list(rhs), tw.to_tower)
        builder.del_gf2_mul(b_, gated, target=rhs[h:], field=gf_h)
        builder.del_gf2_mul(e_, gated, target=rhs[:h], field=gf_h)
        builder.free(rhs)
        builder.cx(b_, a_)
        builder.del_and(z, ninv, gated)
        builder.free(gated)
        inv_uncompute(norm, ninv, state)
        xor_linear(builder, b_, norm, norm_b)
        xor_linear(builder, a_, norm, tw.square)
        builder.del_gf2_mul(a_, b_, target=norm, field=gf_h)
        builder.free(norm)
        apply_matrix_inplace(builder, list(od), tw.from_tower)

    words = [(w, k) for k, w in enumerate(n_words)] + [(w, k) for k, w in enumerate(d_words)]
    prev = 0
    for j in positions:
        step = j - prev
        if step:  # rotate every word k by alpha^(k * step)
            for w, k in words:
                c = int(gf.pow(alpha, (k * step) % 4095))
                if c != 1:
                    builder.gf2_imul(c, target=km.array(w), field=gf)
            prev = j
        a = int(gf.pow(alpha, j))
        sg = builder.alloc_qubits(deg)
        _fanin(builder, d_words, sg)
        ladder = BMDecoder._zero_test(builder, sg)
        z = ladder[-1]
        builder.x(sg)
        _fanin(builder, d_words, sg)  # clear sg while the division runs
        builder.free(sg)
        od = builder.alloc_qubits(deg)
        _fanin(builder, d_words, od, odd)
        om = builder.alloc_qubits(deg)
        _fanin(builder, n_words, om)
        c_m = int(gf.invert(T.peval(gf, modulus, a)))
        builder.gf2_imul(c_m, target=om, field=gf)
        division(od, om, z, masks[j])
        builder.gf2_idiv(c_m, target=om, field=gf)
        _fanin(builder, n_words, om)
        builder.free(om)
        _fanin(builder, d_words, od, odd)
        builder.free(od)
        sg = builder.alloc_qubits(deg)
        _fanin(builder, d_words, sg)
        builder.x(sg)
        BMDecoder._zero_untest(builder, sg, ladder)
        _fanin(builder, d_words, sg)
        builder.free(sg)
    if prev:  # rotate back
        for w, k in words:
            c = int(gf.pow(alpha, (-k * prev) % 4095))
            if c != 1:
                builder.gf2_imul(c, target=km.array(w), field=gf)
