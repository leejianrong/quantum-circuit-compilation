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

from bench import experiments, ledger

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


THIRD_PARTY = ("public/", "public:", "data/", "/kaggle/input/")


# Runs of our generators that load third-party data, so they do not count as fully our own circuit.
NOT_FULLY_OWN = {
    "997264adf89b3d54edde3bcd836aa0fe5b1bd42022c3b21e9c0994d8b0fe0d9a": "E001, our loader on public words",
}


def is_own(r: ledger.Row) -> bool:
    """A run of a circuit we generated, not a public circuit, the host's baseline or our loader on
    someone else's table (`NOT_FULLY_OWN`)."""
    return (
        not r.circuit.startswith(THIRD_PARTY)
        and "/public/" not in r.circuit
        and r.circuit_sha256 not in NOT_FULLY_OWN
    )


def own_runs(rows: list[ledger.Row]) -> list[ledger.Row]:
    """Verified runs of our own circuits: what "ours" means in the score and ratio plots."""
    return [r for r in verified(rows) if is_own(r)]


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
    pts = [(when(r, origin), ratio(bench, r.cost)) for r in own_runs(rows) if r.bench == bench and r.cost]
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
        for r in own_runs(rows)
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


def stage_bars(rows: list[ledger.Row]) -> list[tuple[str, dict[str, float]]]:
    """One (label, shares) per distinct circuit that has stage shares; the remainder is "other"."""
    latest: dict[tuple[str, str], ledger.Row] = {}
    for r in rows:
        if r.stage_shares and r.kind in (None, "full", "screen"):
            latest[(r.bench, r.circuit_sha256)] = r
    out = []
    for (b, sha), r in sorted(latest.items()):
        shares = dict(r.stage_shares or {})
        rest = 1.0 - sum(shares.values())
        if rest > 0.005:
            shares["other (unmarked)"] = rest
        out.append((f"{b}\n{sha[:8]}", shares))
    return out


def structure_points(rows: list[ledger.Row]) -> list[tuple[str, str, int, float]]:
    """(bench, kind, qubits, toffoli-like count) per distinct circuit with statistics.

    kind is "verified", "public-reference" or "failed"; a failed run has no verified cost.
    """
    seen: dict[tuple[str, str], tuple[str, str, int, float]] = {}
    ok = {id(r) for r in verified(rows)}
    for r in rows:
        if r.toffolis is None or r.qubits is None or r.kind not in (None, "full", "public-reference"):
            continue
        kind = "public-reference" if r.kind == "public-reference" else "verified" if id(r) in ok else "failed"
        seen[(r.bench, r.circuit_sha256)] = (r.bench, kind, r.qubits, float(r.toffolis))
    return list(seen.values())


def pareto_front(points: list[tuple[int, float]]) -> list[tuple[int, float]]:
    """Non-dominated (qubits, toffolis) points, both minimised, sorted by qubits."""
    front: list[tuple[int, float]] = []
    for q, t in sorted(set(points)):
        if not front or t < front[-1][1]:
            front.append((q, t))
    return front


FUNNEL_KEYS = (*BENCHES, "all")


def funnel_counts(
    rows: list[ledger.Row], exps: dict[str, experiments.Experiment]
) -> list[tuple[str, dict[str, int]]]:
    """Screened, full verified, promoted, submitted, each split by benchmark ("all" for submissions)."""

    def tally(items: list[tuple[str, str]]) -> dict[str, int]:
        out: dict[str, int] = {}
        for b, _ in set(items):
            out[b] = out.get(b, 0) + 1
        return out

    screened = [(r.bench, r.circuit_sha256) for r in rows if r.kind == "screen"]
    full = [(r.bench, r.circuit_sha256) for r in verified(rows)]
    promoted = [(e.benchmark, e.id) for e in exps.values() if e.outcome == "promoted"]
    submitted = [(r.bench, r.circuit) for r in rows if r.kind == "leaderboard"]
    return [
        ("screened (reduced shots)", tally(screened)),
        ("full verified", tally(full)),
        ("promoted", tally(promoted)),
        ("submitted", tally(submitted)),
    ]


def wall_groups(rows: list[ledger.Row]) -> list[tuple[str, list[tuple[float, str]]]]:
    """Per (bench, host): (minutes per salt, run kind) for runs that did work."""
    groups: dict[tuple[str, str], list[tuple[float, str]]] = {}
    for r in rows:
        if r.kind not in (None, "full", "screen") or r.wall_s <= 0:
            continue
        kind = "failed" if r.status == "FAIL" else "screen" if r.reduced_shots else "full"
        groups.setdefault((r.bench, r.host), []).append((r.wall_s / 60 / max(r.salts, 1), kind))

    def order(k: tuple[str, str]) -> tuple[int, str]:
        return (BENCHES.index(k[0]) if k[0] in BENCHES else len(BENCHES), k[1])

    return [(f"{b}\n{h}", groups[(b, h)]) for b, h in sorted(groups, key=order)]


