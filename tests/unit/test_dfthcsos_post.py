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


def test_joint_rotation_keeps_invariants_and_lowers_weight_part() -> None:
    from dfthcsos_gen.post import _joint_obj, rotate_joint

    rng = np.random.default_rng(3)
    w = rng.standard_normal((12, 6)) * (rng.random((12, 6)) < 0.4)
    cap = rng.standard_normal(6)
    w2, cap2, o = rotate_joint(w, cap, iters=100)
    assert np.allclose(o @ o.T, np.eye(6), atol=1e-9)
    assert np.allclose(w2 @ w2.T, w @ w.T)  # sum_c w_c w_c^T, hence sum_c X_c (x) X_c, is unchanged
    assert np.allclose(w2 @ cap2, w @ cap)  # sum_c W_c w_c, hence the offset term, is unchanged
    assert _joint_obj(w2, cap2, 1e-4)[0] < _joint_obj(w, cap, 1e-4)[0]
