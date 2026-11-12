"""The GF(2^2h) tower identities behind the Forney division hold (pure field arithmetic, no data needed)."""

import random

import kickmix as km  # type: ignore[import-not-found,unused-ignore]
import pytest

from dqi_gen.tower import Tower, _apply, _invert


@pytest.mark.parametrize("h", [2, 3, 4, 5, 6])
def test_norm_conjugate_and_karatsuba_identities(h: int) -> None:
    gf, sub = km.GF2Field(2 * h), km.GF2Field(h)
    tw = Tower.build(gf, sub)
    mask = (1 << h) - 1
    rng = random.Random(h)
    for _ in range(300):
        a = rng.randint(1, (1 << (2 * h)) - 1)
        co = _apply(tw.to_tower, a)
        a_, b_ = co & mask, co >> h
        assert _apply(tw.from_tower, co) == a
        norm = sub.add(sub.add(sub.square(a_), sub.mul(a_, b_)), sub.mul(tw.b, sub.square(b_)))
        conj = _apply(tw.from_tower, (a_ ^ b_) | (b_ << h))
        assert gf.mul(a, conj) == _apply(tw.embed, norm)  # a * conj(a) is the norm, in the subfield
        inv = gf.mul(conj, _apply(tw.embed, sub.invert(norm)))
        assert gf.mul(a, inv) == 1


def test_matrix_inverse_round_trip() -> None:
    cols = [0b0001, 0b0011, 0b0111, 0b1111]
    inv = _invert(cols)
    for x in range(16):
        assert _apply(inv, _apply(cols, x)) == x
