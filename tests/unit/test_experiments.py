import pathlib

import pytest

from bench import cli, experiments, ledger


def test_new_close_list_shape(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    log = tmp_path / "e.jsonl"
    assert (
        cli.main(["exp", "--log", str(log), "new", "fold phases", "--bench", "invsqrt", "--parent", "ab"])
        == 0
    )
    assert capsys.readouterr().out.strip() == "E001"
    assert cli.main(["exp", "--log", str(log), "new", "second", "--bench", "dqi"]) == 0
    assert capsys.readouterr().out.strip() == "E002"
    assert cli.main(["exp", "--log", str(log), "close", "E001", "rejected", "--notes", "1 failure"]) == 0
    assert len(log.read_text().splitlines()) == 3  # append-only: close adds a snapshot
    e = experiments.read(log)
    assert list(e) == ["E001", "E002"]
    assert (e["E001"].status, e["E001"].outcome, e["E001"].notes) == ("closed", "rejected", "1 failure")
    assert e["E001"].parent == "ab" and e["E001"].closed and e["E002"].status == "open"
    capsys.readouterr()
    assert cli.main(["exp", "--log", str(log), "list", "--ledger", str(tmp_path / "none.jsonl")]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("E001\tclosed\trejected\tinvsqrt\t0 runs")


def test_close_unknown_or_twice_is_an_error(tmp_path: pathlib.Path) -> None:
    log = tmp_path / "e.jsonl"
    assert cli.main(["exp", "--log", str(log), "close", "E9", "failed"]) == 2
    experiments.new("h", "dqi", None, log)
    experiments.close("E001", "failed", None, log)
    assert cli.main(["exp", "--log", str(log), "close", "E001", "failed"]) == 2


def test_verify_rejects_unknown_experiment(tmp_path: pathlib.Path) -> None:
    argv = ["verify", "invsqrt", str(tmp_path / "c.kmb"), "--experiments", str(tmp_path / "e.jsonl")]
    assert cli.main([*argv, "--experiment", "E404"]) == 2


def test_rows_link_to_experiment_in_list(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    log, res = tmp_path / "e.jsonl", tmp_path / "r.jsonl"
    e = experiments.new("h", "invsqrt", None, log)
    c = tmp_path / "c.kmb"
    c.write_bytes(b"x")
    for exp in (e.id, e.id, None):
        ledger.append(cli.run("invsqrt", c, 1, 1, lambda: lambda s: 1.0, experiment=exp), res)
    assert [r.experiment for r in ledger.read(res)] == [e.id, e.id, None]
    assert cli.main(["exp", "--log", str(log), "list", "--ledger", str(res)]) == 0
    assert "2 runs" in capsys.readouterr().out
