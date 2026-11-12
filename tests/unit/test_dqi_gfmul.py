"""The low-rank GF(2^m) multiplier agrees with the field and costs its rank in Toffolis."""

import random

import pytest

km = pytest.importorskip("kickmix")

from dqi_gen import gfmul  # noqa: E402

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(("degree", "rank"), [(3, 6), (6, 18), (12, 42)])
def test_bilinear_algorithm_matches_the_field(degree: int, rank: int) -> None:
    gf = km.GF2Field(degree)
    forms, _ = gfmul.bilinear_algorithm(degree)
    assert len(forms) == rank
    rng = random.Random(3)
    for _ in range(500):
        a, b = rng.randrange(1 << degree), rng.randrange(1 << degree)
        assert gfmul.classical_mul(degree, a, b) == gf.mul(a, b)


def test_circuit_costs_the_rank_and_xors_into_the_target() -> None:
    builder = km.CircuitBuilder()
    gf = km.GF2Field(12)
    a, b, t = (builder.alloc_qubits(12) for _ in range(3))
    gfmul.FastMul(builder, gf).ixor_mul(a, b, t)
    assert int(builder.finish_circuit().operation_statistics().num_toffoli_like) == 42
