"""`bench plots`: static PNGs drawn from ledger/ only (docs/MEASUREMENT.md).

The data selection helpers are pure and need no matplotlib; only `render_*` import it (optional extra
`plots`). Every plot says "no data yet" instead of failing on an empty or tiny ledger.
"""

import argparse
import importlib
import math
import pathlib
import random
from datetime import UTC, datetime, timedelta
from typing import Any

from bench import ledger

BENCHES = ("invsqrt", "dqi", "dfthcsos")
# Baseline (reference) costs from docs/PROVENANCE.md; score = geometric mean of baseline / cost.
BASELINES = {"invsqrt": 2076774.23, "dqi": 24439463583672.9, "dfthcsos": 3355599588.32}
# Okabe-Ito colour-blind-safe palette; readable on a white background.
COLORS = {
    "invsqrt": "#0072B2",
    "dqi": "#D55E00",
    "dfthcsos": "#009E73",
    "score": "#222222",
    "fail": "#CC3311",
    "frontier": "#7A7A7A",
    "leaderboard": "#CC79A7",
}
DEFAULT_OUT = pathlib.Path("out/plots")


def _plt() -> Any:
    mpl = importlib.import_module("matplotlib")
    mpl.use("Agg")
    plt = importlib.import_module("matplotlib.pyplot")
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.grid": True,
            "grid.color": "#dddddd",
            "grid.linewidth": 0.6,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "font.size": 10,
            "axes.titlesize": 11,
            "legend.frameon": False,
        }
    )
    return plt


# ---- pure data selection ---------------------------------------------------------------------


def verified(rows: list[ledger.Row]) -> list[ledger.Row]:
    """Full-shot PASS rows with a cost: what we may call verified (reduced-shot runs never count)."""
    return [
        r for r in rows if r.status == "PASS" and r.cost and not r.reduced_shots and r.kind in (None, "full")
    ]


def failures(rows: list[ledger.Row]) -> list[ledger.Row]:
    return [r for r in rows if r.status == "FAIL" and r.kind in (None, "full", "screen", "leaderboard")]


def parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    t = datetime.fromisoformat(ts)
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def timeline_origin(rows: list[ledger.Row]) -> datetime:
    """Where undated (schema 1) rows are drawn: half a day before the earliest timestamp."""
    dated = [t for r in rows if (t := parse_ts(r.ts))]
    return (min(dated) if dated else datetime(2026, 1, 1, tzinfo=UTC)) - timedelta(hours=12)


def when(r: ledger.Row, origin: datetime) -> datetime:
    return parse_ts(r.ts) or origin


def ratio(bench: str, cost: float) -> float:
    return BASELINES[bench] / cost


def run_points(rows: list[ledger.Row], bench: str) -> list[tuple[datetime, float]]:
    """(time, ratio) per verified run of one benchmark, oldest first."""
    origin = timeline_origin(rows)
    pts = [(when(r, origin), ratio(bench, r.cost)) for r in verified(rows) if r.bench == bench and r.cost]
    return sorted(pts)


def staircase(points: list[tuple[datetime, float]]) -> list[tuple[datetime, float]]:
    """Best-so-far over time; only the steps where the best improves."""
    best, out = 0.0, []
    for t, v in sorted(points):
        if v > best:
            best = v
            out.append((t, v))
    return out


def frontier_ratio(rows: list[ledger.Row], bench: str) -> float | None:
    """Best public reference ratio for a benchmark (unverified by us)."""
    costs = [r.cost for r in rows if r.kind == "public-reference" and r.bench == bench and r.cost]
    return ratio(bench, min(costs)) if costs else None


def geomean(values: list[float]) -> float:
    return math.exp(sum(math.log(v) for v in values) / len(values))


def score_staircase(rows: list[ledger.Row]) -> list[tuple[datetime, float]]:
    """Geometric-mean score of our best verified ratios, once all three benchmarks have one."""
    origin = timeline_origin(rows)
    events = sorted(
        (when(r, origin), r.bench, ratio(r.bench, r.cost))
        for r in verified(rows)
        if r.bench in BASELINES and r.cost
    )
    best: dict[str, float] = {}
    out: list[tuple[datetime, float]] = []
    for t, b, v in events:
        best[b] = max(best.get(b, 0.0), v)
        if len(best) == len(BASELINES):
            score = geomean(list(best.values()))
            if not out or score > out[-1][1]:
                out.append((t, score))
    return out


def frontier_score(rows: list[ledger.Row]) -> float | None:
    rs = [frontier_ratio(rows, b) for b in BENCHES]
    return geomean([x for x in rs if x]) if all(rs) else None


