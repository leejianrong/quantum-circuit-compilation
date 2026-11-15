"""Figures for the learning track, drawn from code and `analysis/numbers/learn.json` only.

    uv run --extra plots python -m analysis.learn_figures [out_dir]     # SVGs, default docs/img/learn
    make learn-figures

Every figure is a function that returns a matplotlib Figure and is listed in FIGURES. The SVGs are
committed; tests/unit/test_learn_figures.py regenerates each one twice (byte-identical), checks the
plotted numbers against the ledger, and fails if a page references a figure that is not registered.
Text stays text in the SVG (no outlined glyphs) and the background is transparent, so a figure reads on
the light and the dark theme alike.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Arc  # noqa: E402

from analysis.circuit_draw import draw  # noqa: E402

DATA = Path(__file__).resolve().parent / "numbers" / "learn.json"
INK, FAINT = "#8a93a0", "#4a5160"
OURS, PUBLIC, REF, ACCENT = "#3b82f6", "#f97316", "#94a3b8", "#10b981"  # readable on light and dark

plt.rcParams.update(
    {
        "svg.fonttype": "none",
        "svg.hashsalt": "qcc-learn",
        "font.family": "sans-serif",
        "text.color": INK,
        "axes.labelcolor": INK,
        "axes.edgecolor": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "axes.facecolor": "none",
        "figure.facecolor": "none",
        "savefig.facecolor": "none",
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)


def load() -> dict:  # type: ignore[type-arg]
    return json.loads(DATA.read_text())


# --- complex numbers and phase -------------------------------------------------------------------


def _plane(ax: plt.Axes, lim: float) -> None:
    ax.set_aspect("equal")
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.axhline(0, color=INK, lw=0.8)
    ax.axvline(0, color=INK, lw=0.8)
    ax.set_xlabel("real part")
    ax.set_ylabel("imaginary part")
    for s in ("left", "bottom"):
        ax.spines[s].set_visible(False)


def argand_plane() -> plt.Figure:
    """A complex number as a point: real part, imaginary part, magnitude and angle; times i rotates it."""
    z = 1.2 + 0.9j
    rot = z * 1j
    fig, ax = plt.subplots(figsize=(5.2, 5.2))
    _plane(ax, 1.9)
    ax.plot([z.real, z.real], [0, z.imag], ls=":", color=INK)
    ax.plot([0, z.real], [z.imag, z.imag], ls=":", color=INK)
    for v, c in ((z, OURS), (rot, PUBLIC)):
        ax.annotate("", (v.real, v.imag), (0, 0), arrowprops={"arrowstyle": "-|>", "color": c, "lw": 2})
    ax.plot(z.real, z.imag, "o", color=OURS)
    ax.plot(rot.real, rot.imag, "o", color=PUBLIC)
    theta = np.degrees(np.angle(z))
    ax.add_patch(Arc((0, 0), 1.0, 1.0, theta1=0, theta2=theta, color=ACCENT, lw=1.6))
    ax.text(0.62, 0.17, "angle", color=ACCENT, fontsize=10)
    ax.text(z.real + 0.06, z.imag + 0.06, "z = 1.2 + 0.9i", color=OURS, fontsize=10)
    ax.text(rot.real - 0.1, rot.imag + 0.1, "i·z = -0.9 + 1.2i", color=PUBLIC, fontsize=10, ha="right")
    ax.text(0.35, 0.78, f"|z| = {abs(z):.1f}", color=OURS, fontsize=10, rotation=np.degrees(np.angle(z)))
    ax.set_title("Multiplying by i turns a point a quarter turn", color=INK, fontsize=11)
    return fig


def phase_wheel() -> plt.Figure:
    """The unit circle: a phase gate multiplies the |1> amplitude by e^(i*theta), a point on it."""
    fig, ax = plt.subplots(figsize=(5.2, 5.2))
    _plane(ax, 1.5)
    t = np.linspace(0, 2 * np.pi, 400)
    ax.plot(np.cos(t), np.sin(t), color=INK, lw=1)
    marks = [
        ("1 (no gate)", 0, REF, (0.1, 0.1), "left"),
        ("T = e^(i·π/4)", np.pi / 4, PUBLIC, (0.1, 0.1), "left"),
        ("S = i", np.pi / 2, OURS, (0.1, 0.1), "left"),
        ("Z = -1", np.pi, ACCENT, (-0.1, 0.1), "right"),
    ]
    for name, th, c, (dx, dy), ha in marks:
        p = np.exp(1j * th)
        ax.plot(p.real, p.imag, "o", ms=9, color=c)
        ax.text(p.real + dx, p.imag + dy, name, color=c, fontsize=10, ha=ha)
    ax.text(0, -0.3, "T·T = S, and S·S = Z", ha="center", color=INK, fontsize=10)
    ax.set_title("Phase gates are points on the unit circle", color=INK, fontsize=11)
    return fig


def interference_bars() -> plt.Figure:
    """Signed amplitudes after H H and after H Z H: the sign decides which outcome survives."""
    h = np.array([[1, 1], [1, -1]]) / np.sqrt(2)
    z = np.diag([1.0, -1.0])
    start = np.array([1.0, 0.0])
    cases = [
        ("start |0>", start),
        ("after H", h @ start),
        ("H, H", h @ h @ start),
        ("H, Z, H", h @ z @ h @ start),
    ]
    fig, axes = plt.subplots(1, 4, figsize=(8.4, 2.6), sharey=True)
    for ax, (name, amp) in zip(axes, cases, strict=True):
        ax.bar(["|0>", "|1>"], amp, color=[OURS if a >= 0 else PUBLIC for a in amp], width=0.55)
        ax.axhline(0, color=INK, lw=0.8)
        ax.set_title(name, color=INK, fontsize=10)
        ax.set_ylim(-1.1, 1.1)
        ax.set_yticks([-1, 0, 1])
    axes[0].set_ylabel("amplitude")
    fig.suptitle(
        "A sign changes nothing you can read directly, and decides what interference leaves",
        color=INK,
        fontsize=10,
    )
    fig.tight_layout()
    return fig


# --- circuits --------------------------------------------------------------------------------------


def circuit_toffoli_and() -> plt.Figure:
    """A Toffoli computes AND into a fresh qubit; a second one cleans it up."""
    gates = [("CCX", 0, 1, 2), ("CCX", 0, 1, 2, {"label": "uncompute"})]
    return draw(gates, ["a", "b", "anc = 0"], title="Compute a AND b, then undo it: two Toffolis")


def circuit_mbuc() -> plt.Figure:
    """Compute the AND once; clean the ancilla by measurement and repair the sign with a free CZ."""
    gates = [("CCX", 0, 1, 2), ("HMR", 2, {"label": "HMR→m"}), ("CZ", 0, 1, {"cond": "m"})]
    return draw(gates, ["a", "b", "anc = 0"], title="MBUC: one Toffoli, then measure and repair with CZ")


def circuit_bell() -> plt.Figure:
    """H then CNOT turns |00> into the Bell state."""
    return draw([("H", 0), ("CX", 0, 1)], ["q0 = |0>", "q1 = |0>"], title="The Bell state: H, then CNOT")


def adder_gates(n: int = 4) -> tuple[list[tuple], list[str]]:  # type: ignore[type-arg]
    """The gate list of the page's ripple-carry adder (docs/learn/kickmix-hands-on.md), loop for loop.

    `init_and` is drawn as a Toffoli into a fresh carry qubit; `del_and` is an HMR on the carry plus a CZ on
    (a, b) that runs when the measured bit is 1.
    """
    a = list(range(n))
    b = [n + i for i in range(n)]
    c = [2 * n + i for i in range(n - 1)]
    g: list[tuple] = []  # type: ignore[type-arg]
    for i in range(n - 1):
        if i:
            g += [("CX", c[i - 1], a[i]), ("CX", c[i - 1], b[i])]
        g.append(("CCX", a[i], b[i], c[i]))
        if i:
            g.append(("CX", c[i - 1], c[i]))
    g += [("CX", a[n - 1], b[n - 1]), ("CX", c[n - 2], b[n - 1])]
    for i in reversed(range(n - 1)):
        if i:
            g.append(("CX", c[i - 1], c[i]))
        g += [("HMR", c[i], {"label": "HMR", "sets": f"m{i}"}), ("CZ", a[i], b[i], {"cond": f"m{i}"})]
        if i:
            g.append(("CX", c[i - 1], a[i]))
        g.append(("CX", a[i], b[i]))
    wires = [f"a[{i}]" for i in a] + [f"b[{i}]" for i in range(n)] + [f"carry {i} = 0" for i in range(n - 1)]
    return g, wires


def circuit_adder() -> plt.Figure:
    gates, wires = adder_gates(4)
    return draw(gates, wires, title="The 4-bit adder: 3 Toffolis, 11 qubits", compact=True)


def state_vector_growth() -> plt.Figure:
    """Memory of a state vector of n qubits (2^n complex numbers, 16 bytes each)."""
    d = load()
    n = np.arange(1, 71)
    nbytes = 16.0 * 2.0**n
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    ax.plot(n, nbytes, color=OURS, lw=2)
    for label, val in (("1 GB", 1e9), ("1 TB", 1e12), ("1 PB", 1e15)):
        ax.axhline(val, color=INK, lw=0.7, ls=":")
        ax.text(1.5, val * 1.25, label, fontsize=8.5, color=INK)
    for p in (d["invsqrt"]["points"][-1], d["invsqrt"]["points"][-2]):
        q = p["qubits"]
        ax.plot(q, 16.0 * 2.0**q, "o", color=PUBLIC, ms=7)
        ax.annotate(
            f"{p['label']}: {q} qubits",
            (q, 16.0 * 2.0**q),
            textcoords="offset points",
            xytext=(-8, 8),
            ha="right",
            fontsize=8.5,
            color=PUBLIC,
        )
    ax.set_yscale("log")
    ax.set_xlabel("qubits n")
    ax.set_ylabel("bytes for the state vector")
    ax.set_title("46 qubits already need a petabyte to write the state down", color=INK, fontsize=10)
    return fig


def _stacked(ax: plt.Axes, y: float, parts: list[tuple[str, float]], colours: list[str]) -> None:
    """One stacked bar; labels sit inside wide segments and above narrow ones."""
    total = sum(v for _, v in parts)
    left = 0.0
    for (name, v), c in zip(parts, colours, strict=True):
        ax.barh(y, v, left=left, color=c, height=0.5)
        if v / total >= 0.12:
            ax.text(left + v / 2, y, f"{name}\n{v:,}", ha="center", va="center", fontsize=8, color="#0b1220")
        else:
            ax.annotate(
                f"{name}: {v:,}",
                (left + v / 2, y + 0.25),
                xytext=(left + v / 2, y + 0.45),
                ha="right",
                fontsize=8,
                color=INK,
                arrowprops={"arrowstyle": "-", "color": INK, "lw": 0.7},
            )
        left += v


def invsqrt_reference_stages() -> plt.Figure:
    """Toffolis per direction of the reference invsqrt circuit; the multiplications dominate."""
    rows = load()["primers"]["invsqrt_reference_toffolis_per_direction"]
    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    ys = list(range(len(rows)))[::-1]
    for y, (_name, v, mult) in zip(ys, rows, strict=True):
        ax.barh(y, v, color=PUBLIC if mult else REF, height=0.6)
        ax.text(v + 15, y, f"{v:,}", va="center", fontsize=8.5, color=INK)
    ax.set_yticks(ys, [r[0] for r in rows], fontsize=9)
    mult_total = sum(r[1] for r in rows if r[2])
    total = sum(r[1] for r in rows)
    ax.set_xlabel("Toffolis per direction")
    ax.set_title(
        f"Horner and Newton multiplications: {mult_total:,} of {total:,} ({mult_total / total:.0%})",
        color=INK,
        fontsize=10,
    )
    ax.set_xlim(0, 1250)
    fig.tight_layout()
    return fig


def dqi_reference_split() -> plt.Figure:
    """Where the DQI reference decoder spends its Toffolis."""
    d = load()["primers"]["dqi_reference"]
    fig, ax = plt.subplots(figsize=(7.2, 2.2))
    short = {
        "Chien search, Forney, phase": "Chien, Forney,\nphase",
        "initial shift and its inverse": "initial shift",
    }
    _stacked(ax, 0, [(short.get(n, n), v) for n, v in d["stages"]], [PUBLIC, PUBLIC, OURS, REF])
    ax.xaxis.set_major_formatter(lambda x, _: f"{x / 1e6:g}M")
    ax.set_xlim(0, d["total"])
    ax.set_ylim(-0.6, 0.6)
    ax.set_yticks([])
    ax.set_xlabel("Toffolis (total 5,725,461)")
    ax.set_title("DQI reference: the two Euclid passes are 74% of the cost", color=INK, fontsize=10)
    return fig


def dfthcsos_baseline_split() -> plt.Figure:
    """The dfthcsos baseline's T_total and Q_total, by part."""
    d = load()["primers"]["dfthcsos_baseline"]
    short = {
        "state preparation and Givens (formulas)": "formulas",
        "state-preparation qubits": "state\nprep",
        "angle words (J x brot)": "angle\nwords",
    }
    fig, axes = plt.subplots(2, 1, figsize=(7.2, 3.4))
    for ax, key, total, title in (
        (axes[0], "t_parts", d["t_total"], "T_total (Toffolis)"),
        (axes[1], "q_parts", d["q_total"], "Q_total (qubits)"),
    ):
        _stacked(ax, 0, [(short.get(n, n), v) for n, v in d[key]], [PUBLIC, REF, OURS][: len(d[key])])
        ax.set_xlim(0, total)
        ax.set_ylim(-0.6, 0.6)
        ax.set_yticks([])
        ax.set_title(f"{title}: {total:,}", color=INK, fontsize=10, loc="left")
    fig.tight_layout()
    return fig


