"""The 2-D one-hot loader: plans are exact, counts match the circuit, the circuit loads the table."""

import numpy as np
import pytest

from dfthcsos_gen.bilinear import (
    best_lb,
    bilinear_toffolis,
    center,
    centered_rank,
    evaluate_plan,
    geometry,
    gf2_rank,
    plan_plane,
    plane_toffolis,
    planes_of,
)


def _low_rank_plane(h: int, ll: int, rank: int, rng: np.random.Generator) -> np.ndarray:
    a = rng.integers(0, 2, size=(h, rank)).astype(bool)
    b = rng.integers(0, 2, size=(rank, ll)).astype(bool)
    plane = (a.astype(int) @ b.astype(int)) % 2 == 1
    plane ^= rng.integers(0, 2, size=(h, 1)).astype(bool)  # F(h)
    plane ^= rng.integers(0, 2, size=(1, ll)).astype(bool)  # G(l)
    return np.asarray(plane)


def test_rank_and_centering() -> None:
    rng = np.random.default_rng(0)
    p = _low_rank_plane(20, 16, 4, rng)
    assert gf2_rank(center(p)) <= 4
    assert gf2_rank(np.eye(7, dtype=bool)) == 7
    assert plane_toffolis(p) <= 2


@pytest.mark.parametrize("rank", [0, 1, 2, 3, 6, 9])
def test_plan_reproduces_the_plane(rank: int) -> None:
    rng = np.random.default_rng(rank)
    p = _low_rank_plane(23, 16, rank, rng)
    plan = plan_plane(p)
    assert len(plan.products) == (centered_rank(p) + 1) // 2
    assert (evaluate_plan(plan, 23, 16) == p).all()


def test_random_plane_is_expensive() -> None:
    rng = np.random.default_rng(1)
    p = rng.integers(0, 2, size=(39, 32)).astype(bool)
    assert plane_toffolis(p) >= 14


def test_geometry_for_the_public_shape() -> None:
    assert best_lb(1220) == 5
    assert geometry(1220, 5) == (39, 32)


def test_toffoli_count_matches_the_circuit_and_it_loads() -> None:
    km = pytest.importorskip("kickmix")
    from dfthcsos_gen.bilinear import build_bilinear_loader

    rng = np.random.default_rng(3)
    a, j, brot, lb = 100, 3, 4, 3
    h, ll = geometry(a, lb)
    planes = np.stack([_low_rank_plane(h, ll, r, rng) for r in [0, 1, 2, 3, 4, 5, 2, 1, 6, 3, 2, 1]])
    full = planes.transpose(1, 2, 0).reshape(h * ll, j * brot)[:a]
    delta = (full.reshape(a, j, brot) * (1 << np.arange(brot))).sum(axis=2)
    assert (planes_of(delta, brot, lb)[:, : a // ll] == planes[:, : a // ll]).all()
    circ = build_bilinear_loader(delta, brot, lb)
    assert circ.operation_statistics().num_toffoli_like == bilinear_toffolis(delta, brot, lb)

    n = (a - 1).bit_length()
    shots = 8
    sim = km.Simulator(batch_size=a * shots, debug_print=False, seed=1)
    sim.use_same_registers_as(circ)
    addr = np.tile(np.arange(a), shots)
    sel = [km.q(i) for i in range(n)]
    sim.write_across_shots(km.array(sel), ((addr[None, :] >> np.arange(n)[:, None]) & 1).astype(bool))
    sim.do(circ)
    assert not sim.read_phase_flipped_across_shots().any()
    got = np.zeros((a * shots, j), dtype=np.int64)
    for w in range(j):
        reg = km.array([km.q(n + w * brot + i) for i in range(brot)])
        got[:, w] = (sim.read_across_shots(reg).astype(np.int64) * (1 << np.arange(brot))[:, None]).sum(
            axis=0
        )
    assert (got == np.tile(delta, (shots, 1))).all()
    work = km.array([km.q(i) for i in range(n + j * brot, circ.num_qubits)])
    assert not sim.read_across_shots(work).any()