def render_stages(rows: list[ledger.Row], out: pathlib.Path) -> pathlib.Path:
    """Stacked bars of the static toffoli-like count by marked stage (not the official cost)."""
    plt = _plt()
    bars = stage_bars(rows)
    fig, ax = plt.subplots(figsize=(max(7.0, 1.6 * len(bars) + 4), 5.5))
    ax.set_title("Where the toffoli-like count goes, by stage")
    if not bars:
        _no_data(ax, "no data yet\n(needs a circuit with `mark` stages in the ledger)")
        return _save(fig, out, "stages.png")
    names = sorted({n for _, sh in bars for n in sh}, key=lambda n: (n.startswith("other"), n))
    cmap = plt.get_cmap("tab20")
    for j, name in enumerate(names):
        bottoms = [sum(v for k, v in sh.items() if names.index(k) < j) * 100 for _, sh in bars]
        vals = [sh.get(name, 0.0) * 100 for _, sh in bars]
        color = "#cccccc" if name.startswith("other") else cmap(j % 20)
        ax.bar(range(len(bars)), vals, bottom=bottoms, label=name, color=color, edgecolor="white")
    ax.set_xticks(range(len(bars)), [b for b, _ in bars])
    ax.set_ylim(0, 100)
    ax.set_ylabel("share of toffoli-like count (%)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8)
    note = "static toffoli-like count (CCX+CCZ+CSWAP), not the official cost"
    fig.text(0.5, 0.01, note, ha="center", fontsize=8, color="#777777")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    return _save(fig, out, "stages.png")


def render_pareto(rows: list[ledger.Row], out: pathlib.Path) -> pathlib.Path:
    """Toffoli-like count against qubits, log-log, with iso-product curves and per-benchmark fronts."""
    plt = _plt()
    lines = importlib.import_module("matplotlib.lines")
    pts = structure_points(rows)
    fig, ax = plt.subplots(figsize=(8.5, 6))
    ax.set_title("Toffoli-like count vs qubits (down and left is better)")
    if not pts:
        _no_data(ax, "no data yet\n(needs ledger rows with toffolis and qubits)")
        return _save(fig, out, "pareto.png")
    qs, ts = [p[2] for p in pts], [p[3] for p in pts]
    ax.set_xscale("log")
    ax.set_yscale("log")
    qlo, qhi, tlo, thi = min(qs) / 1.6, max(qs) * 1.6, min(ts) / 1.6, max(ts) * 1.6
    ax.set_xlim(qlo, qhi)
    ax.set_ylim(tlo, thi)
    for e in range(math.floor(math.log10(qlo * tlo)), math.ceil(math.log10(qhi * thi)) + 1):
        ax.plot([qlo, qhi], [10.0**e / qlo, 10.0**e / qhi], color="#bbbbbb", lw=0.8, ls=":", zorder=0)
        x_lab = min(qhi, 10.0**e / tlo)
        if qlo < x_lab and tlo <= 10.0**e / x_lab <= thi:
            ax.annotate(
                f"Q x T = 1e{e}",
                (x_lab, 10.0**e / x_lab),
                fontsize=7,
                color="#888888",
                ha="right",
                va="bottom",
            )
    for bench in BENCHES:
        mine = [p for p in pts if p[0] == bench]
        col = COLORS[bench]
        front = pareto_front([(p[2], p[3]) for p in mine if p[1] != "failed"])
        if len(front) > 1:
            ax.step([q for q, _ in front], [t for _, t in front], where="post", color=col, lw=1.2, alpha=0.6)
        for _, kind, q, t in mine:
            if kind == "verified":
                ax.plot(q, t, "o", color=col, ms=9, mec="white")
            elif kind == "public-reference":
                ax.plot(q, t, "o", mfc="none", mec=col, mew=1.8, ms=9)
            else:
                ax.plot(q, t, "x", color=COLORS["fail"], ms=9, mew=2)
    ticker = importlib.import_module("matplotlib.ticker")
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x:g}"))
    ax.xaxis.set_minor_formatter(
        ticker.FuncFormatter(
            lambda x, _: f"{x:g}" if round(x / 10 ** math.floor(math.log10(x))) in (2, 5) else ""
        )
    )
    ax.set_xlabel("qubits (count)")
    ax.set_ylabel("toffoli-like count (CCX+CCZ+CSWAP, static)")
    handles = [lines.Line2D([], [], color=COLORS[b], marker="o", ls="", label=b) for b in BENCHES]
    handles += [
        lines.Line2D([], [], color="#444444", marker="o", ls="", label="verified (filled)"),
        lines.Line2D(
            [], [], mfc="none", mec="#444444", marker="o", ls="", label="public, unverified (hollow)"
        ),
        lines.Line2D([], [], color=COLORS["fail"], marker="x", ls="", mew=2, label="failed"),
    ]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8)
    fig.tight_layout()
    return _save(fig, out, "pareto.png")


