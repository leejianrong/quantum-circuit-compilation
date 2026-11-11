import pathlib

import pytest

from bench import cli, ledger, outside

HEADER = "ref,fileName,date,description,status,publicScore,privateScore\n"


def sub(status: str, score: str = "") -> str:
    d = "Verified public portfolio: x"
    return f'58244710,submission.zip,2026-11-11 16:46:44.647000,"{d}",SubmissionStatus.{status},{score},\n'


def test_public_hashes_are_in_provenance() -> None:
    text = (pathlib.Path(__file__).resolve().parents[2] / "docs" / "PROVENANCE.md").read_text()
    for _bench, sha, _cost in outside.PUBLIC:
        assert sha in text


def test_backfill_is_idempotent_and_leaves_old_lines(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "r.jsonl"
    old = cli.run("invsqrt", tmp_path / "x", 1, 1, lambda: lambda s: 1.0)
    ledger.append(old, path)
    first = path.read_text()
    assert outside.backfill(path) == len(outside.PUBLIC)
    assert outside.backfill(path) == 0
    assert path.read_text().startswith(first)
    rows = ledger.read(path)
    assert len(rows) == 1 + len(outside.PUBLIC)
    ref = rows[1]
    assert ref.kind == "public-reference" and ref.status == "UNVERIFIED" and ref.salts == 0
    assert ref.cost and ref.toffolis is None


def test_lb_states_pending_complete_error(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "r.jsonl"
    assert outside.lb(path, lambda: "Warning: old kaggle\n" + HEADER + sub("PENDING")) == 1
    assert outside.lb(path, lambda: HEADER + sub("PENDING")) == 0
    assert outside.lb(path, lambda: HEADER + sub("COMPLETE", "25.21797")) == 1
    assert outside.lb(path, lambda: HEADER + sub("COMPLETE", "25.21797")) == 0
    assert outside.lb(path, lambda: HEADER + sub("ERROR")) == 1
    pending, done, err = ledger.read(path)
    assert [r.status for r in (pending, done, err)] == ["PENDING", "PASS", "FAIL"]
    assert pending.leaderboard_score is None and done.leaderboard_score == 25.21797
    assert done.kind == "leaderboard" and done.circuit == "submission:58244710"
    assert done.ts == "2026-11-11T16:46:44+00:00" and err.error


def test_lb_command_reports_kaggle_failure(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom() -> str:
        raise FileNotFoundError("kaggle")

    monkeypatch.setattr(outside, "fetch_submissions", boom)
    assert cli.main(["lb", "--ledger", str(tmp_path / "r.jsonl")]) == 1
    assert "kaggle submissions failed" in capsys.readouterr().out
