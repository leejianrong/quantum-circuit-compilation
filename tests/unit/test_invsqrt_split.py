"""The split-phase invsqrt generators (QCC-13): each circuit must equal its bit-exact model."""

from fractions import Fraction

import kickmix as km
import numpy as np
import pytest

from invsqrt_gen.model import Tables, fit_tables, model_y, rel_error
from invsqrt_gen.params import Params
from invsqrt_gen.predict import predict
from invsqrt_gen.split import build_centered, build_split, fit_split

COMPLEMENT = Params(a=3, frac=(22, 15, 9), guard=2, ceil=True)
CENTERED = Params(a=3, frac=(22, 15, 9), guard=2, centered=True)
PM1 = Params(a=3, frac=(22, 15, 9), guard=2, centered=True, pm1=True)
PM1R = Params(a=3, frac=(22, 15, 9), guard=2, centered=True, pm1=True, rnd=True)


def _check(p: Params, t: Tables, c: km.Circuit) -> None:
    rng = np.random.default_rng(0)
    xs = np.concatenate([rng.integers(1, 3_133_453, 80), [1, 2, 3, 4, 5, 16, 1 << 20, 3_133_452]]).astype(
        np.int64
    )
    sim = km.Simulator(batch_size=len(xs), seed=3)
    reg = c.register_data["x"]
    bits = ((xs[None, :] >> np.arange(22, dtype=np.int64)[:, None]) & 1) == 1
    sim.clear_for_shot()
    sim.write_across_shots(reg, bits)
    sim.do(c)
    back = sim.read_across_shots(reg).astype(np.int64)
    assert (back * (1 << np.arange(22))[:, None]).sum(axis=0).tolist() == xs.tolist()
    scratch = km.array([km.q(i) for i in range(c.num_qubits) if km.q(i) not in set(reg)])
    assert not sim.read_across_shots(scratch).any()
    f = p.wy + 10
    for i, x in enumerate(xs.tolist()):
        z = 22 - x.bit_length()
        y = int(model_y(p, t, np.array([x << z], dtype=np.int64), np.array([z & 1], dtype=np.int64))[0])
        assert Fraction(sim.read_shot_phase(i)) / 2 % 1 == Fraction(y << (z // 2), 1 << f) % 1


@pytest.mark.parametrize("coarse", ["barrel", "serial"])
def test_complement_split_equals_model(coarse: str) -> None:
    t = fit_split(COMPLEMENT, passes=1, stride=211)
    _check(COMPLEMENT, t, build_split(COMPLEMENT, t, coarse))


@pytest.mark.parametrize("coarse", ["barrel", "serial"])
def test_centered_split_equals_model(coarse: str) -> None:
    t = fit_tables(CENTERED, passes=1, stride=211)
    _check(CENTERED, t, build_centered(CENTERED, t, coarse))


@pytest.mark.parametrize("p", [PM1, PM1R], ids=["floor", "round"])
def test_pm1_rows_equal_model(p: Params) -> None:
    t = fit_tables(p, passes=1, stride=211)
    c = build_centered(p, t, "barrel")
    _check(p, t, c)
    # no operand register: the only ancillas are the carries of the widest add
    assert c.num_qubits < build_centered(CENTERED, fit_tables(CENTERED, passes=1, stride=211)).num_qubits


def test_free_savings_keep_the_model_and_shrink_the_circuit() -> None:
    """Lent leading-one qubit, trimmed registers and windows cut qubits and Toffolis, not correctness."""
    t = fit_tables(PM1R, passes=1, stride=211)
    lean = build_centered(PM1R, t)
    plain = build_centered(PM1R, t, spare_leading_one=False, trim_windows=False)
    _check(PM1R, t, lean)
    _check(PM1R, t, plain)
    assert lean.num_qubits < plain.num_qubits
    assert lean.operation_statistics().num_toffoli_like < plain.operation_statistics().num_toffoli_like


def test_centered_remainder_saves_a_row() -> None:
    plain = Params(a=3, frac=(22, 15, 9), guard=2)
    from invsqrt_gen.model import digit_plan

    assert len(digit_plan(CENTERED, 0)) == len(digit_plan(plain, 0)) - 1


def test_predict_reports_cost() -> None:
    t = fit_tables(CENTERED, passes=1, stride=211)
    r = predict(CENTERED, t, build_centered(CENTERED, t))
    assert r["cost"] > r["qubits"] * r["toffolis"]  # the rotations add T cost on top of the Toffolis
    assert rel_error(CENTERED, t)[0] == pytest.approx(2.0 ** r["model_error_log2"])


def test_reachable_inputs_are_the_benchmark_range() -> None:
    from invsqrt_gen.model import MAX_X, normalised_inputs, reachable_mask

    xn, par = normalised_inputs()
    reach = reachable_mask()
    assert MAX_X == 3_133_452 and reach.sum() == 2_350_089
    assert reach[(par == 1) & (xn % 2 == 0)].all()  # x = xn / 2 < 2^21 always runs
    assert not reach[(par == 0) & (xn > MAX_X) & (xn % 4 != 0)].any()  # z >= 2 needs two zero low bits


def test_reachable_fit_only_scores_reachable_inputs() -> None:
    from invsqrt_gen.model import reachable_mask

    t = fit_tables(CENTERED, passes=1, stride=211, reachable=True)
    _, per = rel_error(CENTERED, t)
    assert per[reachable_mask()].max() < 0.01
