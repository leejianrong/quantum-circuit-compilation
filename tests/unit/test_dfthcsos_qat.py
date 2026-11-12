import numpy as np

from dfthcsos_gen.post import angles_of, balanced_tree, decode, decode_backward, decode_real


def test_angles_roundtrip_and_gradient() -> None:
    rng = np.random.default_rng(0)
    u = rng.normal(size=(6, 76))
    u /= np.linalg.norm(u, axis=1, keepdims=True)
    edges, brot = balanced_tree(), 10
    th = angles_of(u, edges, brot)
    v, _ = decode_real(th, edges, brot)
    assert np.allclose(np.abs(np.sum(v * u, axis=1)), 1.0)
    words = np.rint(th).astype(np.int64) % (1 << brot)
    assert np.allclose(decode(words, edges, brot), decode_real(np.rint(th), edges, brot)[0])
    a = rng.normal(size=(6, 76))
    th0 = th + rng.normal(size=th.shape)
    _, saved = decode_real(th0, edges, brot)
    g = decode_backward(th0, edges, brot, saved, a)
    d = rng.normal(size=th.shape)
    eps = 1e-6
    fp = np.sum(decode_real(th0 + eps * d, edges, brot)[0] * a)
    fm = np.sum(decode_real(th0 - eps * d, edges, brot)[0] * a)
    assert abs((fp - fm) / (2 * eps) - np.sum(g * d)) < 1e-5
