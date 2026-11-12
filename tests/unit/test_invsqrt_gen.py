"""The invsqrt generator: the circuit must equal its bit-exact model, restore x and clean the scratch."""

import pathlib
from fractions import Fraction

import kickmix as km
import numpy as np
import pytest

from invsqrt_gen.build import build, ripple_add
from invsqrt_gen.model import fit_tables, model_y, normalised_inputs, rel_error
from invsqrt_gen.params import Params

SMALL = Params(a=3, frac=(22, 15, 9), guard=2)


@pytest.fixture(scope="module")
def small() -> tuple[Params, km.Circuit]:
    t = fit_tables(SMALL, passes=1, stride=211)
    return SMALL, build(SMALL, t)


def _run(c: km.Circuit, xs: np.ndarray) -> km.Simulator:
    sim = km.Simulator(batch_size=len(xs), seed=3)
    reg = c.register_data["x"]
    bits = ((xs[None, :] >> np.arange(22, dtype=np.int64)[:, None]) & 1) == 1
    sim.clear_for_shot()
    sim.write_across_shots(reg, bits)
    sim.do(c)
    return sim


def test_params_shape() -> None:
    assert SMALL.degree == 2 and SMALL.wy == 20 and SMALL.rwidth == 18
    assert len(SMALL.entries) == 2 << SMALL.a


def test_model_covers_all_normalised_inputs() -> None:
    xn, par = normalised_inputs()
    assert xn.min() == 1 << 21 and xn.max() == (1 << 22) - 1 and set(par.tolist()) == {0, 1}


def test_circuit_equals_model(small: tuple[Params, km.Circuit]) -> None:
    p, c = small
    t = fit_tables(p, passes=1, stride=211)
    rng = np.random.default_rng(0)
    xs = np.concatenate([rng.integers(1, 3_133_453, 120), [1, 2, 3, 4, 5, 16, 1 << 20, 3_133_452]]).astype(
        np.int64
    )
    sim = _run(c, xs)
    reg = c.register_data["x"]
    back = sim.read_across_shots(reg).astype(np.int64)
    assert (back * (1 << np.arange(22))[:, None]).sum(axis=0).tolist() == xs.tolist()
    scratch = km.array([km.q(i) for i in range(c.num_qubits) if km.q(i) not in set(reg)])
    assert not sim.read_across_shots(scratch).any()
    f = p.wy + 10
    for i, x in enumerate(xs.tolist()):
        z = 22 - x.bit_length()
        s = z // 2
        y = int(model_y(p, t, np.array([x << z], dtype=np.int64), np.array([z & 1], dtype=np.int64))[0])
        want = Fraction(y << s, 1 << f) % 1
        assert Fraction(sim.read_shot_phase(i)) / 2 % 1 == want


def test_error_is_reported() -> None:
    t = fit_tables(SMALL, passes=1, stride=211)
    err, per = rel_error(SMALL, t)
    assert err == pytest.approx(per.max()) and err < 0.01


def test_booth_digits_rebuild_the_remainder() -> None:
    r = np.arange(1 << SMALL.rwidth, dtype=np.int64)

    def bit(i: int) -> np.ndarray:
        return (r >> i) & 1 if 0 <= i < SMALL.rwidth else np.zeros_like(r)

    total = sum(
        (-2 * bit(2 * n + 1) + bit(2 * n) + bit(2 * n - 1)) * 4**n for n in range(SMALL.rwidth // 2 + 1)
    )
    assert (total == r).all()


@pytest.mark.parametrize("subtract", [False, True])
def test_ripple_add_matches_integers(subtract: bool) -> None:
    w, m = 5, 9
    b = km.CircuitBuilder()
    a = b.create_quantum_register(w, name="a")
    t = b.create_quantum_register(m, name="t")
    ripple_add(b, a, t, subtract=subtract)
    c = b.finish_circuit()
    rng = np.random.default_rng(1)
    av = rng.integers(0, 1 << w, 256)
    tv = rng.integers(0, 1 << m, 256)
    sim = km.Simulator(batch_size=256, seed=0)
    sim.use_same_registers_as(c)
    for i in range(256):
        sim.write_within_shot("a", i, int(av[i]))
        sim.write_within_shot("t", i, int(tv[i]))
    sim.do(c)
    want = (tv - av if subtract else tv + av) % (1 << m)
    got = [sim.read_within_shot("t", i, out=int) for i in range(256)]
    assert got == want.tolist()
    assert [sim.read_within_shot("a", i, out=int) for i in range(256)] == av.tolist()
    assert not sim.read_phase_flipped_across_shots().any()


def test_kmx_and_kmb_are_the_same_circuit(small: tuple[Params, km.Circuit], tmp_path: pathlib.Path) -> None:
    _, c = small
    c.to_file(tmp_path / "c.kmb", format="kmb")
    c.to_file(tmp_path / "c.kmx", format="kmx")
    kmb = km.Circuit.from_file(tmp_path / "c.kmb", format="kmb")
    kmx = km.Circuit.from_file(tmp_path / "c.kmx", format="kmx")
    assert kmb == kmx == c
