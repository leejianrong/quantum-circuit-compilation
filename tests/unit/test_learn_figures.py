"""The learning-track figures: deterministic, tied to the ledger, and every page figure is registered."""

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

pytest.importorskip("matplotlib")

from analysis import learn_figures  # noqa: E402
from analysis.circuit_draw import draw  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
IMG = ROOT / "docs" / "img" / "learn"
LEARN = ROOT / "docs" / "learn"


def svg_text(path: Path) -> list[str]:
    """The text strings of an SVG: labels and numbers, independent of path geometry."""
    return [
        t.strip()
        for el in ET.parse(path).iter()
        if el.tag.endswith("text")
        for t in [el.text or ""]
        if t.strip()
    ]


@pytest.mark.parametrize("name", sorted(learn_figures.FIGURES))
def test_figure_renders_deterministically(name: str, tmp_path: Path) -> None:
    a, b = tmp_path / "a.svg", tmp_path / "b.svg"
    learn_figures.render(name, a)
    learn_figures.render(name, b)
    assert a.read_bytes() == b.read_bytes()


@pytest.mark.parametrize("name", sorted(learn_figures.FIGURES))
def test_committed_svg_is_current(name: str, tmp_path: Path) -> None:
    committed = IMG / f"{name}.svg"
    assert committed.is_file(), f"run `make learn-figures` and commit {committed}"
    fresh = tmp_path / "fresh.svg"
    learn_figures.render(name, fresh)
    assert svg_text(committed) == svg_text(fresh), f"{name}.svg is stale: run `make learn-figures`"


def test_no_stray_svgs() -> None:
    assert {p.stem for p in IMG.glob("*.svg")} == set(learn_figures.FIGURES)


def test_pages_use_exactly_the_registered_figures() -> None:
    used = set()
    for page in LEARN.rglob("*.md"):
        used |= set(re.findall(r"img/learn/([a-z0-9-]+)\.svg", page.read_text()))
    assert used == set(learn_figures.FIGURES)


def ledger_rows() -> list[dict]:  # type: ignore[type-arg]
    rows = (json.loads(line) for line in (ROOT / "ledger" / "results.jsonl").read_text().splitlines() if line)
    return [r for r in rows if r.get("status") == "PASS" and not r.get("reduced_shots")]


def test_plotted_circuits_match_ledger_rows() -> None:
    d = learn_figures.load()
    rows = ledger_rows()
    for bench in ("invsqrt", "dqi"):
        for p in d[bench]["points"]:
            hits = [
                r
                for r in rows
                if r["bench"] == bench
                and r["circuit_sha256"].startswith(p["sha"])
                and r.get("qubits") == p["qubits"]
                and abs(r["cost"] - p["cost"]) <= 1
            ]
            assert hits, f"{bench} {p['label']}: no PASS full ledger row with sha {p['sha']}, Q and cost"
            if "toffoli" in p:
                assert any(r.get("toffolis") == p["toffoli"] for r in hits), p["label"]


def test_cost_model_numbers_are_consistent() -> None:
    d = learn_figures.load()
    ref = d["invsqrt"]["reference"]
    assert ref["cost"] / ref["qubits"] == pytest.approx(7988, abs=1)  # the page says C = 7,988
    r = d["meta"]["dqi_r_eps"]
    for p in d["dqi"]["points"]:
        assert p["cost"] / (p["qubits"] ** 2 * p["toffoli"]) == pytest.approx(r, abs=0.03)


def test_circuit_drawer_handles_every_gate_kind() -> None:
    gates = [("H", 0), ("X", 1), ("CX", 0, 1), ("CZ", 0, 2, {"cond": "m"}), ("CCX", 0, 1, 2), ("HMR", 2)]
    fig = draw(gates, ["a", "b", "c"], title="all kinds")
    assert len(fig.axes) == 1


def test_widget_data_module_is_current() -> None:
    path = learn_figures.WIDGET_DATA
    assert path.read_text(encoding="utf-8") == learn_figures.widget_data(), "run `make learn-figures`"


def test_pages_only_use_registered_widgets() -> None:
    registry = set(
        re.findall(r'^\s+"?([a-z-]+)"?: mount\w+,', (ROOT / "docs/javascripts/widgets.mjs").read_text(), re.M)
    )
    used = set()
    for page in LEARN.rglob("*.md"):
        used |= set(re.findall(r'data-widget="([a-z-]+)"', page.read_text()))
    assert registry == {"interference", "iso-cost", "mbuc", "dfthcsos"}
    assert used == registry


def test_primer_figure_numbers_add_up_and_appear_in_the_pages() -> None:
    d = learn_figures.load()["primers"]
    inv = d["invsqrt_reference_toffolis_per_direction"]
    assert sum(r[1] for r in inv) == d["invsqrt_sum_per_direction"]
    assert sum(r[1] for r in inv if r[2]) == 3423  # Horner plus the three Newton multiplications
    dqi = d["dqi_reference"]
    assert sum(v for _, v in dqi["stages"]) == dqi["total"]
    df = d["dfthcsos_baseline"]
    assert sum(v for _, v in df["t_parts"]) == df["t_total"]
    assert sum(v for _, v in df["q_parts"]) == df["q_total"]
    pages = {p.name: p.read_text() for p in LEARN.rglob("*.md")}
    for page, needles in (
        ("primer-invsqrt.md", ["3,871", "3,423", "1,071", "867"]),
        ("primer-dqi.md", ["5,725,461"]),
        ("primer-dfthcsos.md", ["93,237", "79,480", "13,757", "730", "544"]),
    ):
        for n in needles:
            assert n in pages[page], f"{page} no longer mentions {n}: update analysis/numbers/learn.json"


def test_adder_diagram_matches_the_real_circuit() -> None:
    km = pytest.importorskip("kickmix")
    gates, wires = learn_figures.adder_gates(4)
    bd = km.CircuitBuilder()  # the page's adder, built the same way
    a = bd.create_quantum_register(4, "a")
    b = bd.create_quantum_register(4, "b")
    c = bd.alloc_qubits(3)
    for i in range(3):
        if i:
            bd.cx(c[i - 1], a[i])
            bd.cx(c[i - 1], b[i])
        bd.init_and(a[i], b[i], c[i])
        if i:
            bd.cx(c[i - 1], c[i])
    bd.cx(a[3], b[3])
    bd.cx(c[2], b[3])
    for i in reversed(range(3)):
        if i:
            bd.cx(c[i - 1], c[i])
        bd.del_and(a[i], b[i], c[i])
        if i:
            bd.cx(c[i - 1], a[i])
        bd.cx(a[i], b[i])
    circuit = bd.finish_circuit()
    kinds = [g[0] for g in gates]
    assert kinds.count("CCX") == circuit.operation_statistics().num_toffoli_like == 3
    assert len(wires) == circuit.num_qubits == 11
    # kickmix counts init_and and del_and as two instructions each (allocate and AND; measure and fix)
    drawn = kinds.count("CX") + 2 * kinds.count("CCX") + kinds.count("HMR") + kinds.count("CZ")
    assert drawn == circuit.operation_statistics().num_instructions == 27
