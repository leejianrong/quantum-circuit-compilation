import math

import pytest

from bench.rates import Point, lambda_eff, percent_per_lambda, rotation_cost, rotation_precision_bits


@pytest.mark.parametrize(
    ("bench", "q", "t"), [("invsqrt", 44, 1708.42), ("dqi", 890, 367877.5), ("dfthcsos", 427, 14712)]
)
def test_qubit_in_toffolis_matches_finite_difference(bench, q, t):
    p = Point(bench, q, t)
    k = p.qubit_power
    # one qubit up and the equivalent Toffolis down leave the score unchanged to second order
    assert math.isclose(((q + 1) ** k * (t - p.qubit_in_toffolis())) / (q**k * t), 1.0, rel_tol=1e-3)


def test_rotation_cost_roundtrip():
    assert math.isclose(rotation_precision_bits(rotation_cost(43)), 43)


def test_lambda_derivative():
    lam, e = 283.0, 3.914898
    h = 1e-4
    fd = 100 * (lambda_eff(lam + h, e) / lambda_eff(lam, e) - 1) / h
    assert math.isclose(fd, percent_per_lambda(lam, e), rel_tol=1e-4)
