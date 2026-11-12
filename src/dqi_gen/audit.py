"""Stage and sub-stage Toffoli breakdown of a DQI decoder circuit, from its `mark` (INFO_TAG) blocks.

Works on any kickmix circuit with marks (the host reference, or ours). The circuit is dumped as text and
streamed, so a full-size circuit needs no second in-memory copy (run those on Kaggle, ADR-0002).
Counts are static (CCX + CCZ + CSWAP, conditioned or not), like `operation_statistics()`.

    QCC_DATA=data uv run python -m dqi_gen.audit --m 4095 --n 70 --degree 12   # Kaggle only
    QCC_DATA=data uv run python -m dqi_gen.audit --m 63 --n 10 --degree 6      # seconds, local
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import tempfile
from collections.abc import Iterable
from typing import Any

from dqi_gen import host

TOFFOLI_OPS = ("CCX ", "CCZ ", "CSWAP ")
ENTER, EXIT = 'INFO_TAG "@enter:', 'INFO_TAG "@exit:'


def tally(lines: Iterable[str]) -> tuple[dict[tuple[str, ...], int], int]:
    """Toffoli-like count per mark path (exclusive of nested marks) and the total."""
    stack: list[str] = []
    excl: dict[tuple[str, ...], int] = collections.defaultdict(int)
    total = 0
    for line in lines:
        if line.startswith(ENTER):
            stack.append(line[len(ENTER) : line.rindex('"')])
        elif line.startswith(EXIT):
            name = line[len(EXIT) : line.rindex('"')]
            if not stack or stack[-1] != name:
                raise ValueError(f"unbalanced mark {name!r}, stack {stack}")
            stack.pop()
        elif line.startswith(TOFFOLI_OPS):
            excl[tuple(stack)] += 1
            total += 1
    return dict(excl), total


def breakdown(excl: dict[tuple[str, ...], int], total: int) -> dict[str, Any]:
    """Top-level stage totals and inclusive totals per mark name (a name's own and nested blocks)."""
    stages: dict[str, int] = collections.defaultdict(int)
    inclusive: dict[str, int] = collections.defaultdict(int)
    for path, count in excl.items():
        stages[path[0] if path else "(unmarked)"] += count
        for name in set(path):
            inclusive[name] += count
    order = sorted(stages.items(), key=lambda kv: -kv[1])
    return {
        "total": total,
        "stages": {k: {"toffolis": v, "share": round(v / total, 6)} for k, v in order},
        "marks": {
            k: {"toffolis": v, "share": round(v / total, 6)}
            for k, v in sorted(inclusive.items(), key=lambda kv: -kv[1])
        },
    }


def audit_circuit(circuit: Any) -> dict[str, Any]:
    """Audit an in-memory circuit; checks the tally against `operation_statistics()`."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "c.kmx")
        circuit.to_file(path, format="kmx")
        with open(path) as f:
            excl, total = tally(f)
    expected = int(circuit.operation_statistics().num_toffoli_like)
    if total != expected:
        raise AssertionError(f"tally {total} != operation_statistics {expected}")
    out = breakdown(excl, total)
    out["qubits"] = int(circuit.num_qubits)
    out["reaction_depth"] = int(circuit.reaction_depth())
    return out


def audit_reference(m: int, n: int, degree: int) -> dict[str, Any]:
    out = audit_circuit(host.reference().build_reference_circuit(m, n, degree))
    out["params"] = {"m": m, "n": n, "degree": degree}
    return out


def render(result: dict[str, Any]) -> str:
    rows = [f"params {result['params']}, qubits {result['qubits']}, total {result['total']:,} Toffolis", ""]
    rows += ["| stage | Toffolis | share |", "|---|---:|---:|"]
    rows += [f"| {k} | {v['toffolis']:,} | {v['share']:.1%} |" for k, v in result["stages"].items()]
    rows += ["", "| mark (inclusive) | Toffolis | share |", "|---|---:|---:|"]
    rows += [f"| {k} | {v['toffolis']:,} | {v['share']:.1%} |" for k, v in result["marks"].items()]
    return "\n".join(rows)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--m", type=int, default=4095)
    p.add_argument("--n", type=int, default=70)
    p.add_argument("--degree", type=int, default=12)
    p.add_argument("--json", help="also write the result as JSON to this path")
    a = p.parse_args()
    result = audit_reference(a.m, a.n, a.degree)
    print(render(result))
    if a.json:
        with open(a.json, "w") as f:
            json.dump(result, f, indent=1)


if __name__ == "__main__":
    main()
