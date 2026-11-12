"""The Cost explorer's view model reproduces the verifier-checked costs at the right settings."""

import pytest

from dashboard import cost


def test_baseline_preset_reproduces_the_host_cost() -> None:
    r = cost.evaluate(cost.PRESETS["Host baseline"])
    assert r.breakdown.score == pytest.approx(3_355_599_588.3155365, rel=1e-9)
    assert r.ratio == pytest.approx(1.0)
    assert r.gate.status == "pass" and r.gate.basis == "measured"


def test_public_preset_reproduces_the_public_refit() -> None:
    r = cost.evaluate(cost.PRESETS["Public refit"])
    assert r.breakdown.score == pytest.approx(299_614_422.43592083, rel=1e-9)
    assert r.ratio == pytest.approx(11.2, abs=0.01)
    assert r.gate.status == "pass"


def test_public_table_with_our_loader_matches_the_verified_6_85() -> None:
    r = cost.evaluate(cost.PRESETS["Public table, our loader"])
    assert r.angles.toffoli == 14616 and r.angles.qubits == 125
    assert r.breakdown.score == pytest.approx(489_890_973.18, rel=1e-6)
    assert r.ratio == pytest.approx(6.85, abs=0.01)


@pytest.mark.parametrize(
    ("preset", "verified", "ratio"),
    [("Our 11-bit table", 1_697_674_804.55, 1.98), ("Our 12-bit table", 1_850_153_217.13, 1.81)],
)
def test_own_tables_match_the_verified_cost(preset: str, verified: float, ratio: float) -> None:
    r = cost.evaluate(cost.PRESETS[preset])
    assert r.breakdown.score == pytest.approx(verified, rel=2e-3)  # Lambda is stored to 4 digits
    assert r.ratio == pytest.approx(ratio, abs=0.01)
    assert r.gate.status == "pass" and r.cap_ok


def test_own_table_gate_fails_below_eleven_bits() -> None:
    s = cost.PRESETS["Our 11-bit table"]
    for brot, status in ((12, "pass"), (11, "pass"), (10, "fail"), (9, "fail"), (8, "fail")):
        r = cost.evaluate(cost.Setting(s.R, s.B, s.C, brot, s.J, "own", "own"))
        assert r.gate.status == status, brot


def test_a_different_shape_is_not_measured() -> None:
    s = cost.PRESETS["Our 11-bit table"]
    r = cost.evaluate(cost.Setting(9, s.B, s.C, 11, 9, "own", "own"))
    assert r.gate.status == "not measured"


def test_qubit_cap_is_checked() -> None:
    s = cost.PRESETS["Our 11-bit table"]
    assert not cost.evaluate(cost.Setting(s.R, s.B, s.C, 11, 30, "own", "own")).cap_ok
    assert cost.max_J(8, 176, 11) == 9


def test_cliffs_of_the_baseline_shape() -> None:
    # test_dfthcsos_model: inner_temp is 273 at brot 7 and 544 at 8
    assert cost.cliffs(cost.PRESETS["Host baseline"]) == [(7, 8), (14, 15)]
    assert cost.cliffs(cost.PRESETS["Our 11-bit table"]) == [(8, 9)]


def test_chart_rows_have_one_dot_at_the_chosen_width() -> None:
    rows = cost.chart_rows(cost.PRESETS["Our 11-bit table"])
    assert [r[0] for r in rows] == list(cost.BROTS)
    assert [r[0] for r in rows if r[3] is not None] == [11]
