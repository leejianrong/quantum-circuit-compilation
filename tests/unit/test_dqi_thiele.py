"""The quadratic-node model: syndromes -> residues -> rational reconstruction -> error values."""

import random

from dqi_gen import thiele as T


def _gcd(gf, a, b):  # type: ignore[no-untyped-def]
    a, b = T.trim(a), T.trim(b)
    while b:
        a, b = b, T.pdivmod(gf, a, b)[1]
    return a


def test_residues_are_values_of_one_rational_function() -> None:
    gf = T.field()
    rng = random.Random(3)
    ks = T.kappas(gf)
    assert len(set(ks)) == 35 and all(T.trace(gf, c) == 1 for c in ks)
    for weight in (1, 5, 20, 35):
        pos = rng.sample(range(4095), weight)
        word = {j: rng.randint(1, 4095) for j in pos}
        s = T.syndromes_of(gf, word)
        p = T.residue_polynomial(gf, s)
        n, d = T.reconstruct(gf, p)
        g = _gcd(gf, n, d)
        n, d = T.pdivmod(gf, n, g)[0], T.pdivmod(gf, d, g)[0]
        assert len(d) - 1 == weight
        alpha = gf.primitive_element
        for j, e in word.items():
            a = int(gf.pow(alpha, j))
            assert T.peval(gf, d, a) == 0
            assert T.amplitude(gf, n, d, a) == e
        # D P + N vanishes modulo every quadratic: the residues are the values of N / D at the nodes
        total = T.padd(T.pmul(gf, d, p), n)
        for r in T.residues(gf, total):
            assert r == (0, 0)


def test_extract_and_synthesize_recover_the_rational_function() -> None:
    gf = T.field()
    rng = random.Random(8)
    for weight in (1, 3, 19, 28, 35):
        pos = rng.sample(range(4095), weight)
        word = {j: rng.randint(1, 4095) for j in pos}
        p = T.residue_polynomial(gf, T.syndromes_of(gf, word))
        heads, w = T.extract(gf, T.residues(gf, p))
        assert w == weight
        n, d = T.synthesize(gf, heads)
        alpha = gf.primitive_element
        for j, e in word.items():
            a = int(gf.pow(alpha, j))
            assert T.peval(gf, d, a) == 0
            assert T.amplitude(gf, n, d, a) == e
