"""`bench index`: segmentation, scanning, the index of a tiny circuit, and the sha-keyed cache (QCC-71)."""

import json
import pathlib

import numpy as np
import pytest

from bench import circindex

# 22 input qubits (INPUT_QUBITS) are touched first so the invsqrt width simulation has a defined start.
HEADER = [f"X q{i}" for i in range(22)]
UNIT = [
    "CX q0 q22",
    "HMR q23 b0",
    "PUSH_CONDITION if b0",
    "CCX q22 q23 q24",
    "POP_CONDITION",
    "Z_POW q22 0.25",
]
TEXT = "\n".join(HEADER + UNIT * 10 + ["Z_POW q22 0.5"]) + "\n"


def scanned(list_all: bool = True) -> circindex.Scan:
    return circindex.scan(TEXT.splitlines(), list_all=list_all)


def test_segment_cuts_at_the_step() -> None:
    width = np.array([3] * 100 + [9] * 100)
    assert circindex.segment(width, 2, min_len=10) == [(0, 100), (100, 200)]


def test_segment_stops_when_nothing_to_gain() -> None:
    assert circindex.segment(np.full(300, 5), 8, min_len=10) == [(0, 300)]


def test_segments_cover_the_circuit_without_gaps() -> None:
    rng = np.random.default_rng(0)
    width = np.repeat(rng.integers(1, 30, 12), 40)
    segs = circindex.segment(width, 6, min_len=20)
    assert segs[0][0] == 0 and segs[-1][1] == len(width)
    assert all(a[1] == b[0] for a, b in zip(segs, segs[1:], strict=False))


def test_segment_takes_several_features() -> None:
    feats = np.stack([np.zeros(200), np.array([0.0] * 120 + [5.0] * 80)], axis=1)
    assert circindex.segment(feats, 2, min_len=10) == [(0, 120), (120, 200)]


def test_modules_scale_back_from_blocks() -> None:
    text = ["X q0"] * 30_000 + ["CCX q0 q1 q2"] * 30_000
    s = circindex.scan(text, list_all=False)
    segs = circindex.segment_modules(s, circindex.interval_width(s), 2)
    assert segs[0][0] == 0 and segs[-1][1] == s.n and len(segs) == 2
    assert abs(segs[0][1] - 30_000) <= 4  # within one averaging block of the change


def test_scan_lists_everything_or_only_priced_gates() -> None:
    full, sparse = scanned(True), scanned(False)
    assert full.n == sparse.n == len(HEADER) + 60 + 1
    assert len(full.rows) == full.n
    assert {r[1].split()[0] for r in sparse.rows} == {"CCX", "Z_POW"}  # CCX and the 0.25 rotation
    assert len(sparse.rows) == 20 and all("0.5" not in r[1] for r in sparse.rows)
    assert sparse.listing == "priced"


def test_conditioned_flags_follow_push_and_pop() -> None:
    rows = {r[1]: r[2] for r in scanned().rows}
    assert rows["CCX q22 q23 q24"] is True
    assert rows["PUSH_CONDITION if b0"] is False and rows["CX q0 q22"] is False


def test_interval_width_counts_qubits_between_first_and_last_use() -> None:
    s = circindex.scan(["X q0", "CX q0 q1", "X q2", "CX q1 q2"], list_all=True)
    assert list(circindex.interval_width(s)) == [1, 2, 2, 2]


def test_build_counts_and_modules() -> None:
    s = circindex.build(
        scanned(), bench="invsqrt", name="tiny", sha256="ab" * 32, k=3, samples=32, page_size=50
    )
    n = len(HEADER) + 61
    assert s["instructions"] == n and s["ccx"] == 10 and s["listing"] == "all"
    assert s["pages"] == -(-n // 50)
    mods = s["modules"]
    assert mods[0]["start"] == 0 and mods[-1]["end"] == n
    assert sum(m["ccx"] for m in mods) == 10
    assert s["module_source"].startswith("inferred")


def test_other_benchmarks_use_the_touch_interval_width() -> None:
    s = circindex.build(scanned(False), bench="dqi", name="t", sha256="00", k=3)
    assert s["width_method"].startswith("touch interval") and s["samples"] is None
    assert s["listing"] == "priced" and s["listed"] == 20


def test_build_is_deterministic() -> None:
    a = circindex.build(scanned(), bench="invsqrt", name="t", sha256="00", k=3, samples=32)
    b = circindex.build(scanned(), bench="invsqrt", name="t", sha256="00", k=3, samples=32)
    assert a == b


def test_bench_is_taken_from_the_directory(tmp_path: pathlib.Path) -> None:
    assert circindex.bench_of(tmp_path / "best" / "dqi" / "x.kmb") == "dqi"
    with pytest.raises(ValueError):
        circindex.bench_of(tmp_path / "somewhere" / "x.kmb")


def test_index_file_caches_by_sha(tmp_path: pathlib.Path) -> None:
    circ = tmp_path / "tiny.kmx"
    circ.write_text(TEXT)
    root = tmp_path / "idx"
    status, out = circindex.index_file(circ, root, bench="invsqrt", k=3, samples=32)
    assert status == "built"
    summary = json.loads((out / "summary.json").read_text())
    assert out.name == summary["sha256"][:8]
    pages = sorted((out / "pages").glob("*.json"))
    assert len(pages) == summary["pages"]
    assert json.loads(pages[0].read_text())["rows"][0] == [0, "X q0", 0]
    assert circindex.index_file(circ, root, bench="invsqrt", k=3, samples=32)[0] == "cached"
    assert circindex.index_file(circ, root, bench="invsqrt", force=True, k=3, samples=32)[0] == "built"
    assert not [p for p in root.iterdir() if p.name != out.name]  # the temporary text export is gone
