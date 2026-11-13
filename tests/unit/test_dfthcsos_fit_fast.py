import numpy as np

from dfthcsos_gen.fit import Objective, pack_matrix
from dfthcsos_gen.fit_fast import FastObjective


def _case() -> tuple[np.ndarray, np.ndarray, np.ndarray, int, tuple[int, int, int]]:
    n, shape = 8, (3, 4, 2)
    rng = np.random.default_rng(1)
    a = rng.normal(size=(n * n, n * n))
    t4 = (a + a.T).reshape(n, n, n, n)
    t4 = t4 + t4.transpose(1, 0, 2, 3)
    t4 = t4 + t4.transpose(0, 1, 3, 2)
    tm = pack_matrix(t4.reshape(n * n, n * n), n)
    return tm, rng.normal(size=(12, n)), rng.normal(size=shape), n, shape


def test_fast_objective_equals_the_reference_dense_and_full_rank() -> None:
    tm, v, w, n, shape = _case()
    f0, gv0, gw0 = Objective(tm, n, shape).value_grad(v, w)
    for rank in (None, tm.shape[0]):
        f, gv, gw = FastObjective(tm, n, shape, rank=rank).value_grad(v, w)
        assert abs(f - f0) < 1e-8 * abs(f0)
        assert np.abs(gv - gv0).max() < 1e-9 * np.abs(gv0).max()
        assert np.abs(gw - gw0).max() < 1e-9 * np.abs(gw0).max()


def test_truncated_and_float32_stay_close() -> None:
    tm, v, w, n, shape = _case()
    f0, gv0, _ = Objective(tm, n, shape).value_grad(v, w)
    f, gv, _ = FastObjective(tm, n, shape, rank=tm.shape[0], dtype=np.float32).value_grad(v, w)
    assert abs(f - f0) < 1e-4 * abs(f0)
    assert np.abs(gv - gv0).max() < 1e-3 * np.abs(gv0).max()