# --- cost model ------------------------------------------------------------------------------------


def _iso_ratio_lines(
    ax: plt.Axes,
    levels: list[float],
    cost_of: Callable[[np.ndarray], np.ndarray],
    x: np.ndarray,
    base: float,
    xlim: tuple[float, float],
    ylim: tuple[float, float],
) -> None:
    """Dashed lines of equal score ratio, each labelled where it is last inside the axes."""
    for r in levels:
        y = (base / r) / cost_of(x)
        ax.plot(x, y, color=INK, lw=0.8, ls="--", alpha=0.7)
        inside = np.where((y >= ylim[0] * 1.05) & (y <= ylim[1] * 0.95) & (x <= xlim[1] * 0.97))[0]
        if len(inside):
            i = inside[-1]
            ax.text(x[i], y[i], f" {r:g}x", color=INK, fontsize=8.5, va="bottom")


def _scatter(ax: plt.Axes, pts: list[dict], xkey: str, ykey: str) -> None:  # type: ignore[type-arg]
    colours = {"ours": OURS, "public": PUBLIC, "reference": REF}
    for p in pts:
        ax.plot(p[xkey], p[ykey], "o", color=colours[p["kind"]], ms=8)
        dx, dy = p.get("offset", (8, 6))
        ax.annotate(
            p["label"],
            (p[xkey], p[ykey]),
            textcoords="offset points",
            xytext=(dx, dy),
            fontsize=8.5,
            color=colours[p["kind"]],
            ha="left" if dx >= 0 else "right",
        )


