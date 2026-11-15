"""A small circuit drawer: a gate list in, a matplotlib figure out. No dependencies beyond matplotlib.

    fig = draw([("CCX", 0, 1, 2)], ["a", "b", "anc"])

Gates are tuples ``(kind, *wires)``, optionally followed by a dict of options. Kinds:

* single-qubit boxes: ``H X Z S T`` and ``HMR`` (Hadamard, measure into a classical bit, reset to 0)
* ``CX`` (control, target), ``CZ`` (a, b), ``CCX`` (control, control, target)

Options: ``{"cond": "m"}`` marks a gate that runs only when classical bit ``m`` is 1 (drawn in the accent
colour with an ``if m`` label); ``{"label": "text"}`` overrides a box label. Columns are laid out left to
right, one gate per column, so the picture reads like the gate list.
"""

from __future__ import annotations

from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, Rectangle  # noqa: E402

INK = "#8a93a0"
ACCENT = "#c05621"
BOX = "#2b6cb0"
Gate = tuple[Any, ...]


def _split(gate: Gate) -> tuple[str, list[int], dict[str, str]]:
    opts: dict[str, str] = {}
    items = list(gate)
    if isinstance(items[-1], dict):
        opts = items.pop()
    return items[0], items[1:], opts


def draw(gates: list[Gate], wires: list[str], title: str | None = None) -> plt.Figure:
    n = len(wires)
    width = 0.9 * len(gates) + 1.8
    fig, ax = plt.subplots(figsize=(max(3.2, width), 0.75 * n + (0.5 if title else 0.2)))
    fig.patch.set_alpha(0)
    ax.set_facecolor("none")
    x_end = len(gates) + 0.5
    for i, name in enumerate(wires):
        y = -i
        ax.plot([0, x_end], [y, y], color=INK, lw=1, zorder=1)
        ax.text(-0.15, y, name, ha="right", va="center", color=INK, fontsize=10)
    for col, gate in enumerate(gates, start=1):
        kind, ws, opts = _split(gate)
        colour = ACCENT if "cond" in opts else BOX
        ys = [-w for w in ws]
        if len(ws) > 1:
            ax.plot([col, col], [min(ys), max(ys)], color=colour, lw=1.6, zorder=2)
        if kind in ("CX", "CCX"):
            for w in ws[:-1]:
                ax.add_patch(Circle((col, -w), 0.08, color=colour, zorder=3))
            t = -ws[-1]
            ax.add_patch(Circle((col, t), 0.2, fill=True, fc="none", ec=colour, lw=1.6, zorder=3))
            ax.plot([col - 0.2, col + 0.2], [t, t], color=colour, lw=1.6, zorder=4)
            ax.plot([col, col], [t - 0.2, t + 0.2], color=colour, lw=1.6, zorder=4)
        elif kind == "CZ":
            for w in ws:
                ax.add_patch(Circle((col, -w), 0.08, color=colour, zorder=3))
        else:
            label = opts.get("label", kind)
            w = 0.62 if len(label) > 1 else 0.44
            ax.add_patch(
                Rectangle((col - w / 2, -ws[0] - 0.22), w, 0.44, fc="white", ec=colour, lw=1.6, zorder=3)
            )
            ax.text(col, -ws[0], label, ha="center", va="center", color="#1a202c", fontsize=9, zorder=4)
        if "cond" in opts:
            ax.text(col, max(ys) + 0.38, f"if {opts['cond']}", ha="center", color=ACCENT, fontsize=8)
    ax.set_xlim(-0.9, x_end + 0.2)
    ax.set_ylim(-n + 0.4, 0.7)
    ax.axis("off")
    if title:
        ax.set_title(title, color=INK, fontsize=10)
    fig.tight_layout()
    return fig
