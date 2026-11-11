import importlib.util
import pathlib

import pytest

from bench import cli, experiments, ledger, plots

FIXTURE = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "ledger_small.jsonl"
needs_mpl = pytest.mark.skipif(
    importlib.util.find_spec("matplotlib") is None, reason="plots extra not installed"
)


@pytest.fixture
def rows() -> list[ledger.Row]:
    return ledger.read(FIXTURE)


def test_verified_excludes_screens_failures_and_references(rows: list[ledger.Row]) -> None:
    v = plots.verified(rows)
    assert len(v) == 7
    assert {r.kind for r in v} == {"full"}
    assert len(plots.failures(rows)) == 1


def test_staircase_is_best_so_far(rows: list[ledger.Row]) -> None:
    st = plots.staircase(plots.run_points(rows, "invsqrt"))
    assert [round(v) for _, v in st] == [1, 20, 22]


def test_score_is_geomean_once_all_three_exist(rows: list[ledger.Row]) -> None:
    sc = plots.score_staircase(rows)
    assert sc[0][1] == pytest.approx(1.0, rel=0.01)
    assert sc[-1][1] == pytest.approx((22.0 * 60.0 * 11.0) ** (1 / 3), rel=0.02)


def test_frontier_and_leaderboard(rows: list[ledger.Row]) -> None:
    assert plots.frontier_ratio(rows, "dqi") == pytest.approx(65.0)
    assert plots.frontier_score(rows) == pytest.approx((23.0 * 65.0 * 11.2) ** (1 / 3))
    assert [v for _, v in plots.leaderboard_points(rows)] == [25.2]


def test_salt_groups_and_spread(rows: list[ledger.Row]) -> None:
    groups = dict(plots.salt_groups(rows))
    assert len(groups) == 7
    g = next(c for label, c in groups.items() if label.startswith("dqi\nb2b2b2b2"))
    assert plots.spread_pct(g) == pytest.approx([0.0, 1.0, 0.0])


def test_undated_rows_sit_before_the_first_timestamp(rows: list[ledger.Row]) -> None:
    for r in rows:
        r.ts = None
    pts = plots.run_points(rows, "invsqrt")
    assert len({t for t, _ in pts}) == 1


@needs_mpl
def test_render_all_writes_pngs(rows: list[ledger.Row], tmp_path: pathlib.Path) -> None:
    paths = plots.render_all(rows, tmp_path / "plots")
    assert len(paths) == 6
    assert all(p.read_bytes().startswith(b"\x89PNG") for p in paths)


EXPS = FIXTURE.with_name("experiments_small.jsonl")


def test_stage_bars_add_an_other_remainder(rows: list[ledger.Row]) -> None:
    bars = dict(plots.stage_bars(rows))
    assert len(bars) == 2
    shares = bars["invsqrt\na2a2a2a2"]
    assert shares["setup"] == 0.2 and shares["other (unmarked)"] == pytest.approx(0.1)


def test_pareto_points_and_front(rows: list[ledger.Row]) -> None:
    got = {(b, q) for b, _, q, _ in plots.structure_points(rows)}
    assert got == {("invsqrt", 300), ("invsqrt", 320), ("dqi", 2000), ("dfthcsos", 500)}
    assert plots.pareto_front([(300, 9e5), (320, 8.5e5), (400, 9e5)]) == [(300, 9e5), (320, 8.5e5)]


def test_funnel_counts(rows: list[ledger.Row]) -> None:
    stages = dict(plots.funnel_counts(rows, experiments.read(EXPS)))
    assert stages["screened (reduced shots)"] == {"dqi": 1}
    assert stages["full verified"] == {"invsqrt": 3, "dqi": 2, "dfthcsos": 2}
    assert stages["promoted"] == {"invsqrt": 1}
    assert stages["submitted"] == {"all": 1}


def test_wall_groups_split_by_host_and_kind(rows: list[ledger.Row]) -> None:
    groups = dict(plots.wall_groups(rows))
    assert list(groups) == ["invsqrt\nh1", "dqi\nh1", "dqi\nkaggle", "dfthcsos\nh1"]
    assert sorted(k for _, k in groups["invsqrt\nh1"]) == ["failed", "full", "full", "full"]
    assert [round(m, 2) for m, _ in groups["dqi\nkaggle"]] == [round(1300 / 60 / 3, 2)]


@needs_mpl
def test_render_with_experiment_log(rows: list[ledger.Row], tmp_path: pathlib.Path) -> None:
    paths = plots.render_all(rows, tmp_path, experiments.read(EXPS))
    assert [p.name for p in paths] == [
        "progress.png",
        "salt_spread.png",
        "stages.png",
        "pareto.png",
        "funnel.png",
        "wall_time.png",
    ]
    assert all(p.stat().st_size > 2000 for p in paths)


@needs_mpl
@pytest.mark.parametrize("n", [0, 1, 3])
def test_tiny_ledger_degrades_gracefully(rows: list[ledger.Row], tmp_path: pathlib.Path, n: int) -> None:
    paths = plots.render_all(rows[:n], tmp_path)
    assert all(p.exists() for p in paths)


@needs_mpl
def test_cli_plots_missing_ledger(tmp_path: pathlib.Path) -> None:
    assert cli.main(["plots", "--ledger", str(tmp_path / "none.jsonl"), "--out", str(tmp_path / "o")]) == 0
    assert (tmp_path / "o" / "progress.png").exists()
