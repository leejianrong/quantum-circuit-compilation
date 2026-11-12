"""Jacobi solver: Gauss weights recover the errors, the pair carries (a, b), S_{k-1} erases."""

import random

import pytest

from dqi_gen import jacobi

GF = jacobi.field(8)
ORDER = 255
T = 6


def _case(seed: int, weight: int) -> tuple[dict[int, int], list[int]]:
    rng = random.Random(seed)
    pos = rng.sample(range(ORDER), weight)
    vals = {j: rng.randrange(1, 256) for j in pos}
    return vals, jacobi.syndromes(GF, vals, 2 * T)


def _generic_cases() -> list[tuple[dict[int, int], list[int]]]:
    out = []
    for seed in range(200):
        vals, s = _case(seed, 1 + seed % T)
        sol = jacobi.solve(GF, s, T)
        if sol.stopped_at == len(vals) and sol.erase_ok:
            out.append((vals, s))
    return out


def test_most_random_cases_are_generic() -> None:
    assert len(_generic_cases()) > 150


@pytest.mark.parametrize("idx", range(0, 150, 15))
def test_gauss_weights_recover_the_errors(idx: int) -> None:
    vals, s = _generic_cases()[idx]
    sol = jacobi.solve(GF, s, T)
    alpha = GF.primitive_element
    roots = [j for j in range(ORDER) if jacobi.poly_eval(GF, sol.p, GF.pow(alpha, j)) == 0]
    assert sorted(roots) == sorted(vals)
    for j, e in vals.items():
        x = GF.pow(alpha, j)
        assert GF.mul(jacobi.gauss_weight(GF, sol, x), GF.pow(alpha, (-j) % ORDER)) == e


@pytest.mark.parametrize("idx", range(0, 150, 25))
def test_pair_carries_the_recurrence_parameters(idx: int) -> None:
    _, s = _generic_cases()[idx]
    p, pp, hp = [1], [], 0
    for k in range(T - 1):
        h = jacobi._dot(GF, p, s, k)
        if h == 0:
            break
        a = GF.mul(jacobi._dot(GF, p, s, k + 1), GF.invert(h)) ^ (p[k - 1] if k else 0)
        b = GF.mul(h, GF.invert(hp)) if k else 0
        new = [0] * (k + 2)
        for i, c in enumerate(p):
            new[i + 1] ^= c
            new[i] ^= GF.mul(a, c)
        for i, c in enumerate(pp):
            new[i] ^= GF.mul(b, c)
        if k >= 1:
            ra, rb, q = jacobi.peel(GF, new, p)
            assert (ra, rb, q) == (a, b, pp)
        pp, p, hp = p, new, h


@pytest.mark.parametrize("idx", range(0, 150, 25))
def test_s_km1_erases_from_pk(idx: int) -> None:
    _, s = _generic_cases()[idx]
    p = [1]
    pp: list[int] = []
    hp = 0
    for k in range(T):
        h = jacobi._dot(GF, p, s, k)
        if h == 0:
            break
        if k >= 1:
            assert jacobi.erase_value(GF, p, s, k) == s[k - 1]
        a = GF.mul(jacobi._dot(GF, p, s, k + 1), GF.invert(h)) ^ (p[k - 1] if k else 0)
        b = GF.mul(h, GF.invert(hp)) if k else 0
        new = [0] * (k + 2)
        for i, c in enumerate(p):
            new[i + 1] ^= c
            new[i] ^= GF.mul(a, c)
        for i, c in enumerate(pp):
            new[i] ^= GF.mul(b, c)
        pp, p, hp = p, new, h
