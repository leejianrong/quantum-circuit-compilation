import numpy as np

from dfthcsos_gen.fit import Objective, pack_matrix


def _problem(n=5, shape=(2, 3, 2), seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, n, n, n))
    x = x + x.transpose(1, 0, 2, 3)
    x = x + x.transpose(0, 1, 3, 2)
    x = x + x.transpose(2, 3, 0, 1)
    tmat = x.reshape(n * n, n * n)
    obj = Objective(pack_matrix(tmat, n), n, shape)
    v = rng.normal(size=(shape[0] * shape[1], n))
    w = rng.normal(size=shape)
    return tmat, obj, v, w


def test_value_matches_the_definition():
    n, shape = 5, (2, 3, 2)
    tmat, obj, v, w = _problem(n, shape)
    u = v / np.linalg.norm(v, axis=1, keepdims=True)
    u = u.reshape(shape[0], shape[1], n)
    xs = np.einsum("rbp,rbq,rbc->rcpq", u, u, w)
    h2 = np.einsum("rcpq,rcst->pqst", xs, xs).reshape(n * n, n * n)
    expected = np.sum((h2 - tmat) ** 2)
    assert abs(obj.value_grad(v, w)[0] - expected) < 1e-9 * max(1.0, expected)


def test_gradients_match_finite_differences():
    _, obj, v, w = _problem()
    _, gv, gw = obj.value_grad(v, w)
    eps = 1e-6
    for idx in [(0, 1), (3, 4), (5, 0)]:
        vp, vm = v.copy(), v.copy()
        vp[idx] += eps
        vm[idx] -= eps
        fd = (obj.value_grad(vp, w, False)[0] - obj.value_grad(vm, w, False)[0]) / (2 * eps)
        assert abs(fd - gv[idx]) < 1e-5 * max(1.0, abs(fd))
    for idx in [(0, 1, 1), (1, 2, 0)]:
        wp, wm = w.copy(), w.copy()
        wp[idx] += eps
        wm[idx] -= eps
        fd = (obj.value_grad(v, wp, False)[0] - obj.value_grad(v, wm, False)[0]) / (2 * eps)
        assert abs(fd - gw[idx]) < 1e-5 * max(1.0, abs(fd))
