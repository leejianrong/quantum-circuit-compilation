"""Multi-page PDF report from the analysis data (matplotlib only).

uv run python -m analysis.report [out.pdf]       # default out/reports/qcc-analysis.pdf
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

from analysis import dqi_figures  # noqa: E402


def title_page(d: dict) -> plt.Figure:  # type: ignore[type-arg]
    t = d["totals"]
    o, h = t["ours"], t["theirs"]
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.text(0.08, 0.92, "QCC analysis report", fontsize=22, weight="bold")
    fig.text(0.08, 0.88, "DQI: our circuit against the best public one", fontsize=13)
    rows = [
        ("", "ours", "best public"),
        ("qubits", f"{o['qubits']}", f"{h['qubits']}"),
        ("Toffoli-like gates", f"{o['toffoli_like']:,}", f"{h['toffoli_like']:,}"),
        ("worst-salt cost", f"{o['worst_salt_cost']:.4e}", f"{h['worst_salt_cost']:.4e}"),
        (
            "ratio to baseline",
            f"{t['baseline_cost'] / o['worst_salt_cost']:.2f}x",
            f"{t['baseline_cost'] / h['worst_salt_cost']:.2f}x",
        ),
    ]
    for i, r in enumerate(rows):
        y = 0.82 - i * 0.035
        fig.text(0.08, y, r[0], fontsize=11)
        fig.text(0.42, y, r[1], fontsize=11, family="monospace")
        fig.text(0.65, y, r[2], fontsize=11, family="monospace")
    fig.text(
        0.08,
        0.60,
        "Tags: M measured by us, V read from the other builder's source or recorded data, I inferred.\n"
        "Numbers come from analysis/numbers/dqi.json; every figure is regenerated from that file.",
        fontsize=9,
    )
    return fig


def build(out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    d = dqi_figures.load()
    with PdfPages(out) as pdf:
        pdf.savefig(title_page(d))
        plt.close("all")
        for fn in dqi_figures.FIGURES.values():
            fig = fn(d)
            pdf.savefig(fig)
            plt.close(fig)
    return out


if __name__ == "__main__":
    print(build(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("out/reports/qcc-analysis.pdf")))
