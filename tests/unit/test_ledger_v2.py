import json
import pathlib

import kickmix as km  # type: ignore[import-not-found,unused-ignore]

from bench import cli, ledger, stats


def small_circuit() -> km.Circuit:
    bd = km.CircuitBuilder()
    a = bd.create_quantum_register(3, "a")
    b = bd.create_quantum_register(3, "b")
    t = bd.alloc_qubits(2)
    with bd.mark("stage1"):
        bd.init_and(a[0], b[0], t[0])
    with bd.mark("stage2"):
        bd.ccz(a[1], b[1], a[2])
        bd.ccx(a[1], b[1], t[1])
    bd.del_and(a[0], b[0], t[0])
    return bd.finish_circuit()


def test_circuit_stats_and_stage_shares() -> None:
    s = stats.circuit_stats(small_circuit())
    assert (s["toffolis"], s["qubits"]) == (3, 8)
    assert isinstance(s["depth"], int)
    assert s["stage_shares"] == {"stage1": 0.333333, "stage2": 0.666667}


def test_nested_and_repeated_marks() -> None:
    bd = km.CircuitBuilder()
    a = bd.create_quantum_register(4, "a")
    with bd.mark("outer"):
        bd.ccz(a[0], a[1], a[2])
        with bd.mark("inner"):
            bd.ccz(a[0], a[1], a[3])
    for _ in range(2):
        with bd.mark("rep"):
            bd.ccz(a[0], a[1], a[2])
    shares = stats.circuit_stats(bd.finish_circuit())["stage_shares"]
    assert shares == {"outer": 0.5, "rep": 0.5}


def test_no_marks_gives_none() -> None:
    bd = km.CircuitBuilder()
    a = bd.create_quantum_register(3, "a")
    bd.ccz(a[0], a[1], a[2])
    assert stats.circuit_stats(bd.finish_circuit())["stage_shares"] is None


def test_path_stats_file_and_angle_directory(tmp_path: pathlib.Path) -> None:
    c = small_circuit()
    c.to_file(tmp_path / "angle_k_0.kmb", format="kmb")
    c.to_file(tmp_path / "angle_k_1.kmb", format="kmb")
    assert stats.path_stats(tmp_path / "angle_k_0.kmb")["toffolis"] == 3
    d = stats.path_stats(tmp_path)
    assert d["toffolis"] == 6 and d["qubits"] == 8 and d["stage_shares"] is None


def test_run_fills_v2_fields(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "c.kmb"
    small_circuit().to_file(f, format="kmb")
    row = cli.run(
        "invsqrt",
        f,
        2,
        1,
        lambda: lambda salt: 5.0,
        stats_fn=lambda: stats.path_stats(f),
        experiment="E1",
        parent_sha="abc",
    )
    assert row.schema == 2 and row.kind == "full" and row.experiment == "E1" and row.parent_sha == "abc"
    assert row.salt_costs == [5.0, 5.0] and row.toffolis == 3 and row.qubits == 8
    assert row.ts and row.ts.endswith("+00:00")
    reduced = cli.run("invsqrt", f, 1, 4, lambda: lambda salt: 5.0)
    assert reduced.kind == "screen" and reduced.toffolis is None


def test_stats_failure_does_not_lose_the_row(tmp_path: pathlib.Path) -> None:
    def boom() -> dict[str, object]:
        raise ValueError("bad")

    row = cli.run("invsqrt", tmp_path / "x", 1, 1, lambda: lambda salt: 1.0, stats_fn=boom)
    assert row.status == "PASS" and row.toffolis is None


def test_reader_accepts_schema_1_and_2(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "r.jsonl"
    old = {
        "bench": "invsqrt", "circuit": "c", "circuit_sha256": "s", "cost": 1.0, "costs": [1.0],
        "error": None, "failures": 0, "git_sha": "x", "host": "h", "reduced_shots": False,
        "salts": 1, "schema": 1, "shots_divisor": 1, "status": "PASS", "wall_s": 1.0,
    }  # fmt: skip
    path.write_text(json.dumps(old) + "\n")
    new = cli.run("invsqrt", tmp_path / "x", 1, 1, lambda: lambda salt: 2.0)
    ledger.append(new, path)
    rows = ledger.read(path)
    assert rows[0].schema == 1 and rows[0].ts is None and rows[0].kind is None
    assert rows[1] == new
    assert path.read_text().splitlines()[0] == json.dumps(old)
