"""The angle LP (`invsqrt_gen.angles.solve`) on a synthetic problem with a known cure."""

import numpy as np

from invsqrt_gen.angles import solve


def test_solve_cancels_a_correctable_error() -> None:
    rng = np.random.default_rng(0)
    n, k = 3000, 6
    f = rng.uniform(0.5, 1.0, n) * 2.0**-10
    m = (rng.integers(0, 2, (n, k)) * 2.0 ** -(np.arange(k) + 20)).astype(np.float32) / f[:, None].astype(
        np.float32
    )
    d_true = np.array([0.02, -0.03, 0.01, 0.0, -0.01, 0.015])
    tol = f * 2.0**-24
    # an error 5x over budget that scales d_true would remove, plus noise 0.2 of the budget
    e0 = -(m.astype(np.float64) * f[:, None]) @ d_true + rng.uniform(-0.2, 0.2, n) * tol
    e0 = e0 * 1.0
    d, before, after = solve(m, f, e0, rounds=6, seed_rows=3000)
    assert after >= before
    assert before < 0 < after
    assert np.abs(d).max() <= 0.05 + 1e-12


def test_solve_keeps_zero_when_already_optimal() -> None:
    n, k = 500, 3
    f = np.full(n, 2.0**-10)
    m = np.zeros((n, k), dtype=np.float32)
    e0 = np.zeros(n)
    d, before, after = solve(m, f, e0, rounds=3, seed_rows=500)
    assert after >= before - 1e-30
    assert np.allclose(before, 2.0**-34)
