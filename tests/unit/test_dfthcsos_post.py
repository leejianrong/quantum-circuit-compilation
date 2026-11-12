import numpy as np
import pytest

from dfthcsos_gen.post import balanced_tree, decode, encode, path_tree, rotate_min_l1


@pytest.mark.parametrize("tree", [path_tree, balanced_tree])
def test_encode_decode_roundtrip(tree) -> None:
    rng = np.random.default_rng(0)
    u = rng.normal(size=(20, 76))
    u /= np.linalg.norm(u, axis=1, keepdims=True)
    edges = tree()
    err = {}
    for brot in (8, 12, 16):
        w = encode(u, edges, brot)
        assert w.min() >= 0 and w.max() < 1 << brot
        v = decode(w, edges, brot)
        err[brot] = float(np.max(np.minimum(np.linalg.norm(v - u, axis=1), np.linalg.norm(v + u, axis=1))))
    assert err[16] < 1e-3 and err[16] < err[12] < err[8]


def test_rotation_keeps_gram_and_shrinks_l1() -> None:
    rng = np.random.default_rng(1)
    sparse = rng.normal(size=(30, 6)) * (rng.random((30, 6)) < 0.3)
    w = sparse @ np.linalg.qr(rng.normal(size=(6, 6)))[0]
    w2, o = rotate_min_l1(w, iters=100)
    assert np.allclose(o @ o.T, np.eye(6), atol=1e-9)
    assert np.allclose(w2 @ w2.T, w @ w.T, atol=1e-9)
    assert np.sum(np.abs(w2).sum(0) ** 2) < 0.9 * np.sum(np.abs(w).sum(0) ** 2)