def render_funnel(
    rows: list[ledger.Row], exps: dict[str, experiments.Experiment], out: pathlib.Path
) -> pathlib.Path:
    """Experiment funnel from ledger kinds and the experiment log, split by benchmark."""
    plt = _plt()
    stages = funnel_counts(rows, exps)
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    ax.set_title(f"Experiment funnel ({len(exps)} experiments opened)")
    if not any(c for _, c in stages):
        _no_data(ax)
        return _save(fig, out, "funnel.png")
    ys = list(range(len(stages)))[::-1]
    left = [0] * len(stages)
    for key in FUNNEL_KEYS:
        vals = [c.get(key, 0) for _, c in stages]
        label = "submission (all benchmarks)" if key == "all" else key
        color = COLORS.get(key, COLORS["leaderboard"])
        ax.barh(ys, vals, left=left, color=color, label=label, edgecolor="white")
        left = [a + b for a, b in zip(left, vals, strict=True)]
    for y, total in zip(ys, left, strict=True):
        ax.text(total + 0.05, y, str(total), va="center", fontsize=10)
    ax.set_yticks(ys, [n for n, _ in stages])
    ax.set_xlabel("count (distinct circuits; promoted = experiments)")
    ax.xaxis.get_major_locator().set_params(integer=True)
    ax.set_xlim(0, max(left) * 1.12 + 0.5)
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    return _save(fig, out, "funnel.png")


def render_wall_time(rows: list[ledger.Row], out: pathlib.Path) -> pathlib.Path:
    """Verify wall time per salt for each benchmark and host."""
    plt = _plt()
    lines = importlib.import_module("matplotlib.lines")
    groups = wall_groups(rows)
    fig, ax = plt.subplots(figsize=(max(7.0, 1.4 * len(groups) + 3), 5))
    ax.set_title("Verify wall time per salt")
    if not groups:
        _no_data(ax)
        return _save(fig, out, "wall_time.png")
    rng = random.Random(0)
    allv = [v for _, g in groups for v, _ in g]
    for i, (label, g) in enumerate(groups):
        col = COLORS.get(label.split("\n")[0], "#444444")
        for v, kind in g:
            x = i + rng.uniform(-0.15, 0.15)
            if kind == "full":
                ax.plot(x, v, "o", color=col, ms=8, mec="white")
            elif kind == "screen":
                ax.plot(x, v, "o", mfc="none", mec=col, mew=1.8, ms=8)
            else:
                ax.plot(x, v, "x", color=COLORS["fail"], ms=8, mew=2)
    ax.set_xticks(range(len(groups)), [g[0] for g in groups])
    ax.set_xlim(-0.6, len(groups) - 0.4)
    if min(allv) > 0 and max(allv) / min(allv) >= 10:
        ax.set_yscale("log")
    ax.set_ylabel("wall time per salt (minutes)")
    handles = [
        lines.Line2D([], [], color="#444444", marker="o", ls="", label="full"),
        lines.Line2D([], [], mfc="none", mec="#444444", marker="o", ls="", label="screen (reduced shots)"),
        lines.Line2D([], [], color=COLORS["fail"], marker="x", ls="", mew=2, label="failed"),
    ]
    ax.legend(handles=handles, loc="upper left", fontsize=8)
    fig.tight_layout()
    return _save(fig, out, "wall_time.png")


def render_all(
    rows: list[ledger.Row],
    out: pathlib.Path = DEFAULT_OUT,
    exps: dict[str, experiments.Experiment] | None = None,
) -> list[pathlib.Path]:
    return [
        render_progress(rows, out),
        render_salt_spread(rows, out),
        render_stages(rows, out),
        render_pareto(rows, out),
        render_funnel(rows, exps or {}, out),
        render_wall_time(rows, out),
    ]


# ---- CLI ---------------------------------------------------------------------------------------


def add_parser(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    p = sub.add_parser("plots", help="draw PNGs from the ledger into out/plots/ (needs the plots extra)")
    p.add_argument("--ledger", type=pathlib.Path, default=ledger.DEFAULT_LEDGER)
    p.add_argument("--experiments", type=pathlib.Path, default=experiments.DEFAULT_LOG)
    p.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)


def run(a: argparse.Namespace) -> int:
    try:
        importlib.import_module("matplotlib")
    except ImportError:
        print("error: matplotlib is not installed (run `uv sync --extra plots`)")
        return 1
    rows = ledger.read(a.ledger) if a.ledger.exists() else []
    for path in render_all(rows, a.out, experiments.read(a.experiments)):
        print(path)
    return 0
