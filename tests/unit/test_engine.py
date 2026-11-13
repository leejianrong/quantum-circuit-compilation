"""`bench verify --engine kickmix-engine` against a fake engine: screening only, never evidence."""

import json
import pathlib
import stat
import sys

import pytest

from bench import cli, engine, ledger, promote

FAKE = """#!{python}
import json, os, sys
argv = sys.argv[1:]
log = os.environ.get("KICKMIX_ENGINE_FAKE_LOG")
if log:
    with open(log, "w") as f:
        json.dump({{"argv": argv, "env": sorted(os.environ)}}, f)
salt = argv[argv.index("--salt") + 1]
if os.environ.get("KICKMIX_ENGINE_FAKE_MODE") == "fail":
    print(json.dumps({{"status": "FAIL", "error": "x was not restored."}}))
    sys.exit(1)
if os.environ.get("KICKMIX_ENGINE_FAKE_MODE") == "garbage":
    print("not json")
    sys.exit(3)
print(json.dumps({{"status": "PASS", "score": 100.0 + int(salt[:2], 16)}}))
"""
SHA = "0123456789abcdef0123456789abcdef01234567"


@pytest.fixture
def fake(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    path = tmp_path / "fake-engine"
    path.write_text(FAKE.format(python=sys.executable))
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv(engine.ENV_BIN, str(path))
    monkeypatch.setenv(engine.ENV_SHA, SHA)
    return path


def run_cli(tmp_path: pathlib.Path, *extra: str) -> tuple[int, ledger.Row | None]:
    circuit = tmp_path / "c.kmb"
    circuit.write_bytes(b"not a real circuit")
    out = tmp_path / "ledger.jsonl"
    rc = cli.main(
        ["verify", "invsqrt", str(circuit), "--engine", "kickmix-engine", "--ledger", str(out), *extra]
    )
    return rc, (ledger.read(out)[-1] if out.exists() else None)


def test_engine_row_is_a_screen_row_tagged_with_the_commit(
    fake: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    rc, row = run_cli(tmp_path, "--salts", "2")
    assert row is not None
    assert rc == 0
    assert (row.status, row.kind, row.engine, row.failures, row.salts) == (
        "PASS",
        "screen",
        "kickmix-engine@0123456789ab",
        0,
        2,
    )
    assert len(row.costs) == 2
    assert row.cost == max(row.costs)
    assert row.reduced_shots is False


def test_engine_gets_the_salts_the_official_path_uses(fake: pathlib.Path, tmp_path: pathlib.Path) -> None:
    log = tmp_path / "log.json"
    runner = engine.make_runner(
        "invsqrt",
        tmp_path / "c.kmb",
        tmp_path,
        threads=3,
        environ={
            engine.ENV_BIN: str(fake),
            engine.ENV_SHA: SHA,
            "KICKMIX_ENGINE_FAKE_LOG": str(log),
        },
    )
    runner(cli.salt_for(1))
    argv = json.loads(log.read_text())["argv"]
    assert argv[:2] == ["verify", "invsqrt"]
    assert argv[argv.index("--salt") + 1] == cli.salt_for(1)
    assert argv[argv.index("--threads") + 1] == "3"


def test_engine_failure_is_a_fail_row_with_its_message(
    fake: pathlib.Path, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KICKMIX_ENGINE_FAKE_MODE", "fail")
    rc, row = run_cli(tmp_path)
    assert row is not None
    assert rc == 1
    assert row.status == "FAIL"
    assert row.failures == 1
    assert row.error is not None
    assert "x was not restored." in row.error
    assert row.kind == "screen"


def test_unparsable_engine_output_is_a_runtime_error_not_a_pass(
    fake: pathlib.Path, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KICKMIX_ENGINE_FAKE_MODE", "garbage")
    runner = engine.make_runner("invsqrt", tmp_path / "c.kmb", tmp_path)
    with pytest.raises(RuntimeError, match="no JSON"):
        runner("a" * 64)


def test_unconfigured_engine_is_refused_and_writes_no_row(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(engine.ENV_BIN, raising=False)
    monkeypatch.delenv(engine.ENV_SHA, raising=False)
    rc, row = run_cli(tmp_path)
    assert (rc, row) == (2, None)


def test_engine_needs_its_commit_sha(
    fake: pathlib.Path, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(engine.ENV_SHA)
    assert run_cli(tmp_path) == (2, None)


@pytest.mark.parametrize("flags", [("--kind", "full"), ("--shots-divisor", "4")])
def test_engine_cannot_make_full_rows(
    fake: pathlib.Path, tmp_path: pathlib.Path, flags: tuple[str, ...]
) -> None:
    assert run_cli(tmp_path, *flags) == (2, None)


def test_child_environment_carries_no_credentials(
    fake: pathlib.Path, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KAGGLE_KEY", "secret")
    monkeypatch.setenv("PANDAN_TOKEN", "secret")
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    monkeypatch.setenv("KICKMIX_ENGINE_CACHE", "/x")
    log = tmp_path / "log.json"
    monkeypatch.setenv("KICKMIX_ENGINE_FAKE_LOG", str(log))
    engine.make_runner("invsqrt", tmp_path / "c.kmb", tmp_path)("a" * 64)
    seen = json.loads(log.read_text())["env"]
    assert not {"KAGGLE_KEY", "PANDAN_TOKEN", "GITHUB_TOKEN"} & set(seen)
    assert "KICKMIX_ENGINE_CACHE" in seen
    assert "KICKMIX_ENGINE_VERIFIERS" in seen


def row_for(kind: str, engine_tag: str | None) -> ledger.Row:
    return ledger.Row(
        bench="invsqrt",
        circuit="c",
        circuit_sha256="abc",
        status="PASS",
        cost=1.0,
        costs=[1.0],
        shots_divisor=1,
        reduced_shots=False,
        salts=10,
        failures=0,
        error=None,
        wall_s=1.0,
        git_sha="x",
        kind=kind,
        engine=engine_tag,
    )


def test_promote_ignores_engine_rows() -> None:
    rows = [row_for("full", "kickmix-engine@0123456789ab")]
    assert promote.evidence(rows, "invsqrt", "abc") == []
    rows.append(row_for("full", None))
    assert len(promote.evidence(rows, "invsqrt", "abc")) == 1


def test_non_executable_launcher_is_refused(
    fake: pathlib.Path, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake.chmod(0o644)
    assert run_cli(tmp_path) == (2, None)
