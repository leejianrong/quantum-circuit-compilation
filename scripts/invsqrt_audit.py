"""Per-stage Toffoli counts of the host's reference invsqrt circuit (QCC-11).

Usage: QCC_DATA=$PWD/data uv run python scripts/invsqrt_audit.py

Builds `data/verifiers/invsqrt/nr_reference_circuit.py` with kickmix and attributes each
CCX/CCZ/CSWAP to the innermost second-level `mark` block (children of compute_y1/uncompute_y1).
Static counts: the verifier averages per shot, which only matters for conditional blocks.
"""

import collections
import os
import pathlib
import sys

data = pathlib.Path(os.environ.get("QCC_DATA", "data"))
sys.path += [str(data / "verifiers")]

from invsqrt.nr_reference_circuit import Precision, build_nr_circuit  # noqa: E402

TOFFOLI = ("CCX", "CCZ", "CSWAP")


def stage_counts(circuit: object) -> dict[str, int]:
    stack: list[str] = []
    counts: collections.Counter[str] = collections.Counter()
    for line in str(circuit).splitlines():
        if line.startswith("INFO_TAG"):
            tag = line.split('"')[1]
            if tag.startswith("@enter:"):
                stack.append(tag[7:])
            elif tag.startswith("@exit:"):
                stack.pop()
        elif line.split(" ")[0] in TOFFOLI:
            # level 1 is compute_y1 / uncompute_y1, level 2 the stage
            name = stack[1] if len(stack) > 1 else (stack[0] if stack else "top")
            direction = "fwd" if stack and stack[0] == "compute_y1" else "rev"
            counts[f"{name} ({direction})"] += 1
    return dict(counts)


if __name__ == "__main__":
    c = build_nr_circuit(10, prec=Precision())
    stats = c.operation_statistics()
    print("qubits", c.num_qubits, "toffolis", stats.num_toffoli_like, "ops", dict(stats.items()))
    for k, v in sorted(stage_counts(c).items()):
        print(f"{k:32s}{v:6d}")