def iso_cost_invsqrt() -> plt.Figure:
    """invsqrt: cost = Q * C. Every point on a dashed line scores the same ratio."""
    d = load()
    base = d["meta"]["baseline_cost"]["invsqrt"]
    ref = d["invsqrt"]["reference"]
    pts = [ref, *d["invsqrt"]["points"]]
    for p in pts:
        p["c"] = p["cost"] / p["qubits"]
    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    x = np.geomspace(30, 300, 100)
    _iso_ratio_lines(ax, [1, 5, 10, 25], lambda q: q, x, base, (30, 380), (800, 30000))
    _scatter(ax, pts, "qubits", "c")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(30, 380)
    ax.set_ylim(800, 30000)
    ax.set_xlabel("logical qubits Q")
    ax.set_ylabel("Toffoli-equivalents C  (cost = Q · C)")
    ax.set_title(
        "invsqrt: fewer qubits and fewer Toffolis both move a circuit up the ratio lines",
        color=INK,
        fontsize=10,
    )
    return fig


def iso_cost_dqi() -> plt.Figure:
    """dqi: cost = R * Q^2 * T. Qubits are squared, so a 1% cut in Q is worth a 2% cut in T."""
    d = load()
    base = d["meta"]["baseline_cost"]["dqi"]
    r = d["meta"]["dqi_r_eps"]
    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    x = np.geomspace(700, 2200, 100)
    _iso_ratio_lines(ax, [5, 10, 30, 60], lambda q: r * q**2, x, base, (700, 2800), (3e5, 1.2e6))
    _scatter(ax, d["dqi"]["points"], "qubits", "toffoli")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(700, 2800)
    ax.set_ylim(3e5, 1.2e6)
    ax.set_xlabel("logical qubits Q")
    ax.set_ylabel("Toffolis T  (cost = R · Q² · T)")
    ax.set_title("dqi: the same picture with Q squared", color=INK, fontsize=10)
    return fig


