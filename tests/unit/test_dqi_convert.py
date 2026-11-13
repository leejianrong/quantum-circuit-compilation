"""The amplitude polynomial reproduces the error values at the roots (weights 19 to 35, padded chain)."""

import random

import pytest

pytest.importorskip("kickmix")

from dqi_gen import convert  # noqa: E402
from dqi_gen import thiele as T  # noqa: E402


def _chain(word: dict[int, int]) -> tuple[list[int], list[int]]:
    gf = T.field()
    ks = T.kappas(gf)
    res = T.residues(gf, T.residue_polynomial(gf, T.syndromes_of(gf, word)))
    heads, w = T.extract(gf, res)
    full = list(heads) + [(0, 0)] * (35 - w)
    n, d = ([1], []) if (35 - w) % 2 else ([], [1])
    for i in reversed(range(35)):
        n, d = d, T.padd(T.pmul(gf, [ks[i], 1, 1], n), T.pmul(gf, T.trim(list(full[i])), d))
    return T.trim(n), T.trim(d)


@pytest.mark.parametrize("weight", [35, 34, 29, 24, 19])
def test_amplitude_polynomial(weight: int) -> None:
    gf = T.field()
    rng = random.Random(weight)
    word = {j: rng.randint(1, 4095) for j in rng.sample(range(4095), weight)}
    n, d = _chain(word)
    c = convert.amplitude_polynomial(gf, n, d)
    assert len(c) <= len(d) - 1
    alpha = gf.primitive_element
    for j, e in word.items():
        assert convert.error_value(gf, c, int(gf.pow(alpha, j))) == e
    assert convert.admitted(gf, d)
