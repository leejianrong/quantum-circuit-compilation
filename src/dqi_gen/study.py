"""Aggregate structure of a DQI circuit from its text dump (ADR-0009 stage 2, QCC-19).

Streams the text form of a circuit and keeps only counts: instruction mix, Toffoli-like gates per window,
how many distinct qubit ids each window touches, and per qubit block its first and last use. Nothing keeps
or prints gate lists; the report is a few kilobytes of statistics about layout and stage order.

    python -m dqi_gen.study circuit.kmb --out study.json         # kmb is dumped to text in a temp dir
"""

from __future__ import annotations

import argparse
import collections
import importlib
import json
import os
import re
import tempfile
from collections.abc import Iterable
from typing import Any

TOFFOLI = ("CCX", "CCZ", "CSWAP")
QRE = re.compile(r"q(\d+)")
TAG = re.compile(r'INFO_TAG "([^"]*)"')


def scan(lines: Iterable[str], window: int = 200_000, block: int = 12) -> dict[str, Any]:
    mix: collections.Counter[str] = collections.Counter()
    first: dict[int, int] = {}
    last: dict[int, int] = {}
    tof_touch: collections.Counter[int] = collections.Counter()
    wins: list[dict[str, Any]] = []
    tags: list[tuple[int, str]] = []
    cur_tof = 0
    cur_ids: set[int] = set()
    i = 0
    for i, line in enumerate(lines):
        op = line.split(" ", 1)[0].rstrip("\n")
        mix[op] += 1
        if op == "INFO_TAG":
            m = TAG.match(line)
            if m and len(tags) < 4000:
                tags.append((i, m.group(1)))
        elif op not in ("APPEND_TO_REGISTER", "REGISTER"):
            ids = [int(x) for x in QRE.findall(line)]
            for q in ids:
                first.setdefault(q, i)
                last[q] = i
            cur_ids.update(ids)
            if op in TOFFOLI:
                cur_tof += 1
                for q in ids:
                    tof_touch[q] += 1
        if (i + 1) % window == 0:
            wins.append({"end": i + 1, "toffoli": cur_tof, "distinct_qubits": len(cur_ids)})
            cur_tof, cur_ids = 0, set()
    wins.append({"end": i + 1, "toffoli": cur_tof, "distinct_qubits": len(cur_ids)})
    blocks: dict[int, dict[str, int]] = {}
    for q in sorted(first):
        b = blocks.setdefault(q // block, {"first": first[q], "last": last[q], "toffoli_touches": 0})
        b["first"] = min(b["first"], first[q])
        b["last"] = max(b["last"], last[q])
        b["toffoli_touches"] += tof_touch[q]
    return {
        "instructions": i + 1,
        "qubit_ids": len(first),
        "max_id": max(first) if first else -1,
        "mix": dict(mix.most_common()),
        "windows": wins,
        "blocks": {str(k): v for k, v in blocks.items()},
        "tags": tags,
    }


def dump_text(path: str, out: str) -> None:
    importlib.import_module("kickmix").Circuit.from_file(path).to_file(out, format="kmx")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("circuit")
    p.add_argument("--out", required=True)
    p.add_argument("--window", type=int, default=200_000)
    a = p.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        text = os.path.join(tmp, "c.kmx")
        dump_text(a.circuit, text)
        with open(text) as f:
            result = scan(f, a.window)
    with open(a.out, "w") as f:
        json.dump(result, f)
    print(json.dumps({k: result[k] for k in ("instructions", "qubit_ids", "max_id", "mix")}))


if __name__ == "__main__":
    main()