FIGURES: dict[str, Callable[[], plt.Figure]] = {
    "argand-plane": argand_plane,
    "phase-wheel": phase_wheel,
    "interference-bars": interference_bars,
    "circuit-toffoli-and": circuit_toffoli_and,
    "circuit-mbuc": circuit_mbuc,
    "circuit-bell": circuit_bell,
    "circuit-adder": circuit_adder,
    "state-vector-growth": state_vector_growth,
    "invsqrt-reference-stages": invsqrt_reference_stages,
    "dqi-reference-split": dqi_reference_split,
    "dfthcsos-baseline-split": dfthcsos_baseline_split,
    "iso-cost-invsqrt": iso_cost_invsqrt,
    "iso-cost-dqi": iso_cost_dqi,
}


def render(name: str, path: Path) -> None:
    fig = FIGURES[name]()
    fig.savefig(path, format="svg", metadata={"Date": None, "Creator": "analysis.learn_figures"})
    plt.close(fig)


WIDGET_DATA = Path(__file__).resolve().parents[1] / "docs" / "javascripts" / "widgets-data.mjs"


def widget_data() -> str:
    """The numbers the browser widgets read, as an ES module generated from learn.json."""
    d = load()
    data = {**d["widgets"], "dqi_r_eps": d["meta"]["dqi_r_eps"], "invsqrt": d["invsqrt"], "dqi": d["dqi"]}
    data["invsqrt"] = {"points": [d["invsqrt"]["reference"], *d["invsqrt"]["points"]]}
    header = "// Generated by analysis/learn_figures.py from analysis/numbers/learn.json; do not edit.\n"
    return header + "export const DATA = " + json.dumps(data, indent=1, sort_keys=True) + ";\n"


def main(out: Path) -> None:
    WIDGET_DATA.write_text(widget_data(), encoding="utf-8")
    print("wrote", WIDGET_DATA)

    out.mkdir(parents=True, exist_ok=True)
    for name in FIGURES:
        render(name, out / f"{name}.svg")
        print("wrote", out / f"{name}.svg")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/img/learn"))
