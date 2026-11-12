"""The dashboard app (indah). Reads ledger/ only. Run with `make dashboard`.

`build_app` returns the root component; `main` serves it on the first free port. Each tab is one
function returning a component, so adding a tab is one line in `TABS`.
"""

import pathlib
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import indah
from starlette.applications import Starlette

from bench import experiments, ledger, plots
from dashboard import cost_view, data, lineage_view, runs_view

OURS = plots.COLORS["score"]
PUBLIC = plots.COLORS["frontier"]
LEADERBOARD = plots.COLORS["leaderboard"]
OUTCOME_TONES = {
    "promoted": "ok",
    "rejected": "warn",
    "failed": "err",
    "abandoned": "neutral",
    "open": "info",
    "closed": "neutral",
}


def fx(v: float | None) -> str:
    return "-" if v is None else f"{v:.2f}x"


# ---- scoreboard ------------------------------------------------------------------------------


def _card(title: str, badge: str, tone: str, stats: list[indah.Component], note: str) -> indah.Component:
    head = indah.Row([indah.Badge(badge, tone=tone)], gap="0.5rem")
    return indah.Card(
        [head, indah.Grid(stats, columns=2, gap="0.75rem"), indah.Text(note, variant="caption")],
        title=title,
    )


def story(s: data.Summary) -> str:
    if s.gap is None:
        return "No verified score yet: the score needs a verified run of all three benchmarks."
    lead = (
        f"Our best verified score is **{fx(s.ours_score)}**. The public frontier reports "
        f"**{fx(s.public_score)}** (not verified by us), {s.gap:.1f}x above us"
    )
    if s.leaderboard_score:
        lead += f"; the leaderboard shows **{s.leaderboard_score:.2f}**"
    return lead + ". The work is closing that gap with circuits we generated ourselves."


def scoreboard(rows: list[ledger.Row]) -> indah.Component:
    s = data.summarize(rows)

    def behind(ours: float | None, pub: float | None) -> str | None:
        return f"-{pub / ours:.1f}x behind public" if ours and pub else None

    ours_stats: list[Any] = [
        indah.Stat(fx(s.ours_score), label="Score (geo. mean)", delta=behind(s.ours_score, s.public_score))
    ] + [indah.Stat(fx(s.ours[b]), label=b, delta=behind(s.ours[b], s.public[b])) for b in data.BENCHES]
    pub_stats: list[Any] = [indah.Stat(fx(s.public_score), label="Score (geo. mean)")] + [
        indah.Stat(fx(s.public[b]), label=b) for b in data.BENCHES
    ]
    lb_stats: list[Any] = [
        indah.Stat("-" if s.leaderboard_score is None else f"{s.leaderboard_score:.2f}", label="Best score"),
        indah.Stat(str(s.leaderboard_n), label="Submissions"),
    ]
    cards = indah.Grid(
        [
            _card(
                "Ours (verified)",
                "official verifier, full shots",
                "ok",
                ours_stats,
                "Circuits we generated, best worst-salt cost per benchmark.",
            ),
            _card(
                "Public reference (unverified)",
                "reported by the source",
                "warn",
                pub_stats,
                "Best public cost per benchmark, as reported. We have not verified these.",
            ),
            _card(
                "Leaderboard",
                "scored by Kaggle",
                "info",
                lb_stats,
                "What Kaggle gave our submissions. A submission may hold public circuits.",
            ),
        ],
        columns=3,
    )
    return indah.Column(
        [
            indah.Text(story(s), markdown=True),
            cards,
            score_chart(rows, s),
            ratio_chart(rows, s),
            log_view(rows),
        ],
        gap="1.25rem",
    )


