import json

import pytest

pytest.importorskip("matplotlib")

from analysis import dqi_figures, report  # noqa: E402


def test_data_is_internally_consistent() -> None:
    d = dqi_figures.load()
    wf = d["v7_patch_waterfall"]
    assert (
        wf["start"] + sum(s[1] for s in wf["steps"]) == wf["final"] == d["totals"]["theirs"]["toffoli_like"]
    )
    p = d["profile_diff"]
    assert sum(p["theirs"]) == d["totals"]["theirs"]["toffoli_like"]
    assert sum(p["ours"]) == d["totals"]["ours"]["toffoli_like"]
    m = d["instruction_mix"]
    for side, key in (("ours", "ours"), ("theirs", "theirs")):
        t = d["totals"][key]
        assert m[side]["CCX"] + m[side]["CCZ"] + m[side]["CSWAP"] == t["toffoli_like"]
    comps = d["stage_ledger"]["components"]
    assert abs(sum(c["ours"] for c in comps) - d["stage_ledger"]["ours_total"]) < 600
    assert sum(c["theirs_v2"] for c in comps) == d["stage_ledger"]["theirs_v2_total"]
    assert sum(c["theirs_final"] for c in comps) == d["stage_ledger"]["theirs_final_total"]
    assert d["stage_ledger"]["theirs_final_total"] == d["totals"]["theirs"]["toffoli_like"]
    q = d["qubit_timeline_theirs"]
    assert len(q["allocated_Q"]) == q["groups"][-1][2] + 1
    assert max(q["allocated_Q"]) == q["peak_at_marks"] <= q["circuit_peak"]


def test_figures_and_pdf_are_written(tmp_path) -> None:  # type: ignore[no-untyped-def]
    paths = dqi_figures.draw_all(tmp_path / "png")
    assert len(paths) == len(dqi_figures.FIGURES)
    for p in paths:
        assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    pdf = report.build(tmp_path / "r.pdf")
    assert pdf.read_bytes()[:5] == b"%PDF-"
    json.loads(dqi_figures.DATA.read_text())
