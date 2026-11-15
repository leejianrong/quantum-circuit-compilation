"""Per-stage and per-node Toffoli counts of a `fixed.py --stage-log` circuit (QCC-19).

    python -m dqi_gen.stages study.json    # study.json: `python -m dqi_gen.study X.kmb --out study.json`

Counts are the Toffoli-like gates between consecutive `stage:` tags, the same unit as
`analysis/numbers/dqi.json` (`stage_ledger_native_both`, `extractor_nodes`).
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any

# (group, tag that closes it); a group starts where the previous one ended.
BOUNDARIES = (
    ("extract fwd", "extract_fwd"),
    ("synthesis fwd", "synthesis_fwd"),
    ("outer fwd", "outer_fwd"),
    ("finish fwd", "finish_fwd"),
    ("scan", "scan"),
    ("finish + outer return", "outer_return"),
    ("synthesis return", "synthesis_return"),
    ("extract return", "extract_return"),
)
_NODE = re.compile(r"raw_query_(prefix|return)_(\d+)$")


def tag_deltas(tag_cum: list[list[Any]]) -> list[tuple[str, int]]:
    """`[(stage name, Toffolis since the previous tag)]` for the `stage:` tags, in order."""
    out: list[tuple[str, int]] = []
    prev = 0
    for tag, _, cum in tag_cum:
        if tag.startswith("stage:"):
            out.append((tag.removeprefix("stage:"), cum - prev))
            prev = cum
    return out


def stage_ledger(study: dict[str, Any]) -> dict[str, Any]:
    deltas = tag_deltas(study["tag_cum"])
    groups: dict[str, int] = {}
    acc = 0
    want = iter(BOUNDARIES)
    group, closing = next(want)
    for name, d in deltas:
        acc += d
        if name == closing:
            groups[group] = acc
            acc = 0
            nxt = next(want, None)
            if nxt is None:
                break
            group, closing = nxt
    fwd: dict[int, int] = {}
    ret: dict[int, int] = {}
    for name, d in deltas:
        m = _NODE.match(name)
        if m:
            (fwd if m.group(1) == "prefix" else ret)[int(m.group(2))] = d
    return {
        "groups": groups,
        "extract_fwd_nodes": [fwd[i] for i in sorted(fwd)],
        "extract_ret_nodes": [ret[i] for i in sorted(ret)],
        "total": sum(groups.values()),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("study")
    a = p.parse_args()
    with open(a.study) as f:
        print(json.dumps(stage_ledger(json.load(f))))


if __name__ == "__main__":
    main()
