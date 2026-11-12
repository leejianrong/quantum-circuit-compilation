import pathlib

from bench import cli, ledger


def test_ledger_round_trip(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "sub" / "results.jsonl"
    c = tmp_path / "c.kmb"
    c.write_bytes(b"abc")
    row = cli.run("invsqrt", c, 2, 4, lambda: lambda salt: 3.0)
    ledger.append(row, path)
    ledger.append(row, path)
    assert ledger.read(path) == [row, row]
    assert row.status == "PASS" and row.cost == 3.0 and row.reduced_shots and row.schema == ledger.SCHEMA


def test_sha_stable_and_content_sensitive(tmp_path: pathlib.Path) -> None:
    (tmp_path / "a.kmb").write_bytes(b"x")
    (tmp_path / "b.kmb").write_bytes(b"y")
    first = ledger.sha256_path(tmp_path)
    assert first == ledger.sha256_path(tmp_path)
    assert (
        ledger.sha256_path(tmp_path / "a.kmb")
        == "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881"
    )
    (tmp_path / "b.kmb").write_bytes(b"z")
    assert ledger.sha256_path(tmp_path) != first


def test_salts_distinct_and_long() -> None:
    salts = {cli.salt_for(i) for i in range(10)}
    assert len(salts) == 10 and all(len(s) >= 32 for s in salts)


def test_corrupted_circuit_is_fail_row_not_crash(tmp_path: pathlib.Path) -> None:
    c = tmp_path / "bad.kmb"
    c.write_bytes(b"garbage")

    def boom() -> cli.Runner:
        raise ValueError("not a kickmix file")

    row = cli.run("dqi", c, 3, 1, boom)
    assert row.status == "FAIL" and row.cost is None and row.failures == 3
    assert row.error and "not a kickmix file" in row.error


def test_one_failing_salt_fails_the_row(tmp_path: pathlib.Path) -> None:
    c = tmp_path / "c.kmb"
    c.write_bytes(b"abc")
    seen = []

    def verify(salt: str) -> float:
        seen.append(salt)
        if len(seen) == 2:
            raise AssertionError("shot failed")
        return 5.0

    row = cli.run("invsqrt", c, 3, 1, lambda: verify)
    assert (row.status, row.failures, row.costs, row.cost) == ("FAIL", 1, [5.0, 5.0], 5.0)


def test_kickmix_import_hint_explains_libstdcxx_mismatch() -> None:
    from bench.cli import kickmix_import_hint

    msg = kickmix_import_hint(ImportError("libstdc++.so.6: version `GLIBCXX_3.4.32' not found"))
    assert "uv sync" in msg and "PYTHONPATH" in msg
    assert kickmix_import_hint(ImportError("no module named kickmix")) == "no module named kickmix"
