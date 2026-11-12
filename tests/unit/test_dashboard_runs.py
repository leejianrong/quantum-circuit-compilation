"""View models of the Anatomy and Verifier theatre tabs, from the fixture ledger (no indah needed)."""

import pathlib

import pytest

from bench import ledger
from dashboard import runs

FIX = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "ledger_small.jsonl"


@pytest.fixture(scope="module")
def rows() -> list[ledger.Row]:
    return ledger.read(FIX)


def by_name(rows: list[ledger.Row], name: str) -> ledger.Row:
    return next(r for r in rows if r.circuit == name)


def test_ticks_show_a_failed_salt(rows: list[ledger.Row]) -> None:
    bad = by_name(rows, "invsqrt/zz")
    assert runs.failed_salts(bad) == {0}
    assert runs.ticks(bad) == [[0.0, 1.0]]
    text, tone = runs.verdict(bad)
    assert tone == "err" and "REJECTED" in text and "whole submission" in text


def test_ticks_of_a_passing_run_are_all_green(rows: list[ledger.Row]) -> None:
    ok = by_name(rows, "invsqrt/a2")
    assert runs.ticks(ok) == [[1.0, 0.0]] * 3
    assert runs.verdict(ok)[1] == "ok"


def test_unnamed_failure_marks_the_first_salts() -> None:
    r = ledger.Row("dqi", "x", "s", "FAIL", None, [], 1, False, 5, 2, "boom", 1.0, "g")
    assert runs.failed_salts(r) == {0, 1}


def test_spread_is_percent_above_best_with_a_running_worst(rows: list[ledger.Row]) -> None:
    out = runs.spread_rows(by_name(rows, "invsqrt/a2"))
    assert [r[0] for r in out] == [0.0, 1.0, 2.0]
    assert out[0][1] == 0.0
    assert out[1][1] == pytest.approx(0.2, rel=0.01)
    assert [r[2] for r in out] == [0.0, out[1][1], out[1][1]]
    assert [r[3] for r in out] == [None, out[1][1], None]
    assert runs.spread_rows(by_name(rows, "invsqrt/zz")) == []


def test_verify_runs_keep_failures_and_drop_references(rows: list[ledger.Row]) -> None:
    names = {r.circuit for r in runs.verify_runs(rows)}
    assert "invsqrt/zz" in names and "public:invsqrt/ff" not in names
    table = runs.run_table(runs.verify_runs(rows))
    assert table[0]["id"] == str(len(table) - 1)  # newest first


def test_stage_table_adds_the_unmarked_remainder(rows: list[ledger.Row]) -> None:
    t = runs.stage_table(by_name(rows, "invsqrt/a2"))
    assert t[0] == {"stage": "newton step (x3)", "share": 70.0}
    assert t[-1]["stage"] == "other (unmarked)" and t[-1]["share"] == pytest.approx(10.0)
    assert runs.stage_table(by_name(rows, "invsqrt/zz")) == []


def test_anatomy_runs_need_structure(rows: list[ledger.Row]) -> None:
    names = {r.circuit for r in runs.anatomy_runs(rows)}
    assert {"invsqrt/a2", "invsqrt/a3"} <= names and "invsqrt/zz" not in names


def test_flame_chart_of_the_small_generator() -> None:
    pytest.importorskip("kickmix")
    out = runs.flame("invsqrt-a3")
    assert out is not None
    svg, shares, toffolis = out
    assert svg.startswith("<svg") and 'fill="white"' in svg
    assert shares is not None and "phase" in shares and 0.99 < sum(shares.values()) < 1.01
    assert toffolis > 1000
    assert runs.data_uri(svg).startswith("data:image/svg+xml;utf8,%3Csvg")
