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
Points = list[tuple[float, float]]


def own_runs(rows: list[ledger.Row]) -> list[ledger.Row]:
    return [r for r in plots.own_runs(rows) if r.bench in BENCHES]


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
#
# The app aligns these with `indah.chart_rows` and draws them as `kind="step"` series (indah#328);
# nothing here knows about indah.


def hours(t: datetime, origin: datetime) -> float:
    return round((t - origin).total_seconds() / 3600, 3)


def _end(rows: list[ledger.Row], origin: datetime) -> float:
    stamps = [t for r in rows if (t := plots.parse_ts(r.ts))] or [origin]
    return hours(max(stamps), origin)


def _held(points: Points, end: float) -> Points:
    """A step series holds each value until the next point; give the last value a point at `end`."""
    return points + [(max(end, points[-1][0]), points[-1][1])] if points else []


def progress_series(rows: list[ledger.Row]) -> dict[str, Points]:
    """Our best-so-far ratio per benchmark, as points of a staircase (hours since the origin)."""
    origin = plots.timeline_origin(rows)
    end = _end(rows, origin)
    return {
        b: _held([(hours(t, origin), v) for t, v in plots.staircase(plots.run_points(rows, b))], end)
        for b in BENCHES
    }


def score_series(rows: list[ledger.Row]) -> dict[str, Points]:
    """Our score staircase and the leaderboard scores (dots)."""
    origin = plots.timeline_origin(rows)
    ours = [(hours(t, origin), v) for t, v in plots.score_staircase(rows)]
    lb = [(hours(t, origin), v) for t, v in plots.leaderboard_points(rows)]
    return {"ours": _held(ours, _end(rows, origin)), "leaderboard": lb}


def failure_hours(rows: list[ledger.Row]) -> list[float]:
    """When verifier failures happened, for vertical rules (at most the latest 12 are drawn)."""
    origin = plots.timeline_origin(rows)
    return sorted({hours(plots.when(r, origin), origin) for r in plots.failures(rows)})


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
