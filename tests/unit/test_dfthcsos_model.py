"""The cost model reproduces the verifier's reported numbers (recorded from real verifier runs)."""

import pytest

from dfthcsos_model import Angles, lambda_eff, plain_qrom_angles, prepare_costs, score
from dfthcsos_model.model import passes_gates

# Baseline: sample submission, verifier output (verify.py, SCORING_README worked example).
BASE_SHAPE = (65, 60, 60)
BASE_LAMBDA, BASE_GAP = 308.4559397330944, 3.965477244291833
BASE_SCORE = 3355599588.3155365

# Public refit (91d0ad25): lambda/gap recomputed with the verifier's evaluate_words, cost from
# `bench verify dfthcsos best/dfthcsos --salts 1`.
REFIT_SHAPE = (8, 143, 44)
REFIT_LAMBDA, REFIT_GAP = 282.77473254974973, 3.914898000250105
REFIT_SCORE = 299614422.43592083


def test_baseline_plain_qrom_matches_verifier() -> None:
    toff, scratch = plain_qrom_angles(65, 60, J=8)
    assert toff == 79480 and scratch == 11
    p = prepare_costs(*BASE_SHAPE, brot=12)
    assert (p.outer_toffoli, p.inner_toffoli, p.givens_toffoli) == (846, 9461, 3450)
    assert (p.outer_persistent, p.outer_temp) == (46, 370)
    assert (p.inner_persistent, p.inner_temp) == (44, 544)
    b = score(BASE_SHAPE, Angles(79480, 119, J=8, brot=12), BASE_LAMBDA, BASE_GAP)
    assert (b.t_total, b.q_total, b.q_temp_source) == (93237, 730, "inner")
    assert b.score == pytest.approx(BASE_SCORE, rel=1e-9)


def test_refit_matches_verifier() -> None:
    p = prepare_costs(*REFIT_SHAPE, brot=8)
    assert (p.outer_toffoli, p.inner_toffoli, p.givens_toffoli) == (317, 4095, 2250)
    assert (p.persistent, p.outer_temp, p.inner_temp) == (84, 90, 303)
    b = score(REFIT_SHAPE, Angles(8302, 128, J=5, brot=8), REFIT_LAMBDA, REFIT_GAP)
    assert (b.t_total, b.q_total) == (14964, 427)
    assert b.score == pytest.approx(REFIT_SCORE, rel=1e-9)


def test_lambda_eff_and_gates() -> None:
    assert lambda_eff(49.0, 3.914898) == pytest.approx(19.19201859236271)
    assert passes_gates(0.02, 0.02, REFIT_LAMBDA, REFIT_GAP)
    assert not passes_gates(0.02, 0.02, REFIT_LAMBDA, 3.914898)  # equality is rejected
    assert not passes_gates(0.0201, 0.01, REFIT_LAMBDA, REFIT_GAP)


def test_brot_cliff_baseline_shape() -> None:
    """The inner QROAM block exponent steps down when brot*75 drops below its temporary qubits."""
    k = {b: prepare_costs(*BASE_SHAPE, brot=b).inner_k for b in (3, 4, 7, 8, 14, 15)}
    assert k == {3: 3, 4: 4, 7: 4, 8: 5, 14: 5, 15: 6}
    assert prepare_costs(*BASE_SHAPE, brot=7).inner_temp == 273
    assert prepare_costs(*BASE_SHAPE, brot=8).inner_temp == 544


def test_refit_shape_sits_just_under_cliff() -> None:
    """(8,143,44): k=5 needs 600 temporaries, and 600 < 75*8 is false (equality), so brot 8 gets k=4."""
    assert prepare_costs(*REFIT_SHAPE, brot=8).inner_k == 4
    assert prepare_costs(*REFIT_SHAPE, brot=9).inner_k == 5
