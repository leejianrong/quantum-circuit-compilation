"""`bench index`: segmentation, the index of a tiny circuit, and the sha-keyed cache (QCC-71)."""

import json
import pathlib

import numpy as np

from bench import circindex

# 22 input qubits (INPUT_QUBITS) are touched first so the width simulation has a well-defined start.
HEADER = [f"X q{i}" for i in range(22)]
BODY = [
    "CX q0 q22",
    "CX q1 q23",
    "CCX q22 q23 q24",
    "CX q0 q25",
    "CX q2 q25",
    "SWAP q22 q23",
    "CX q24 q22",
] * 20
TEXT = "\n".join(HEADER + BODY) + "\n"


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


def test_build_counts_and_modules() -> None:
    s = circindex.build(TEXT, name="tiny.kmb", sha256="ab" * 32, k=3, samples=32, page_size=50)
    n = len(HEADER) + len(BODY)
    assert s["instructions"] == n
    assert s["ccx"] == 20
    assert s["pages"] == -(-n // 50)
    mods = s["modules"]
    assert mods[0]["start"] == 0 and mods[-1]["end"] == n
    assert sum(m["ccx"] for m in mods) == 20
    assert s["module_source"].startswith("inferred")


def test_build_is_deterministic() -> None:
    a = circindex.build(TEXT, name="t", sha256="00", k=3, samples=32)
    b = circindex.build(TEXT, name="t", sha256="00", k=3, samples=32)
    assert a == b


def test_index_file_caches_by_sha(tmp_path: pathlib.Path) -> None:
    circ = tmp_path / "tiny.kmx"
    circ.write_text(TEXT)
    root = tmp_path / "idx"
    status, out = circindex.index_file(circ, root, k=3, samples=32)
    assert status == "built"
    summary = json.loads((out / "summary.json").read_text())
    assert out.name == summary["sha256"][:8]
    pages = sorted((out / "pages").glob("*.json"))
    assert len(pages) == summary["pages"]
    first = json.loads(pages[0].read_text())
    assert first["first"] == 0 and first["lines"][0] == "X q0"
    assert circindex.index_file(circ, root, k=3, samples=32)[0] == "cached"
    assert circindex.index_file(circ, root, force=True, k=3, samples=32)[0] == "built"