def score_chart(rows: list[ledger.Row], s: data.Summary) -> indah.Component:
    rules = (
        [
            {
                "y": s.public_score,
                "label": f"public reference (unverified) {s.public_score:.1f}x",
                "color": PUBLIC,
            }
        ]
        if s.public_score
        else []
    )
    return indah.Chart(
        data.score_rows(rows),
        series=[
            {"label": "ours (verified)", "stroke": OURS, "width": 3},
            {"label": "leaderboard", "stroke": LEADERBOARD, "kind": "scatter", "size": 10},
        ],
        title="Score over time (higher is better)",
        x_label=x_label(rows),
        y_label="score (geo. mean of ratios)",
        rules=rules,
        points=True,
        height=280,
    )


def ratio_chart(rows: list[ledger.Row], s: data.Summary) -> indah.Component:
    top = max([v for v in s.public.values() if v] + [1.0])
    rules = [
        {"y": v, "label": f"{b} public reference {v:.1f}x", "color": plots.COLORS[b]}
        for b in data.BENCHES
        if (v := s.public[b])
    ]
    return indah.Chart(
        data.progress_rows(rows),
        series=[{"label": f"{b} (ours)", "stroke": plots.COLORS[b], "width": 3} for b in data.BENCHES],
        title="Ratio per benchmark, ours (solid) against the public reference (dashed)",
        x_label=x_label(rows),
        y_label="baseline cost / cost",
        rules=rules,
        y_range=(0, 1.1 * top),  # rules do not stretch the axis
        points=True,
        height=320,
    )


def x_label(rows: list[ledger.Row]) -> str:
    return f"hours since {plots.timeline_origin(rows):%Y-%m-%d %H:%M} UTC (undated runs sit at 0)"


def log_view(rows: list[ledger.Row]) -> indah.Component:
    """The same story on log axes, drawn on the server: Chart has no log scale yet (indah#328)."""
    try:
        png = _progress_png(rows)
    except ImportError:
        return indah.Text("Install the plots extra for the log-scale view.", variant="caption")
    return indah.Expander(
        [indah.Image(png, alt="Score and ratio over time on log axes")], label="Log-scale view", open=False
    )


def _progress_png(rows: list[ledger.Row]) -> bytes:
    with tempfile.TemporaryDirectory() as d:
        return plots.render_progress(rows, pathlib.Path(d)).read_bytes()


# ---- experiments -----------------------------------------------------------------------------


def experiments_tab(rows: list[ledger.Row], exps: dict[str, experiments.Experiment]) -> indah.Component:
    table_rows = data.experiment_table(rows, exps)
    by_id = {str(r["id"]): r for r in table_rows}
    chosen: indah.Signal[str | None] = indah.Signal(None)

    def detail() -> str:
        r = by_id.get(chosen.value or "")
        if r is None:
            return "Select an experiment to read its hypothesis and notes."
        runs = [x for x in rows if x.experiment == r["id"]]
        lines = [f"**{r['id']}** ({r['benchmark']}, {r['outcome']})", "", f"*Hypothesis:* {r['hypothesis']}"]
        if r["notes"]:
            lines += ["", f"*Notes:* {r['notes']}"]
        lines += ["", f"{len(runs)} verify runs linked, {r['failures']} failed."]
        return "\n".join(lines)

    table = indah.Table(
        rows=table_rows,
        key="id",
        selected=chosen,
        search=True,
        page_size=15,
        columns=[
            indah.Col("id", title="Id", kind="mono", width="6ch"),
            indah.Col("benchmark", title="Bench", width="10ch"),
            indah.Col("outcome", title="Outcome", kind="badge", tones=OUTCOME_TONES, width="11ch"),
            indah.Col("hypothesis", title="Hypothesis", truncate=True, max_width="60ch"),
            indah.Col("runs", title="Runs", kind="number", width="6ch"),
            indah.Col("failures", title="Failed", kind="number", width="7ch"),
            indah.Col("best_cost", title="Best verified cost", kind="mono"),
            indah.Col("ratio", title="Ratio", kind="mono", width="9ch"),
            indah.Col("opened", title="Opened", kind="time", width="9ch"),
        ],
    )
    n_closed = sum(1 for r in table_rows if r["outcome"] not in ("open", "closed"))
    return indah.Column(
        [
            indah.Text(
                f"{len(table_rows)} experiments, {n_closed} with an outcome. Rejected and failed ones stay: "
                "they are how we know what not to try again.",
            ),
            table,
            indah.Card([indah.Text(detail, markdown=True)], title="Detail"),
        ],
        gap="1rem",
    )


