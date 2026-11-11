"""Circuit structure statistics from kickmix, for ledger v2 (docs/MEASUREMENT.md)."""

import pathlib
import re
from typing import Any

_RECT = re.compile(
    r'<rect x="([\d.]+)" y="(-?[\d.]+)" width="([\d.]+)" height="[\d.]+" [^>]*fill="red"[^>]*/>'
)
_LABEL = re.compile(r">([^<>]+)</text>")
_REPEAT = re.compile(r" \(x\d+\)$")


def stage_shares(svg: str) -> dict[str, float] | None:
    """Top-level `mark` block shares from `flame_chart_svg()`; None when the circuit has no marks.

    The chart is laid out left to right on a 1000-unit axis by CCZ-state count, so a top-level red
    bar's width over 1000 is that stage's share. Nested marks (y != 0) are skipped, and a block
    repeated n times is drawn once as "name (xn)" with the combined width.
    """
    shares: dict[str, float] = {}
    lines = svg.splitlines()
    for i, line in enumerate(lines):
        m = _RECT.search(line)
        if not m or float(m.group(2)) != 0.0 or i + 1 >= len(lines):
            continue
        label = _LABEL.search(lines[i + 1])
        if label:
            name = _REPEAT.sub("", label.group(1))
            shares[name] = shares.get(name, 0.0) + float(m.group(3)) / 1000.0
    return {k: round(v, 6) for k, v in shares.items()} or None


def circuit_stats(circuit: Any) -> dict[str, Any]:
    """Toffolis, qubits, reaction depth and stage shares of one kickmix circuit.

    `toffolis` is `operation_statistics().num_toffoli_like` (CCX + CCZ + CSWAP, counted statically).
    The DQI/invsqrt verifiers average per shot, so the official cost can be lower.
    """
    return {
        "toffolis": int(circuit.operation_statistics().num_toffoli_like),
        "qubits": int(circuit.num_qubits),
        "depth": int(circuit.reaction_depth()),
        "stage_shares": stage_shares(circuit.flame_chart_svg()),
    }


def path_stats(path: pathlib.Path) -> dict[str, Any]:
    """Statistics for a circuit file, or a dfthcsos directory (angle circuits: toffolis and depth
    summed, qubits is the maximum, stage_shares left empty)."""
    import kickmix  # type: ignore[import-not-found,unused-ignore]

    def load(p: pathlib.Path) -> Any:
        return kickmix.Circuit.from_file(p, format=p.suffix.removeprefix("."))

    if path.is_file():
        return circuit_stats(load(path))
    parts = [circuit_stats(load(p)) for p in sorted(path.glob("angle_k_*.km[xb]"))]
    if not parts:
        raise FileNotFoundError(f"no angle_k_* circuits in {path}")
    return {
        "toffolis": sum(s["toffolis"] for s in parts),
        "qubits": max(s["qubits"] for s in parts),
        "depth": sum(s["depth"] for s in parts),
        "stage_shares": None,
    }
