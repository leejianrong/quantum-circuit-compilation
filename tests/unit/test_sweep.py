import fcntl
import pathlib
import sys

import pytest

from bench import cli, ledger, sweep


def fake_row(circuit: pathlib.Path, cost: float | None, status: str = "PASS") -> ledger.Row:
    return ledger.Row(
        bench="invsqrt",
        circuit=str(circuit),
        circuit_sha256=ledger.sha256_path(circuit),
        status=status,
        cost=cost,
        costs=[cost] if cost is not None else [],
        shots_divisor=8,
        reduced_shots=True,
        salts=1,
        failures=0 if status == "PASS" else 1,
        error=None,
        wall_s=0.1,
        git_sha="test",
        kind="screen",
    )


def gen_script(tmp_path: pathlib.Path) -> str:
    """A generator that fails for w=3 and writes `w*g` into the circuit file otherwise."""
    script = tmp_path / "gen.py"
    script.write_text(
        "import sys, pathlib\n"
        "w, g, out = int(sys.argv[1]), int(sys.argv[2]), pathlib.Path(sys.argv[3])\n"
        "if w == 3: sys.exit('no such window')\n"
        "out.write_text(str(w * g))\n"
    )
    return f"{sys.executable} {script} {{w}} {{g}} {{out}}"


def test_parse_param_lists_and_ranges() -> None:
    assert sweep.parse_param("w=4,5") == ("w", ["4", "5"])
    assert sweep.parse_param("w=2:6:2") == ("w", ["2", "4", "6"])
    assert sweep.parse_param("g=1:3") == ("g", ["1", "2", "3"])
    for bad in ("w", "=1", "w=", "1w=2", "w=5:2", "w=1:4:0"):
        with pytest.raises(ValueError):
            sweep.parse_param(bad)


def test_points_grid_random_and_ids() -> None:
    params = {"w": ["1", "2"], "g": ["a", "b", "c"]}
    grid = sweep.make_points(params)
    assert len(grid) == 6 and grid[0] == {"g": "a", "w": "1"}
    assert sweep.make_points(params, n=2) == grid[:2]
    r1, r2 = sweep.make_points(params, "random", 4, seed=1), sweep.make_points(params, "random", 4, seed=1)
    assert r1 == r2 and len({sweep.point_id(p) for p in r1}) == 4
    assert len(sweep.make_points(params, "random", 99)) == 6
    with pytest.raises(ValueError):
        sweep.make_points(params, "random")


def test_render_does_not_reparse_values() -> None:
    out = pathlib.Path("/x/o.kmb")
    assert sweep.render("gen --a {a} --o {out}", {"a": "1; rm -rf /"}, out) == [
        "gen",
        "--a",
        "1; rm -rf /",
        "--o",
        "/x/o.kmb",
    ]


def test_run_sweep_logs_ledger_rows_resumes_and_ranks(tmp_path: pathlib.Path) -> None:
    led, out = tmp_path / "l.jsonl", tmp_path / "out"
    seen: list[dict[str, str]] = []

    def verify(circuit: pathlib.Path, p: dict[str, str]) -> ledger.Row:
        seen.append(p)
        return fake_row(circuit, float(circuit.read_text()))

    points = sweep.make_points({"w": ["2", "3", "4"], "g": ["5"]})
    recs = sweep.run_sweep(
        gen_script(tmp_path), points, out, verify, ledger_path=led, lock_path=tmp_path / "lk"
    )
    assert [r["status"] for r in recs] == ["PASS", "BUILD_FAIL", "PASS"]
    assert "no such window" in recs[1]["error"]
    assert len(ledger.read(led)) == 2 and len(seen) == 2  # a failed build is logged but not verified
    assert [r["cost"] for r in sweep.ranking(recs)] == [10.0, 20.0]
    again = sweep.run_sweep(
        gen_script(tmp_path), points, out, verify, ledger_path=led, lock_path=tmp_path / "lk"
    )
    assert again == [] and len(ledger.read(led)) == 2  # resumed: nothing rerun
    assert len((out / "sweep.jsonl").read_text().splitlines()) == 3


def test_verify_failure_is_recorded_not_ranked(tmp_path: pathlib.Path) -> None:
    pts = sweep.make_points({"w": ["2"], "g": ["1"]})
    recs = sweep.run_sweep(
        gen_script(tmp_path),
        pts,
        tmp_path / "o",
        lambda c, p: fake_row(c, None, "FAIL"),
        ledger_path=tmp_path / "l.jsonl",
        lock_path=tmp_path / "lk",
    )
    assert recs[0]["status"] == "FAIL" and sweep.ranking(recs) == []


def test_heavy_lock_is_exclusive(tmp_path: pathlib.Path) -> None:
    lock = tmp_path / "lk"
    with lock.open("a") as other, sweep.heavy_lock(lock):
        with pytest.raises(BlockingIOError):
            fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
    with lock.open("a") as other:  # released after the context
        fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_cli_dry_run_and_unknown_experiment(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = ["sweep", "invsqrt", "--gen", "gen {w} {out}", "--param", "w=1,2", "--out-dir", str(tmp_path)]
    assert cli.main([*base, "--dry-run"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2 and lines[0].split()[1] == "gen"
    assert not list(tmp_path.iterdir())  # dry run builds nothing
    assert cli.main([*base, "--experiment", "E999", "--experiments", str(tmp_path / "none.jsonl")]) == 2
    assert (
        cli.main(
            ["sweep", "invsqrt", "--gen", "x", "--param", "bad", "--out-dir", str(tmp_path), "--dry-run"]
        )
        == 2
    )
