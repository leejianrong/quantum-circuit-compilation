"""The constant-time Bezout of the half-degree pair gives 1 / sigma' at every root of the locator."""

import random

import kickmix as km  # type: ignore[import-not-found,unused-ignore]

from dqi_gen import bezout


def test_reciprocal_at_roots_and_row_windows() -> None:
    gf = km.GF2Field(12)
    rng = random.Random(2)
    for weight in (1, 2, 9, 20, 34, 35):
        xs = rng.sample(range(1, 4096), weight)  # sigma = prod (1 + x z), roots beta = 1 / x
        sigma = [1]
        for x in xs:
            sigma = bezout.padd(sigma + [0], [0] + bezout.pscale(gf, x, sigma))
        e, o = bezout.halves(gf, sigma)
        uf, vf, steps = bezout.bezout_rows(gf, e, o)
        assert steps == 36
        assert not any(uf[:2]) and not any(vf[:2])  # nonzero coefficients start at index 2
        assert all(c == 0 for c in uf[19:]) and all(c == 0 for c in vf[20:])
        for x in xs:
            beta = gf.invert(x)
            dp = bezout.peval(gf, o, beta)
            assert bezout.reciprocal_at(gf, sigma, x) == gf.invert(gf.mul(dp, dp))
