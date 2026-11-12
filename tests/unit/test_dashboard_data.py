import pathlib

import pytest

from bench import experiments, ledger, plots
from dashboard import data

FIX = pathlib.Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def rows() -> list[ledger.Row]:
    return ledger.read(FIX / "ledger_small.jsonl")


def test_third_party_circuits_are_not_ours(rows: list[ledger.Row]) -> None:
    mk = lambda c: ledger.Row("invsqrt", c, "x", "PASS", 1.0, [1.0], 1, False, 1, 0, None, 0.0, "g")  # noqa: E731
    assert plots.is_own(mk("out/g6.kmb"))
    assert plots.is_own(mk("own:dqi_gen/divstep"))
    for c in ("public/a/b.kmb", "data/sample_submission/invsqrt.kmb", "/kaggle/input/x/dqi.kmb"):
        assert not plots.is_own(mk(c))


def test_summary_keeps_ours_public_and_leaderboard_apart(rows: list[ledger.Row]) -> None:
    s = data.summarize(rows)
    assert s.ours_score == pytest.approx((22.0 * 60.0 * 11.0) ** (1 / 3), rel=0.02)
    assert s.public["dqi"] == pytest.approx(65.0)
    assert s.public_score == pytest.approx((23.0 * 65.0 * 11.2) ** (1 / 3))
    assert s.leaderboard_score == 25.2 and s.leaderboard_n == 1
    assert s.gap and s.gap > 1


def test_summary_of_an_empty_ledger_is_all_none() -> None:
    s = data.summarize([])
    assert s.ours_score is None and s.public_score is None and s.gap is None
    assert data.score_rows([]) and data.progress_rows([])


def test_step_rows_carry_values_forward_with_a_vertical_edge() -> None:
    rows = data.step_rows([[(0.0, 1.0), (10.0, 3.0)]], [[(5.0, 9.0)]], end=20.0)
    assert [r[0] for r in rows] == [0.0, 5.0, 10.0 - data.EPS, 10.0, 20.0]
    assert [r[1] for r in rows] == [1.0, 1.0, 1.0, 3.0, 3.0]
    assert [r[2] for r in rows] == [None, 9.0, None, None, None]


def test_score_rows_start_only_when_all_three_benchmarks_exist(rows: list[ledger.Row]) -> None:
    ys = [r[1] for r in data.score_rows(rows) if r[1] is not None]
    assert ys[0] == pytest.approx(1.0, rel=0.01) and ys[-1] > 20


def test_experiment_table_joins_runs(rows: list[ledger.Row]) -> None:
    exps = experiments.read(FIX / "experiments_small.jsonl")
    for r in rows:
        if r.circuit in ("invsqrt/a3", "invsqrt/zz"):
            r.experiment = "E001"
    table = {r["id"]: r for r in data.experiment_table(rows, exps)}
    assert table["E001"]["runs"] == 2 and table["E001"]["failures"] == 1
    assert table["E001"]["ratio"] == "21.96x"
    assert table["E003"]["outcome"] == "open" and table["E003"]["best_cost"] == "-"
    assert list(table) == ["E003", "E002", "E001"]  # newest first
