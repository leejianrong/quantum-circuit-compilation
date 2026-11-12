"""The Cost explorer tab: sliders over the dfthcsos cost model (`dashboard.cost`)."""

import indah

from bench import plots
from dashboard import cost
from dfthcsos_model.model import QUBIT_CAP

OK = "var(--ok, #009E73)"
ERR = "var(--err, #CC3311)"


def _marks(values: dict[int, str]) -> list[dict[str, object]]:
    return [{"value": v, "label": label} for v, label in values.items()]


def cost_explorer() -> indah.Component:
    start = cost.PRESETS["Our 11-bit table"]
    R, B, C = (indah.Signal(float(v)) for v in (start.R, start.B, start.C))
    brot, J = indah.Signal(float(start.brot)), indah.Signal(float(start.J))
    loader, table = indah.Signal(start.loader), indah.Signal(start.table)

    def setting() -> cost.Setting:
        return cost.Setting(
            int(R.value), int(B.value), int(C.value), int(brot.value), int(J.value), loader.value, table.value
        )

    result = indah.computed(lambda: cost.evaluate(setting()))
    rows = indah.computed(lambda: cost.chart_rows(setting()))
    cliff_at = indah.computed(lambda: (c[0][1] - 0.5) if (c := cost.cliffs(setting())) else None)

    def load(s: cost.Setting) -> None:
        R.set(float(s.R))
        B.set(float(s.B))
        C.set(float(s.C))
        brot.set(float(s.brot))
        J.set(float(s.J))
        loader.set(s.loader)
        table.set(s.table)

    def preset(name: str) -> indah.Button:
        return indah.Button(name, lambda: load(cost.PRESETS[name]), variant="tonal")

    presets = indah.Row([preset(name) for name in cost.PRESETS], gap="0.5rem")

    def slider(sig: indah.Signal[float], label: str, lo: int, hi: int, marks: dict[int, str]) -> indah.Slider:
        return indah.Slider(
            sig, min=lo, max=hi, step=1, label=label, show_value=True, marks=_marks(marks), commit="release"
        )

    sliders = indah.Grid(
        [
            slider(R, "R: outer rank", 1, 80, {8: "8", 65: "65 baseline"}),
            slider(B, "B: rows per rank", 20, 300, {60: "60", 143: "143", 176: "176"}),
            slider(C, "C: columns", 10, 100, {44: "44", 56: "56", 60: "60"}),
            slider(brot, "brot: word width (bits)", 4, 16, {8: "8", 11: "11", 12: "12"}),
            slider(J, "J: words per loader circuit", 1, 30, {5: "5", 8: "8", 9: "9", 13: "13"}),
        ],
        columns=2,
        gap="0.75rem 1.5rem",
    )
    choices = indah.Row(
        [
            indah.Select(
                table,
                options=[(k, t.name) for k, t in cost.TABLES.items()],
                label="Table (Lambda, E_gap, measured errors)",
            ),
            indah.Segmented(
                loader,
                options=[
                    {"value": "own", "label": "Our unary loader"},
                    {"value": "public", "label": "Public loader (fixed counts)"},
                ],
                label="Loader",
            ),
        ],
        gap="1.5rem",
    )

    def fmt(value: float) -> str:
        return f"{value:,.0f}"

    stats = indah.Grid(
        [
            indah.Stat(lambda: fmt(result.value.breakdown.score), label="cost = lambda_eff x T x Q"),
            indah.Stat(
                lambda: f"{result.value.ratio:.2f}x",
                label="ratio vs baseline 3,355,599,588",
                delta=lambda: f"{result.value.vs_public:.2f}x the public cost",
            ),
            indah.Stat(lambda: f"{result.value.breakdown.lambda_eff:.2f}", label="lambda_eff"),
            indah.Stat(lambda: fmt(result.value.breakdown.t_total), label="T_total (Toffolis)"),
            indah.Stat(lambda: str(result.value.breakdown.q_total), label="Q_total (qubits)"),
        ],
        columns=5,
        gap="0.75rem",
    )
    status = indah.computed(lambda: result.value.gate.status)
    gate_row = indah.Row(
        [
            indah.Show(lambda: status.value == "pass", [indah.Badge("accuracy gates pass", tone="ok")]),
            indah.Show(
                lambda: status.value == "fail", [indah.Badge("accuracy gate FAILS: rejected", tone="err")]
            ),
            indah.Show(
                lambda: status.value == "not measured", [indah.Badge("gates not measured", tone="warn")]
            ),
            indah.Show(
                lambda: not result.value.cap_ok, [indah.Badge("over the 128-qubit cap: rejected", tone="err")]
            ),
            indah.Text(
                lambda: f"{result.value.gate.basis} - {result.value.gate.detail}".lstrip(" -"),
                variant="caption",
            ),
        ],
        gap="0.75rem",
    )

    def breakdown() -> str:
        r = result.value
        b = r.breakdown
        steps = ", ".join(f"{lo} to {hi}" for lo, hi in cost.cliffs(r.setting)) or "none"
        return (
            f"**T_total** {fmt(b.t_total)} = angle loader {fmt(b.t_angles)} "
            f"+ state preparation {fmt(b.t_prep)} "
            f"+ Givens {fmt(b.t_givens)}.  **Q_total** {b.q_total} = persistent {b.q_persistent_prep} "
            f"+ words {b.q_words} + workspace {b.q_temp} (set by the {b.q_temp_source} stage).\n\n"
            f"Loader circuit: {r.angles.qubits} qubits (cap {QUBIT_CAP}), inner QROAM block exponent "
            f"{b.prep.inner_k}. Q_total steps up between widths {steps} for this shape "
            "(the vertical line)."
        )

    chart = indah.Chart(
        rows,
        series=[
            {"label": "cost at your J (clamped to 128 qubits)", "stroke": plots.COLORS["dqi"], "width": 3},
            {"label": "cost at the largest J that fits", "stroke": plots.COLORS["invsqrt"], "dash": [6, 4]},
            {"label": "your setting", "stroke": plots.COLORS["dfthcsos"], "kind": "scatter", "size": 12},
        ],
        title="Cost against word width (log scale; lower is better)",
        x_label="brot: bits per word",
        y_label="lambda_eff x T_total x Q_total",
        y_scale="log",
        x_range=(4, 16),
        y_range=(1e8, 1e11),
        playhead=cliff_at,
        rules=[
            {
                "y": cost.BASELINE_COST,
                "label": "baseline 3.36e9 (1.00x)",
                "color": plots.COLORS["leaderboard"],
            },
            {"y": cost.PUBLIC_COST, "label": "public 3.00e8 (11.20x)", "color": plots.COLORS["frontier"]},
        ],
        bands=[
            {
                "x0": 4,
                "x1": 10.5,
                "label": "our table: error_2 above 0.02 below 11 bits",
                "color": ERR,
                "alpha": 0.08,
            }
        ],
        markers=[{"x": b, "y": c, "label": label, "color": OK} for b, c, label in cost.VERIFIED],
        points=True,
        height=380,
    )
    return indah.Column(
        [
            indah.Text(
                "The score is `lambda_eff x T_total x Q_total`, computed with the exact cost model "
                "(`dfthcsos_model`), not a simulation. Pick a preset or drag a slider; the heavy "
                "recompute runs once when you release it. Green dots are costs the official verifier "
                "confirmed. The red band is where our own table fails the accuracy gate, which is the "
                "cliff: below 11 bits the words are too coarse.",
                markdown=True,
            ),
            presets,
            indah.Card([sliders, choices], title="Settings"),
            stats,
            gate_row,
            chart,
            indah.Card([indah.Text(breakdown, markdown=True)], title="Where the cost comes from"),
        ],
        gap="1rem",
    )
