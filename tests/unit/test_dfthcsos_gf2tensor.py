import numpy as np

from dfthcsos_gen import gf2tensor as gt


def _table(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 2, size=(6, 9, 5)).astype(np.uint8)


def test_center_and_both_starts_are_exact() -> None:
    tab = _table()
    f, g, tc = gt.center(tab)
    assert ((f[:, :, None] ^ g[:, None, :] ^ tc) == tab).all()
    tc = tc[:, 1:, 1:]
    for terms in (gt.initial_terms(tc), gt.plane_terms(tc)):
        assert (gt.expand(terms, *tc.shape) == tc).all()


def test_flip_walk_and_anneal_keep_the_tensor_exact_and_never_lose_the_best() -> None:
    tab = _table(1)
    tc = gt.center(tab)[2][:, 1:, 1:]
    terms = gt.plane_terms(tc)
    walk = gt.FlipWalk(terms, seed=3)
    start = walk.cost
    best = gt.anneal(walk, 3000, temp=0.1)
    assert (gt.expand(walk.terms, *tc.shape) == tc).all()
    assert (gt.expand(best, *tc.shape) == tc).all()
    assert gt.pair_cost(best) <= start
    assert walk.cost == gt.pair_cost(walk.terms)