def leaderboard_points(rows: list[ledger.Row]) -> list[tuple[datetime, float]]:
    return sorted(
        (t, r.leaderboard_score)
        for r in rows
        if r.kind == "leaderboard" and r.leaderboard_score is not None and (t := parse_ts(r.ts))
    )


def salt_groups(rows: list[ledger.Row]) -> list[tuple[str, list[float]]]:
    """One (label, salt costs) per verified circuit, keeping the run with the most salts."""
    best: dict[tuple[str, str], ledger.Row] = {}
    for r in verified(rows):
        costs = r.salt_costs or r.costs
        key = (r.bench, r.circuit_sha256)
        if costs and (key not in best or len(costs) > len(best[key].salt_costs or best[key].costs)):
            best[key] = r

    def order(item: tuple[tuple[str, str], ledger.Row]) -> tuple[int, str]:
        b, sha = item[0]
        return (BENCHES.index(b) if b in BENCHES else len(BENCHES), sha)

    return [
        (f"{b}\n{sha[:8]}\nn={len(r.salt_costs or r.costs)}", list(r.salt_costs or r.costs))
        for (b, sha), r in sorted(best.items(), key=order)
    ]


def spread_pct(costs: list[float]) -> list[float]:
    """Each salt's cost relative to the circuit's best salt, in percent."""
    lo = min(costs)
    return [(c / lo - 1) * 100 for c in costs]


# ---- drawing -----------------------------------------------------------------------------------


def _no_data(ax: Any, msg: str = "no data yet") -> None:
    ax.text(0.5, 0.5, msg, ha="center", va="center", transform=ax.transAxes, color="#777777", fontsize=11)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)


def _scale_y(ax: Any, values: list[float]) -> None:
    """Log axis when values span decades; explicit limits so a single value still shows its neighbours."""
    if not values:
        return
    if min(values) > 0 and max(values) / min(values) >= 10:
        ax.set_yscale("log")
    ax.set_ylim(min(values) / 1.25, max(values) * 1.25)
    ax.ticklabel_format(axis="y", useOffset=False, style="plain") if ax.get_yscale() == "linear" else None


def _date_axis(ax: Any, times: list[datetime]) -> None:
    mdates = importlib.import_module("matplotlib.dates")
    loc = mdates.AutoDateLocator(minticks=3, maxticks=5)
    ax.xaxis.set_major_locator(loc)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc))
    lo, hi = min(times), max(times)
    pad = max((hi - lo) * 0.08, timedelta(hours=6))
    ax.set_xlim(lo - pad, hi + pad)


def _save(fig: Any, out: pathlib.Path, name: str) -> pathlib.Path:
    out.mkdir(parents=True, exist_ok=True)
    path = out / name
    fig.savefig(path, dpi=150)
    importlib.import_module("matplotlib.pyplot").close(fig)
    return path