# ---- lineage ---------------------------------------------------------------------------------


def lineage_tab(lin: dict[str, Any]) -> indah.Component:
    nodes, edges = lineage_view.graph(lin)
    chosen: indah.Signal[str | None] = indah.Signal(None)
    mine = indah.Signal(False)
    ours = lineage_view.ours_ids(lin)
    # Graph.highlight dims everything else; when indah has node styles this can become a plain flag.
    highlight = indah.computed(
        lambda: (
            {"nodes": ours + [e["source"] for e in lin["edges"] if e["target"] in ours]} if mine.value else {}
        )
    )
    return indah.Column(
        [
            indah.Text(
                "Where each circuit came from, read left to right: the host baseline, public circuits and "
                "their ancestors, then the generators we wrote ourselves (green, large). Red nodes have a "
                "no-licence ancestor and say NO LICENCE. Green edges are ideas we learned and rewrote, "
                "not copied.",
            ),
            indah.Switch(mine, label="Highlight our generators and what we learned from"),
            indah.Graph(
                nodes,
                edges,
                layout="given",
                height=640,
                selected=chosen,
                highlight=highlight,
                legend=False,
                label="Lineage",
            ),
            indah.Image(
                lineage_view.legend_svg(), alt="Legend: baseline, public circuit, ancestor, ours, no licence"
            ),
            indah.Card(
                [indah.Text(lambda: lineage_view.detail(lin, chosen.value), markdown=True)], title="Detail"
            ),
        ],
        gap="1rem",
    )


# ---- app -------------------------------------------------------------------------------------


@dataclass
class Inputs:
    rows: list[ledger.Row]
    exps: dict[str, experiments.Experiment]
    lineage: dict[str, Any]


Tab = Callable[[Inputs], indah.Component]
TABS: list[tuple[str, Tab]] = [
    ("Scoreboard", lambda i: scoreboard(i.rows)),
    ("Experiments", lambda i: experiments_tab(i.rows, i.exps)),
    ("Lineage", lambda i: lineage_tab(i.lineage)),
    ("Cost explorer", lambda i: cost_view.cost_explorer()),
    ("Anatomy", lambda i: runs_view.anatomy_tab(i.rows)),
    ("Verifier theatre", lambda i: runs_view.theatre_tab(i.rows)),
]


def build_app(
    ledger_path: pathlib.Path = ledger.DEFAULT_LEDGER,
    exp_path: pathlib.Path = experiments.DEFAULT_LOG,
    lineage_path: pathlib.Path = lineage_view.LINEAGE,
) -> indah.Component:
    rows, exps = data.load(ledger_path, exp_path)
    inputs = Inputs(rows, exps, lineage_view.load(lineage_path))
    return indah.Column(
        [
            indah.Text("Quantum circuit compilation", variant="title"),
            indah.Tabs([build(inputs) for _, build in TABS], labels=[name for name, _ in TABS]),
        ],
        gap="1rem",
    )


def create(
    ledger_path: pathlib.Path = ledger.DEFAULT_LEDGER,
    exp_path: pathlib.Path = experiments.DEFAULT_LOG,
    lineage_path: pathlib.Path = lineage_view.LINEAGE,
) -> Starlette:
    return indah.create_app(
        # a factory: each viewer gets their own tab state and the ledger is re-read on connect
        session_factory=lambda: indah.Session(build_app(ledger_path, exp_path, lineage_path)),
        title="QCC dashboard",
        max_width="1200px",
    )


def main() -> None:
    indah.launch(create())  # first free port from 8000; prints the URL


if __name__ == "__main__":
    main()
