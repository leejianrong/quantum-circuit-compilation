import json
import pathlib

from bench import lineage
from dashboard import lineage_view

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROVENANCE = (ROOT / "docs" / "PROVENANCE.md").read_text()


def built() -> dict:  # type: ignore[type-arg]
    return lineage.build(PROVENANCE)


def test_checked_in_lineage_is_current() -> None:
    """Edit docs/PROVENANCE.md or bench/lineage.py, then run `uv run python -m bench.lineage`."""
    assert json.loads((ROOT / "ledger" / "lineage.json").read_text()) == json.loads(json.dumps(built()))


def test_every_public_circuit_is_a_provenance_row_with_its_sha() -> None:
    public = [n for n in built()["nodes"] if n["kind"] == "public"]
    assert len(public) >= 12
    for n in public:
        assert n["sha256"] in PROVENANCE and len(n["sha256"]) == 64
        assert n["sources"], n["id"]


def test_graph_covers_all_three_benchmarks_from_baseline_to_ours() -> None:
    lin = built()
    for bench in lineage.BENCHES:
        kinds = {n["kind"] for n in lin["nodes"] if n["bench"] == bench}
        assert {"baseline", "public", "ours"} <= kinds, bench


def test_no_licence_flows_down_derived_edges_only() -> None:
    nodes = {n["id"]: n for n in built()["nodes"]}
    assert nodes["anc:jday96314"]["no_licence"]
    assert all(nodes[i]["no_licence"] for i in ("e9f54be3", "4432ec5f", "b71b21ca"))
    assert not nodes["dqi_gen"]["no_licence"]  # an idea edge does not carry a licence problem
    assert not any(n["no_licence"] for n in nodes.values() if n["bench"] != "dqi")


def test_view_marks_no_licence_twice_and_lays_out_left_to_right() -> None:
    lin = built()
    nodes, edges = lineage_view.graph(lin)
    by = {n["id"]: n for n in nodes}
    assert "[NO LICENCE]" in by["e9f54be3"]["label"] and by["e9f54be3"]["group"].startswith("NO LICENCE")
    assert by["dqi_gen"]["size"] > by["e9f54be3"]["size"]
    for e in edges:
        assert by[e["source"]]["x"] < by[e["target"]]["x"], e


def test_detail_text() -> None:
    lin = built()
    text = lineage_view.detail(lin, "e9f54be3")
    assert "No licence in the ancestry" in text and "S7" in text
    assert "Click a node" in lineage_view.detail(lin, None)