def render_progress(rows: list[ledger.Row], out: pathlib.Path) -> pathlib.Path:
    """Score and per-benchmark ratio over time: verified staircase, public frontier dashed."""
    plt = _plt()
    lines = importlib.import_module("matplotlib.lines")
    fig, axes = plt.subplots(2, 2, figsize=(11, 7.8))
    origin = timeline_origin(rows)
    all_times = [origin] + [t for r in rows if (t := parse_ts(r.ts))]
    fail_rows = failures(rows)
    end = max(all_times)

    def mark_failures(ax: Any, bench: str | None) -> None:
        ts = [when(r, origin) for r in fail_rows if bench is None or r.bench in (bench, "all")]
        if ts:
            ax.plot(
                ts,
                [0.02] * len(ts),
                "x",
                color=COLORS["fail"],
                ms=8,
                mew=2,
                transform=ax.get_xaxis_transform(),
                clip_on=False,
            )

    ax = axes[0][0]
    ax.set_title("Score (geometric mean of ratios)")
    sc, fs, lb = score_staircase(rows), frontier_score(rows), leaderboard_points(rows)
    ys = [v for _, v in sc] + ([fs] if fs else []) + [v for _, v in lb]
    if ys:
        if sc:
            ax.step(
                [t for t, _ in sc] + [end],
                [v for _, v in sc] + [sc[-1][1]],
                where="post",
                color=COLORS["score"],
                lw=2,
            )
            ax.plot([t for t, _ in sc], [v for _, v in sc], "o", color=COLORS["score"])
        if fs:
            ax.axhline(fs, color=COLORS["frontier"], ls="--", lw=1.5)
        if lb:
            ax.plot(
                [t for t, _ in lb], [v for _, v in lb], "D", color=COLORS["leaderboard"], ms=8, mec="white"
            )
            for t, v in lb:
                ax.annotate(
                    f"{v:.2f}", (t, v), textcoords="offset points", xytext=(-6, 8), ha="right", fontsize=9
                )
        mark_failures(ax, None)
        _scale_y(ax, ys)
        _date_axis(ax, all_times)
        ax.set_ylabel("score (baseline cost / cost, geo. mean, x)")
    else:
        _no_data(ax, "no data yet\n(needs a verified run of all three benchmarks,\nor a leaderboard row)")

    for ax, bench in zip((axes[0][1], axes[1][0], axes[1][1]), BENCHES, strict=True):
        ax.set_title(bench)
        pts, fr = run_points(rows, bench), frontier_ratio(rows, bench)
        if not pts and not fr:
            _no_data(ax)
            continue
        col = COLORS[bench]
        if pts:
            st = staircase(pts)
            ax.step(
                [t for t, _ in st] + [end], [v for _, v in st] + [st[-1][1]], where="post", color=col, lw=2
            )
            ax.plot([t for t, _ in pts], [v for _, v in pts], "o", color=col)
        if fr:
            ax.axhline(fr, color=COLORS["frontier"], ls="--", lw=1.5)
        mark_failures(ax, bench)
        _scale_y(ax, [v for _, v in pts] + ([fr] if fr else []))
        _date_axis(ax, all_times)
        ax.set_ylabel("ratio (baseline cost / cost, x)")

    handles = [
        lines.Line2D([], [], color=COLORS["score"], lw=2, marker="o", label="ours, verified (best so far)"),
        lines.Line2D([], [], color=COLORS["frontier"], ls="--", lw=1.5, label="public frontier (unverified)"),
        lines.Line2D([], [], color=COLORS["leaderboard"], marker="D", ls="", label="leaderboard score"),
        lines.Line2D([], [], color=COLORS["fail"], marker="x", ls="", mew=2, label="failed run"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=4, bbox_to_anchor=(0.5, 0.025))
    fig.suptitle("Progress over time (higher is better)", fontweight="bold")
    fig.text(
        0.99,
        0.005,
        "runs without a timestamp (schema 1) sit at the left edge",
        ha="right",
        fontsize=8,
        color="#777777",
    )
    fig.tight_layout(rect=(0, 0.07, 1, 0.97))
    return _save(fig, out, "progress.png")


def render_salt_spread(rows: list[ledger.Row], out: pathlib.Path) -> pathlib.Path:
    """Strip plot of per-salt cost relative to the best salt, per verified circuit."""
    plt = _plt()
    groups = salt_groups(rows)
    fig, ax = plt.subplots(figsize=(max(7.0, 1.1 * len(groups) + 3), 5))
    ax.set_title("Salt spread per verified circuit (the worst salt is what counts)")
    if not groups:
        _no_data(ax)
        return _save(fig, out, "salt_spread.png")
    rng = random.Random(0)
    top = 0.0
    for i, (label, costs) in enumerate(groups):
        col = COLORS.get(label.split("\n")[0], "#444444")
        ys = spread_pct(costs)
        top = max(top, max(ys))
        xs = [i + rng.uniform(-0.18, 0.18) for _ in ys]
        ax.plot(xs, ys, "o", color=col, alpha=0.75, ms=6, mec="white")
        worst = max(range(len(ys)), key=ys.__getitem__)
        ax.plot([xs[worst]], [ys[worst]], "o", mfc="none", mec="black", ms=12, mew=1.4)
    ax.set_xticks(range(len(groups)), [g[0] for g in groups])
    ax.set_xlim(-0.6, len(groups) - 0.4)
    ax.set_ylabel("cost above the circuit's best salt (%)")
    ax.set_ylim(-0.05 * top - 1e-6, top * 1.15 + 1e-6)
    ax.text(
        0.99,
        0.97,
        "ring = worst salt",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=9,
        color="#555555",
    )
    fig.tight_layout()
    return _save(fig, out, "salt_spread.png")


def render_all(rows: list[ledger.Row], out: pathlib.Path = DEFAULT_OUT) -> list[pathlib.Path]:
    return [render_progress(rows, out), render_salt_spread(rows, out)]


# ---- CLI ---------------------------------------------------------------------------------------


def add_parser(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    p = sub.add_parser("plots", help="draw PNGs from the ledger into out/plots/ (needs the plots extra)")
    p.add_argument("--ledger", type=pathlib.Path, default=ledger.DEFAULT_LEDGER)
    p.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)


def run(a: argparse.Namespace) -> int:
    try:
        importlib.import_module("matplotlib")
    except ImportError:
        print("error: matplotlib is not installed (run `uv sync --extra plots`)")
        return 1
    rows = ledger.read(a.ledger) if a.ledger.exists() else []
    for path in render_all(rows, a.out):
        print(path)
    return 0
