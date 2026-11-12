"""The Anatomy and Verifier theatre tabs (view models in `dashboard.runs`)."""

import indah

from bench import ledger, plots
from dashboard import runs

OUTCOME = {"PASS": "ok", "FAIL": "err"}
BAD = "var(--err, #CC3311)"
GOOD = "var(--ok, #009E73)"


def _empty(text: str) -> indah.Component:
    return indah.Text(text, variant="caption")


# ---- anatomy ---------------------------------------------------------------------------------


def anatomy_tab(rows: list[ledger.Row]) -> indah.Component:
    items = runs.anatomy_runs(rows)[::-1]
    flame_key = indah.Signal(next(iter(runs.FLAME_PRESETS)))
    flame_card = indah.Card(
        [
            indah.Text(
                lambda: (
                    runs.FLAME_PRESETS[flame_key.value].note + " Wide blue bars are Toffoli cost, red "
                    "bars are the `mark` blocks (stages) of the generator."
                ),
                markdown=True,
            ),
            indah.Select(
                flame_key,
                options=[(k, p.label) for k, p in runs.FLAME_PRESETS.items()],
                label="Generator instance",
            ),
            indah.Image(
                lambda: _flame_src(flame_key.value), alt="kickmix flame chart of the generator circuit"
            ),
        ],
        title="Flame chart (rebuilt from our generator in under a second)",
    )
    if not items:
        return indah.Column(
            [
                _empty("No ledger entry has structure fields yet (run `bench verify` with a v2 ledger)."),
                flame_card,
            ],
            gap="1rem",
        )
    chosen = indah.Signal(
        str(next((i for i, r in enumerate(items) if r.stage_shares), 0))
    )  # a run with marks
    by_index = {str(i): r for i, r in enumerate(items)}

    def current() -> ledger.Row:
        return by_index.get(chosen.value, items[0])

    def fact(key: str) -> object:
        return lambda: runs.structure_facts(current())[key]

    stats = indah.Grid(
        [
            indah.Stat(fact("toffolis"), label="Toffolis (static count)"),
            indah.Stat(fact("qubits"), label="Qubits"),
            indah.Stat(fact("depth"), label="Reaction depth"),
            indah.Stat(fact("cost"), label="Official cost (worst salt)"),
            indah.Stat(fact("ratio"), label="Ratio vs baseline"),
        ],
        columns=5,
        gap="0.75rem",
    )
    table = indah.computed(lambda: runs.stage_table(current()))
    has_shares = indah.computed(lambda: bool(table.value))
    slices = indah.computed(lambda: [{"label": t["stage"], "value": t["share"]} for t in table.value])
    shares = indah.Show(
        has_shares,
        [
            indah.Grid(
                [
                    indah.Pie(slices, height=220, label="Share of the Toffoli cost by stage"),
                    indah.Table(
                        rows=table,
                        key="stage",
                        columns=[
                            indah.Col("stage", title="Stage", kind="mono"),
                            indah.Col("share", title="Share of cost (%)", kind="number"),
                        ],
                    ),
                ],
                columns=2,
                gap="1rem",
            )
        ],
    )
    no_shares = indah.Show(
        lambda: not has_shares.value,
        [_empty("This circuit has no `mark` blocks, so the ledger has no stage shares for it.")],
    )
    return indah.Column(
        [
            indah.Text(
                "What a circuit is made of. Pick a verified run: totals and stage shares come from the "
                "ledger. The flame chart below is rebuilt from our generator at a small size, because the "
                "full circuits take minutes to build.",
            ),
            indah.Select(
                chosen,
                options=[(str(i), runs.option_label(r)) for i, r in enumerate(items)],
                label="Ledger entry",
            ),
            stats,
            indah.Card([shares, no_shares], title="Stage shares"),
            flame_card,
        ],
        gap="1rem",
    )


def _flame_src(key: str) -> str:
    out = runs.flame(key)
    return runs.data_uri(out[0]) if out else ""


# ---- verifier theatre ------------------------------------------------------------------------


def theatre_tab(rows: list[ledger.Row]) -> indah.Component:
    items = runs.verify_runs(rows)
    if not items:
        return _empty("No verifier runs in the ledger yet.")
    fails = [i for i, r in enumerate(items) if r.status == "FAIL"]
    start = fails[-1] if fails else max(range(len(items)), key=lambda i: (items[i].salts, i))
    chosen: indah.Signal[str | None] = indah.Signal(str(start))

    def current() -> ledger.Row:
        return items[int(chosen.value or start)]

    verdict = indah.computed(lambda: runs.verdict(current()))
    table = indah.Table(
        rows=runs.run_table(items),
        key="id",
        selected=chosen,
        page_size=8,
        search=True,
        columns=[
            indah.Col("bench", title="Bench", width="10ch"),
            indah.Col("run", title="Run", kind="mono"),
            indah.Col("kind", title="Kind", width="8ch"),
            indah.Col("status", title="Verdict", kind="badge", tones=OUTCOME, width="9ch"),
            indah.Col("salts", title="Salts", kind="number", width="7ch"),
            indah.Col("failed", title="Failed", kind="number", width="8ch"),
            indah.Col("cost", title="Cost that counts", kind="mono"),
            indah.Col("when", title="When", kind="time", width="9ch"),
        ],
    )
    ok = indah.Show(lambda: verdict.value[1] == "ok", [indah.Badge(lambda: verdict.value[0], tone="ok")])
    rejected = indah.Show(
        lambda: verdict.value[1] == "err", [indah.Badge(lambda: verdict.value[0], tone="err")]
    )
    strip = indah.BarStrip(
        lambda: runs.ticks(current()),
        height=56,
        tones=["ok", "err"],
        names=["pass", "fail"],
        labels=lambda: [f"salt {i}" for i in range(current().salts)],
        label="One tick per salt: green passed, red failed",
    )
    chart = indah.Chart(
        lambda: runs.spread_rows(current()),
        series=[
            {"label": "this salt", "stroke": plots.COLORS["dqi"], "kind": "scatter", "size": 9},
            {
                "label": "worst so far (the last step counts)",
                "stroke": plots.COLORS["invsqrt"],
                "kind": "step",
                "width": 2,
            },
            {"label": "salt that sets the cost", "stroke": BAD, "kind": "scatter", "size": 15},
        ],
        title="Cost of each salt against the best salt, and the running worst",
        x_label="salt",
        y_label="% above the best salt",
        points=True,
        height=300,
    )
    return indah.Column(
        [
            indah.Text(
                "The official verifier runs every salt and the score is the worst one; a single failing salt "
                "rejects the whole submission. Pick a run to replay it: one tick per salt, then the cost "
                "each salt produced. A rejected run is selected first when the ledger has one.",
            ),
            table,
            indah.Row([ok, rejected], gap="0.5rem"),
            strip,
            indah.Text(lambda: runs.spread_facts(current()), variant="caption"),
            indah.Show(
                lambda: bool(current().error),
                [indah.Text(lambda: f"Verifier said: {current().error}", variant="mono", tone="err")],
            ),
            indah.Show(lambda: bool(runs.spread_rows(current())), [chart]),
        ],
        gap="1rem",
    )
