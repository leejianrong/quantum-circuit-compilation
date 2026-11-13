import importlib.util
from pathlib import Path

import numpy as np
import pytest

from dfthcsos_gen.fit import Objective, pack_matrix

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "run_fit_gpu.py"


def test_torch_objective_matches_numpy_value_and_gradients() -> None:
    torch = pytest.importorskip("torch")
    spec = importlib.util.spec_from_file_location("run_fit_gpu", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    n, shape = 8, (2, 4, 3)
    rng = np.random.default_rng(0)
    a = rng.normal(size=(n * n, n * n))
    t4 = (a + a.T).reshape(n, n, n, n)
    t4 = t4 + t4.transpose(1, 0, 2, 3)
    t4 = t4 + t4.transpose(0, 1, 3, 2)
    tm = pack_matrix(t4.reshape(n * n, n * n), n)
    v, w = rng.normal(size=(8, n)), rng.normal(size=shape)
    f, gv, gw = Objective(tm, n, shape).value_grad(v, w)
    vt, wt = torch.tensor(v, requires_grad=True), torch.tensor(w, requires_grad=True)
    ft = mod.make_loss(tm, n, shape, "cpu")(vt, wt)
    ft.backward()
    assert float(ft) == pytest.approx(f, rel=1e-10)
    assert np.abs(vt.grad.numpy() - gv).max() < 1e-9
    assert np.abs(wt.grad.numpy() - gw).max() < 1e-9
