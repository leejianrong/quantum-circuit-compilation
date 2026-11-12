"""Pure view models for the Anatomy and Verifier theatre tabs: no indah import.

Both read ledger rows. Anatomy needs the structure fields (`toffolis`, `qubits`, `stage_shares`);
the theatre needs the per-salt costs and the failure count. A flame chart is only rebuilt for
generator circuits that build in under a second (`FLAME_PRESETS`); the full-size circuits are
verified elsewhere and their stage shares come from the ledger.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from bench import ledger, plots, stats

VERIFIER_KINDS = (None, "full", "screen")
Rows = list[list[float | None]]


def short(r: ledger.Row) -> str:
    name = r.circuit.rstrip("/").rsplit("/", 1)[-1]
    return f"{r.bench} {name} {r.circuit_sha256[:6]}"


def _stamp(r: ledger.Row) -> str:
    return (r.ts or "")[:16].replace("T", " ")


def verify_runs(rows: list[ledger.Row]) -> list[ledger.Row]:
    """Every run the official verifier scored or rejected (screens and failures included), newest last."""
    return [r for r in rows if r.kind in VERIFIER_KINDS and r.bench in plots.BENCHES and r.salts > 0]


def anatomy_runs(rows: list[ledger.Row]) -> list[ledger.Row]:
    """Runs that carry structure: a static Toffoli count or stage shares."""
    return [r for r in verify_runs(rows) if r.toffolis is not None or r.stage_shares]


def option_label(r: ledger.Row) -> str:
    cost = f"{r.cost:,.0f}" if r.cost else "no cost"
    exp = f" {r.experiment}" if r.experiment else ""
    return f"{r.bench}{exp} {r.kind or 'run'} {cost} ({short(r).split()[-1]}) {_stamp(r)}".strip()


# ---- anatomy ---------------------------------------------------------------------------------


def stage_table(r: ledger.Row) -> list[dict[str, Any]]:
    """Stage shares in percent, largest first; the remainder is "other (unmarked)"."""
    shares = dict(r.stage_shares or {})
    if not shares:
        return []
    rest = 1.0 - sum(shares.values())
    if rest > 0.005:
        shares["other (unmarked)"] = rest
    return [
        {"stage": k, "share": round(100 * v, 2)} for k, v in sorted(shares.items(), key=lambda kv: -kv[1])
    ]


def structure_facts(r: ledger.Row) -> dict[str, str]:
    ratio = plots.ratio(r.bench, r.cost) if r.cost and r.bench in plots.BASELINES else None
    return {
        "toffolis": "-" if r.toffolis is None else f"{r.toffolis:,.0f}",
        "qubits": "-" if r.qubits is None else str(r.qubits),
        "depth": "-" if r.depth is None else f"{r.depth:,}",
        "cost": "-" if r.cost is None else f"{r.cost:,.0f}",
        "ratio": "-" if ratio is None else f"{ratio:.2f}x",
    }


def _invsqrt(a: int, frac: tuple[int, ...], guard: int) -> Callable[[], Any]:
    def make() -> Any:
        from invsqrt_gen.build import build
        from invsqrt_gen.model import fit_tables
        from invsqrt_gen.params import Params

        p = Params(a=a, frac=frac, guard=guard)
        return build(p, fit_tables(p, passes=1, stride=211))

    return make


@dataclass(frozen=True)
class FlamePreset:
    label: str
    note: str
    make: Callable[[], Any]


FLAME_PRESETS: dict[str, FlamePreset] = {
    "invsqrt-a3": FlamePreset(
        "invsqrt generator, a=3 (small)",
        "Our table + Horner + phase generator at 8 table segments and degree 2: the same stages as the "
        "full circuit, about 1,400 Toffolis.",
        _invsqrt(3, (22, 15, 9), 2),
    ),
    "invsqrt-a4": FlamePreset(
        "invsqrt generator, a=4 (small)",
        "16 table segments: the lookup stage grows, the Horner stages do not.",
        _invsqrt(4, (22, 15, 9), 2),
    ),
}
_cache: dict[str, tuple[str, dict[str, float] | None, int]] = {}


def with_background(svg: str) -> str:
    """kickmix draws black strokes on nothing: give the chart a white page (so dark mode stays legible)
    and crop the view box to the drawn bars, which it leaves a lot of empty space around."""
    m = re.search(r'viewBox="([-\d. ]+)"', svg)
    if not m:
        return svg
    x, y, w, h = (float(v) for v in m.group(1).split())
    rects = [
        (float(a), float(b)) for a, b in re.findall(r'<rect [^>]*y="(-?[\d.]+)" [^>]*height="([\d.]+)"', svg)
    ]
    if rects:
        top, bottom = min(a for a, _ in rects) - 14, max(a + b for a, b in rects) + 22
        y, h = top, bottom - top
    box = f'viewBox="{x} {y} {w} {h}"'
    rect = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="white"/>'
    svg = svg.replace(m.group(0), box, 1)
    return re.sub(r"(<svg[^>]*>)", lambda mo: mo.group(1) + rect, svg, count=1)


def data_uri(svg: str) -> str:
    return "data:image/svg+xml;utf8," + svg.replace("#", "%23").replace("<", "%3C").replace(">", "%3E")


def flame(key: str) -> tuple[str, dict[str, float] | None, int] | None:
    """(flame chart SVG, stage shares, static Toffoli count) of a preset, or None without kickmix."""
    if key in _cache:
        return _cache[key]
    try:
        circuit = FLAME_PRESETS[key].make()
    except ImportError:
        return None
    svg = circuit.flame_chart_svg()
    out = (
        with_background(svg),
        stats.stage_shares(svg),
        int(circuit.operation_statistics().num_toffoli_like),
    )
    _cache[key] = out
    return out


# ---- verifier theatre ------------------------------------------------------------------------


def failed_salts(r: ledger.Row) -> set[int]:
    """Salt indexes that failed. The ledger keeps the first error text ("salt 3: ..."); when it does
    not name a salt the first `failures` salts are shown as failed, which is a guess."""
    named = {int(n) for n in re.findall(r"salt (\d+)", r.error or "")}
    if named:
        return named
    return set(range(min(r.failures, r.salts))) if r.status == "FAIL" or r.failures else set()


def ticks(r: ledger.Row) -> list[list[float]]:
    """One `[pass, fail]` bar per salt, for a BarStrip with tones ok and err."""
    bad = failed_salts(r)
    return [[0.0, 1.0] if i in bad else [1.0, 0.0] for i in range(r.salts)]


def verdict(r: ledger.Row) -> tuple[str, str]:
    if r.status == "PASS" and not r.failures:
        return "ACCEPTED: every salt passed", "ok"
    n = max(r.failures, 1)
    return f"REJECTED: {n} of {r.salts} salts failed, and one failure rejects the whole submission", "err"


def spread_rows(r: ledger.Row) -> Rows:
    """Rows `[salt, % above best salt, running worst, worst salt]`: each salt's cost against the best salt,
    the staircase of the running worst (its last step is the cost that counts) and a dot on the salt that
    sets it. Percent, because the spread is a fraction of a percent of numbers 12 digits long."""
    costs = list(r.salt_costs or r.costs)
    if not costs:
        return []
    lo, worst = min(costs), max(costs)
    out: Rows = []
    run = 0.0
    for i, c in enumerate(costs):
        pct = round(100 * (c / lo - 1), 6)
        run = max(run, pct)
        out.append([float(i), pct, run, pct if c == worst and i == costs.index(c) else None])
    return out


def spread_facts(r: ledger.Row) -> str:
    costs = list(r.salt_costs or r.costs)
    if not costs:
        return "No per-salt costs were recorded for this run."
    lo, hi = min(costs), max(costs)
    return (
        f"{len(costs)} salts: best {lo:,.0f}, worst {hi:,.0f} (counts), spread {100 * (hi / lo - 1):.3f}% "
        f"above the best salt."
    )


def run_table(runs: list[ledger.Row]) -> list[dict[str, object]]:
    """One table row per verifier run, newest first; `id` is the index in `runs`."""
    out = [
        {
            "id": str(i),
            "bench": r.bench,
            "run": f"{r.experiment or ''} {short(r).split()[1]}".strip(),
            "kind": r.kind or "run",
            "status": r.status,
            "salts": r.salts,
            "failed": r.failures,
            "cost": f"{r.cost:,.0f}" if r.cost else "-",
            "when": r.ts or "",
        }
        for i, r in enumerate(runs)
    ]
    return out[::-1]
