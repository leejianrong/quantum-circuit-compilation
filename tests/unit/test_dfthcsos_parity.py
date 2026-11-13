import random

from dfthcsos_gen.parity import gf2_basis, parity_rank, perfect_matching


def _planted(dim: int, decoys: int, seed: int) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    while True:
        vecs = [rng.getrandbits(dim) for _ in range(dim)]
        if len(gf2_basis(vecs)) == dim:
            break
    pairs = [(vecs[2 * i], vecs[2 * i + 1]) for i in range(dim // 2)]
    for _ in range(decoys):  # pairs of dependent-looking vectors that cannot all be used
        x = rng.choice(vecs)
        pairs.append((x, x ^ rng.choice(vecs)))
    rng.shuffle(pairs)
    return pairs


def test_perfect_matching_is_a_basis_and_the_rank_certificate_agrees() -> None:
    for dim, seed in ((12, 0), (24, 1), (30, 2)):
        pairs = _planted(dim, 3 * dim, seed)
        rank, span = parity_rank(pairs)
        assert span == dim and rank == dim
        chosen = perfect_matching(pairs, seed=5)
        assert chosen is not None and len(chosen) == dim // 2
        vecs = [v for i in chosen for v in pairs[i]]
        assert len(gf2_basis(vecs)) == dim


def test_no_perfect_matching_when_every_pair_repeats_a_vector() -> None:
    a, b, c, d = 1, 2, 4, 8
    pairs = [(a, b), (a, c), (a, d)]  # all share a: at most one pair is independent
    rank, span = parity_rank(pairs)
    assert span == 4 and rank == 2 and perfect_matching(pairs) is None
