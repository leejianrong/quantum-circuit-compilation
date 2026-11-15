"""DQI analysis figures, drawn from analysis/numbers/dqi.json only.

    uv run python -m analysis.dqi_figures [out_dir]        # PNGs, default docs/img/analysis

Every number in a figure is in the JSON with its source tag (M measured, V read from the other source).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

DATA = Path(__file__).resolve().parent / "numbers" / "dqi.json"
OURS, THEIRS, GOOD, BAD = "#2b6cb0", "#c05621", "#2f855a", "#c53030"


def load() -> dict:  # type: ignore[type-arg]
    return json.loads(DATA.read_text())


def stage_ledger(d: dict) -> plt.Figure:  # type: ignore[type-arg]
    comps = d["stage_ledger"]["components"]
    names = [c["name"] for c in comps]
    ours = [c["ours"] / 1000 for c in comps]
    theirs = [c["theirs_final"] / 1000 for c in comps]
    fig, ax = plt.subplots(figsize=(8, 4.4))
    x = range(len(names))
    w = 0.38
    ax.bar([i - w / 2 for i in x], ours, w, label="ours (measured, boundaries +-3k)", color=OURS)
    ax.bar([i + w / 2 for i in x], theirs, w, label="his final (native build ledger)", color=THEIRS)
    for i, (o, t) in enumerate(zip(ours, theirs, strict=True)):
        ax.text(i, max(o, t) + 2, f"{o - t:+.1f}k", ha="center", fontsize=9, color=BAD if o > t else GOOD)
    ax.set_xticks(list(x), names, fontsize=8)
    ax.set_ylabel("static Toffolis (thousands)")
    ax.set_title("DQI cost by component: ours minus his above each pair")
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def qubit_timeline(d: dict) -> plt.Figure:  # type: ignore[type-arg]
    q = d["qubit_timeline_theirs"]
    ys = q["allocated_Q"]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.step(range(len(ys)), ys, where="post", color=THEIRS, lw=1.4)
    palette = ["#edf2f7", "#e2e8f0"]
    for i, (name, lo, hi) in enumerate(q["groups"]):
        ax.axvspan(lo - 0.5, hi + 0.5, color=palette[i % 2], zorder=0)
        ax.text((lo + hi) / 2, 892, name, rotation=90, ha="center", va="bottom", fontsize=7)
    ax.axhline(q["circuit_peak"], color=BAD, lw=1, ls="--")
    ax.text(
        len(ys) - 1,
        q["circuit_peak"] + 1,
        f"circuit peak {q['circuit_peak']} (inside a stage)",
        ha="right",
        fontsize=8,
        color=BAD,
    )
    ax.set_ylim(830, 940)
    ax.set_xlabel("stage mark index in his build")
    ax.set_ylabel("allocated qubits at the end of each mark")
    ax.set_title("His qubit width over the build: 840 to 877 at the marks, peak 889 within a stage")
    fig.tight_layout()
    return fig


def patch_waterfall(d: dict) -> plt.Figure:  # type: ignore[type-arg]
    wf = d["v7_patch_waterfall"]
    labels = [wf["start_label"]] + [s[0] for s in wf["steps"]] + ["final"]
    level = wf["start"]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.bar(0, level - 383000, bottom=383000, color=THEIRS)
    for i, (_, delta) in enumerate(wf["steps"], start=1):
        ax.bar(i, delta, bottom=level, color=GOOD if delta < 0 else BAD)
        level += delta
    ax.bar(len(labels) - 1, level - 383000, bottom=383000, color=THEIRS)
    ax.set_xticks(range(len(labels)), labels, rotation=60, ha="right", fontsize=7)
    ax.set_ylim(383000, wf["start"] + 120)
    ax.set_ylabel("static Toffolis")
    ax.set_title(f"His v7 patches: {wf['start']:,} to {wf['final']:,} (sum {wf['final'] - wf['start']:+d})")
    fig.tight_layout()
    return fig


def profile_diff(d: dict) -> plt.Figure:  # type: ignore[type-arg]
    p = d["profile_diff"]
    xs = p["bucket_start_M"]
    diff = [t - o for t, o in zip(p["theirs"], p["ours"], strict=True)]
    fig, (a, b) = plt.subplots(2, 1, figsize=(8, 5.6), sharex=True)
    a.plot(xs, p["ours"], label="ours", color=OURS)
    a.plot(xs, p["theirs"], label="his", color=THEIRS)
    a.set_ylabel("Toffolis per 2M instr.")
    a.legend(fontsize=8)
    a.set_title("Toffoli profile, aligned at the first Toffoli")
    b.bar(xs, diff, width=1.6, color=[GOOD if v < 0 else BAD for v in diff])
    b.axhline(0, color="k", lw=0.5)
    b.set_ylabel("his minus ours")
    b.set_xlabel("instructions after first Toffoli (millions); drift grows along the axis")
    fig.tight_layout()
    return fig


def instruction_mix(d: dict) -> plt.Figure:  # type: ignore[type-arg]
    m = d["instruction_mix"]
    keys = [k for k in m["ours"] if k not in {"CX", "POP_CONDITION"}]
    fig, ax = plt.subplots(figsize=(8, 4.4))
    x = range(len(keys))
    w = 0.38
    ax.bar([i - w / 2 for i in x], [m["ours"][k] for k in keys], w, label="ours", color=OURS)
    ax.bar([i + w / 2 for i in x], [m["theirs"][k] for k in keys], w, label="his", color=THEIRS)
    ax.set_yscale("log")
    ax.set_xticks(list(x), keys, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("instructions (log)")
    ax.set_title("Instruction mix (CX and POP_CONDITION omitted: CX equal, POP = PUSH)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def j_min_sweep(d: dict) -> plt.Figure:  # type: ignore[type-arg]
    pts = d["j_min_sweep"]["points"]
    js = [p["j_min"] for p in pts]
    fig, (a, b) = plt.subplots(1, 2, figsize=(8, 3.8))
    base = pts[0]["toffolis"]
    a.bar([str(j) for j in js], [p["toffolis"] - base for p in pts], color=GOOD)
    a.set_ylabel("Toffolis relative to J_MIN = 15")
    a.set_xlabel("J_MIN")
    a.set_title("Saving per step is 138 T per slot")
    base_ratio = pts[0]["score_over_q2t"]
    b.bar(
        [str(j) for j in js],
        [p["score_over_q2t"] / base_ratio for p in pts],
        color=[BAD if p["value_errors"] else GOOD for p in pts],
    )
    for i, p in enumerate(pts):
        b.text(
            i,
            p["score_over_q2t"] / base_ratio + 0.005,
            f"{p['value_errors']} errors",
            ha="center",
            fontsize=8,
        )
    b.set_ylim(0.9, 1.2)
    b.set_ylabel("verifier score / Q^2 T, relative")
    b.set_xlabel("J_MIN (narrow instance, 3,072 shots)")
    b.set_title("Failures cost far more than they save")
    fig.tight_layout()
    return fig


FIGURES = {
    "dqi-stage-ledger": stage_ledger,
    "dqi-qubit-timeline": qubit_timeline,
    "dqi-v7-waterfall": patch_waterfall,
    "dqi-profile-diff": profile_diff,
    "dqi-instruction-mix": instruction_mix,
    "dqi-jmin-sweep": j_min_sweep,
}


def draw_all(out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    d = load()
    paths = []
    for name, fn in FIGURES.items():
        fig = fn(d)
        p = out / f"{name}.png"
        fig.savefig(p, dpi=140)
        plt.close(fig)
        paths.append(p)
    return paths


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/img/analysis")
    for q in draw_all(target):
        print(q)
