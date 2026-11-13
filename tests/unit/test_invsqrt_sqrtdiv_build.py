"""The in-place root stage against the integer recurrence."""

import kickmix as km
import numpy as np

from invsqrt_gen.sqrtdiv import reachable_n
from invsqrt_gen.sqrtdiv_build import nr_model, sqrt_root


def _build(steps: int, widths: list[int]) -> tuple[km.Circuit, list[km.q], list[km.q]]:
    b = km.CircuitBuilder()
    x = b.create_quantum_register(22, name="x")
    q, w, _ = sqrt_root(b, x, widths, steps)
    return b.finish_circuit(), q, w


def _signed(bits: np.ndarray) -> np.ndarray:
    v = (bits.astype(np.int64) * (1 << np.arange(len(bits)))[:, None]).sum(axis=0)
    return np.where(bits[-1], v - (1 << len(bits)), v)


def test_nr_model_is_isqrt() -> None:
    n = reachable_n()[::997]
    q, _, widths = nr_model(n)
    r = np.floor(np.sqrt(16.0 * n)).astype(np.int64)
    assert (q == r).all() and max(widths) <= 16


def test_root_circuit_matches_model() -> None:
    n_all = reachable_n()
    _, _, widths = nr_model(n_all)
    rng = np.random.default_rng(0)
    n = np.concatenate([rng.choice(n_all, 300), [2**20, 2**22 - 1, 3 * 2**20]]).astype(np.int64)
    for steps in (2, 5, 13):
        c, q, w = _build(steps, widths)
        sim = km.Simulator(len(n), seed=1)
        bits = ((n[None, :] >> np.arange(22)[:, None]) & 1) == 1
        sim.write_across_shots(c.register_data["x"], bits)
        sim.do(c)
        # reference: the model after `steps` steps
        m = n << 4
        qq = np.zeros_like(n)
        rr = np.zeros_like(n)
        for j in range(steps):
            p = (m >> (2 * (12 - j))) & 3
            rr = np.where(rr >= 0, 4 * rr + p - (4 * qq + 1), 4 * rr + p + (4 * qq + 3))
            qq = 2 * qq + (rr >= 0)
        got_q = sim.read_across_shots(km.array(q)).astype(np.int64)
        got_w = sim.read_across_shots(km.array(w))
        assert ((got_q * (1 << np.arange(len(q)))[:, None]).sum(axis=0) == qq).all()
        assert (_signed(got_w) == rr).all()
