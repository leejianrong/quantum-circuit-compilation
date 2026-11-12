"""Pure view models for the dashboard: no indah import, so they are tested without the extra.

Everything here is read from ledger/ through `bench.ledger`, `bench.experiments` and the selection
helpers in `bench.plots`. Three kinds of number are kept apart on purpose:

- ours: full-shot PASS rows of circuits we built, verified by the official verifier;
- public: the best cost a public source reports for a circuit; we did not verify it;
- leaderboard: what Kaggle scored for a submission.
"""

import pathlib
from dataclasses import dataclass
from datetime import datetime

from bench import experiments, ledger, plots

BENCHES = plots.BENCHES
THIRD_PARTY = ("public/", "public:", "data/", "/kaggle/input/")

Rows = list[list[float | None]]
Points = list[tuple[float, float]]


def is_own(r: ledger.Row) -> bool:
    """A run of a circuit we generated (not a public circuit or the host's baseline)."""
    return not r.circuit.startswith(THIRD_PARTY) and "/public/" not in r.circuit


def own_runs(rows: list[ledger.Row]) -> list[ledger.Row]:
    return [r for r in plots.verified(rows) if is_own(r) and r.bench in BENCHES]


def best_ours(rows: list[ledger.Row], bench: str) -> ledger.Row | None:
    runs = [r for r in own_runs(rows) if r.bench == bench and r.cost]
    return min(runs, key=lambda r: r.cost or 0.0) if runs else None


def ours_ratio(rows: list[ledger.Row], bench: str) -> float | None:
    r = best_ours(rows, bench)
    return plots.ratio(bench, r.cost) if r and r.cost else None


def score(ratios: list[float | None]) -> float | None:
    return plots.geomean([x for x in ratios if x]) if all(ratios) else None


@dataclass
class Summary:
    ours: dict[str, float | None]
    public: dict[str, float | None]
    ours_score: float | None
    public_score: float | None
    leaderboard_score: float | None
    leaderboard_n: int  # leaderboard rows seen (submissions, any status)

    @property
    def gap(self) -> float | None:
        """How many times the public frontier score is above ours."""
        return self.public_score / self.ours_score if self.public_score and self.ours_score else None


def summarize(rows: list[ledger.Row]) -> Summary:
    ours = {b: ours_ratio(rows, b) for b in BENCHES}
    public = {b: plots.frontier_ratio(rows, b) for b in BENCHES}
    lb = plots.leaderboard_points(rows)
    return Summary(
        ours=ours,
        public=public,
        ours_score=score(list(ours.values())),
        public_score=plots.frontier_score(rows),
        leaderboard_score=max((v for _, v in lb), default=None),
        leaderboard_n=sum(1 for r in rows if r.kind == "leaderboard"),
    )


# ---- ratio over time -------------------------------------------------------------------------

EPS = 0.01  # hours between the two points of one step edge


def hours(t: datetime, origin: datetime) -> float:
    return round((t - origin).total_seconds() / 3600, 3)


def own_points(rows: list[ledger.Row], bench: str) -> list[tuple[datetime, float]]:
    origin = plots.timeline_origin(rows)
    runs = [r for r in own_runs(rows) if r.bench == bench and r.cost]
    return sorted((plots.when(r, origin), plots.ratio(bench, r.cost or 0.0)) for r in runs)


def own_score_steps(rows: list[ledger.Row]) -> list[tuple[datetime, float]]:
    """Score of our best verified ratios, once all three benchmarks have one (staircase)."""
    origin = plots.timeline_origin(rows)
    events = sorted(
        (plots.when(r, origin), r.bench, plots.ratio(r.bench, r.cost or 0.0))
        for r in own_runs(rows)
        if r.cost
    )
    best: dict[str, float] = {}
    out: list[tuple[datetime, float]] = []
    for t, b, v in events:
        best[b] = max(best.get(b, 0.0), v)
        if len(best) == len(BENCHES):
            s = plots.geomean(list(best.values()))
            if not out or s > out[-1][1]:
                out.append((t, s))
    return out


def step_rows(series: list[Points], scatter: list[Points] | None = None, end: float | None = None) -> Rows:
    """Chart rows `[x, y_series..., y_scatter...]` drawing each series as a staircase.

    indah's Chart only joins points with straight segments, so a step is two points (just before the
    change at the old value, then at the new one) and the value is carried forward between events.
    When indah has `kind="step"` (leejianrong/indah#328) delete this and pass the raw points.
    """
    scatter = scatter or []
    xs = {x for s in series for x, _ in s} | {x for s in scatter for x, _ in s}
    if end is not None:
        xs.add(end)
    xs |= {x - EPS for s in series for x, _ in s[1:]}
    scat = [dict(s) for s in scatter]
    rows: Rows = []
    for x in sorted(xs):
        row: list[float | None] = [x]
        for s in series:
            seen = [y for sx, y in s if sx <= x]
            row.append(seen[-1] if seen else None)
        row.extend(d.get(x) for d in scat)
        rows.append(row)
    return rows


def _end(rows: list[ledger.Row], origin: datetime) -> float:
    stamps = [t for r in rows if (t := plots.parse_ts(r.ts))] or [origin]
    return hours(max(stamps), origin)


def progress_rows(rows: list[ledger.Row]) -> Rows:
    """Rows for the per-benchmark chart: our best-so-far ratio per benchmark, one column each."""
    origin = plots.timeline_origin(rows)
    series = [[(hours(t, origin), v) for t, v in plots.staircase(own_points(rows, b))] for b in BENCHES]
    return step_rows(series, end=_end(rows, origin))


def score_rows(rows: list[ledger.Row]) -> Rows:
    """Rows for the score chart: our staircase, then the leaderboard scores as dots."""
    origin = plots.timeline_origin(rows)
    ours = [(hours(t, origin), v) for t, v in own_score_steps(rows)]
    lb = [(hours(t, origin), v) for t, v in plots.leaderboard_points(rows)]
    return step_rows([ours], [lb], end=_end(rows, origin))


# ---- experiments ----------------------------------------------------------------------------


def experiment_table(
    rows: list[ledger.Row], exps: dict[str, experiments.Experiment]
) -> list[dict[str, object]]:
    """One row per experiment, newest first, joined to its verify runs in the ledger."""
    out: list[dict[str, object]] = []
    for e in exps.values():
        runs = [r for r in rows if r.experiment == e.id]
        passed = [r for r in plots.verified(runs) if r.cost]
        best = min(passed, key=lambda r: r.cost or 0.0, default=None)
        out.append(
            {
                "id": e.id,
                "benchmark": e.benchmark,
                "outcome": e.outcome or ("open" if e.status == "open" else "closed"),
                "hypothesis": e.hypothesis,
                "runs": len(runs),
                "failures": sum(1 for r in runs if r.status == "FAIL"),
                "best_cost": f"{best.cost:,.0f}" if best and best.cost else "-",
                "ratio": f"{plots.ratio(e.benchmark, best.cost):.2f}x" if best and best.cost else "-",
                "opened": e.opened,
                "notes": e.notes or "",
            }
        )
    return sorted(out, key=lambda r: str(r["opened"]), reverse=True)


def load(
    ledger_path: pathlib.Path = ledger.DEFAULT_LEDGER, exp_path: pathlib.Path = experiments.DEFAULT_LOG
) -> tuple[list[ledger.Row], dict[str, experiments.Experiment]]:
    rows = ledger.read(ledger_path) if ledger_path.exists() else []
    return rows, experiments.read(exp_path)
