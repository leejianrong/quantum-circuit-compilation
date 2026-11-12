import json
import pathlib

from bench import ledger, promote


def make_store(best: pathlib.Path) -> None:
    (best / "invsqrt").mkdir(parents=True)
    (best / "dqi").mkdir()
    (best / "dfthcsos").mkdir()
    (best / "invsqrt" / "invsqrt.kmb").write_bytes(b"inv")
    (best / "dqi" / "dqi.kmb").write_bytes(b"dqi")
    (best / "dfthcsos" / "angle_k_0.kmb").write_bytes(b"a0")
    (best / "dfthcsos" / "submission.npz").write_bytes(b"npz")


def row(sha: str, **kw: object) -> ledger.Row:
    base: dict[str, object] = {
        "bench": "invsqrt",
        "circuit": "c",
        "circuit_sha256": sha,
        "status": "PASS",
        "cost": 100.0,
        "costs": [100.0],
        "shots_divisor": 1,
        "reduced_shots": False,
        "salts": 10,
        "failures": 0,
        "error": None,
        "wall_s": 1.0,
        "git_sha": "x",
        "kind": "full",
    }
    base.update(kw)
    return ledger.Row(**base)  # type: ignore[arg-type]


def test_clean_candidate_passes() -> None:
    d = promote.decide([row("new", cost=90.0), row("old", cost=100.0)], "invsqrt", "new", "old", 10)
    assert d.ok and d.cost == 90.0 and d.prev_cost == 100.0


def test_single_failing_salt_blocks() -> None:
    rows = [row("new", cost=90.0), row("new", cost=90.0, status="FAIL", failures=1, salts=1)]
    d = promote.decide(rows, "invsqrt", "new", None, 10)
    assert not d.ok and any("failed" in r for r in d.reasons)


def test_too_few_salts_blocks() -> None:
    d = promote.decide([row("new", salts=4)], "invsqrt", "new", None, 10)
    assert not d.ok and any("only 4" in r for r in d.reasons)


def test_salts_from_several_runs_add_up() -> None:
    d = promote.decide([row("new", salts=5), row("new", salts=5)], "invsqrt", "new", None, 10)
    assert d.ok and d.salts == 10


def test_reduced_screen_and_public_rows_are_not_evidence() -> None:
    rows = [
        row("new", reduced_shots=True, shots_divisor=20),
        row("new", kind="screen"),
        row("new", kind="public-reference"),
        row("new", kind="leaderboard"),
    ]
    d = promote.decide(rows, "invsqrt", "new", None, 1)
    assert not d.ok and any("no full-strength" in r for r in d.reasons)


def test_must_beat_current_best_on_worst_salt() -> None:
    rows = [row("new", cost=100.0), row("old", cost=100.0)]
    assert not promote.decide(rows, "invsqrt", "new", "old", 10).ok
    rows = [row("new", cost=90.0, costs=[80.0, 90.0]), row("old", cost=100.0)]
    assert promote.decide(rows, "invsqrt", "new", "old", 10).ok


def test_unverified_current_best_is_replaced_with_a_note() -> None:
    d = promote.decide([row("new")], "invsqrt", "new", "mystery", 10)
    assert d.ok and d.notes


def test_other_benchmarks_rows_do_not_count() -> None:
    d = promote.decide([row("new", bench="dqi")], "invsqrt", "new", None, 1)
    assert not d.ok


def test_run_promotes_into_best_and_records_it(tmp_path: pathlib.Path) -> None:
    best = tmp_path / "best"
    make_store(best)
    cand = tmp_path / "cand.kmb"
    cand.write_bytes(b"better")
    sha = ledger.sha256_path(cand)
    old = ledger.sha256_path(best / "invsqrt" / "invsqrt.kmb")
    led = tmp_path / "results.jsonl"
    for r in (row(sha, cost=50.0), row(old, cost=100.0)):
        ledger.append(r, led)
    prom = tmp_path / "promotions.jsonl"
    assert promote.run("invsqrt", cand, led, best, 10, False, prom) == 0
    assert (best / "invsqrt" / "invsqrt.kmb").read_bytes() == b"better"
    rec = json.loads(prom.read_text())
    assert rec["sha256"] == sha and rec["prev_sha256"] == old and rec["cost"] == 50.0
    assert not (best / ".invsqrt.prev").exists()


def test_run_blocked_leaves_best_untouched(tmp_path: pathlib.Path) -> None:
    best = tmp_path / "best"
    make_store(best)
    cand = tmp_path / "cand.kmb"
    cand.write_bytes(b"worse")
    led = tmp_path / "results.jsonl"
    ledger.append(row(ledger.sha256_path(cand), salts=2), led)
    prom = tmp_path / "promotions.jsonl"
    assert promote.run("invsqrt", cand, led, best, 10, False, prom) == 1
    assert (best / "invsqrt" / "invsqrt.kmb").read_bytes() == b"inv"
    assert not prom.exists()


def test_dry_run_changes_nothing(tmp_path: pathlib.Path) -> None:
    best = tmp_path / "best"
    make_store(best)
    cand = tmp_path / "cand.kmb"
    cand.write_bytes(b"better")
    led = tmp_path / "results.jsonl"
    ledger.append(row(ledger.sha256_path(cand), cost=1.0), led)
    assert promote.run("invsqrt", cand, led, best, 10, True, tmp_path / "p.jsonl") == 0
    assert (best / "invsqrt" / "invsqrt.kmb").read_bytes() == b"inv"
