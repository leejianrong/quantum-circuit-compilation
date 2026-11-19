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
BRE = re.compile(r"\bb(\d+)")
COND_OPS = ("CX", "SWAP", "CSWAP", "CCX", "CCZ", "CZ", "Z", "X", "R")
TAG = re.compile(r'INFO_TAG "([^"]*)"')


def scan(lines: Iterable[str], window: int = 200_000, block: int = 12) -> dict[str, Any]:
    mix: collections.Counter[str] = collections.Counter()
    first: dict[int, int] = {}
    last: dict[int, int] = {}
    tof_touch: collections.Counter[int] = collections.Counter()
    wins: list[dict[str, Any]] = []
    tags: list[tuple[int, str]] = []
    tag_cum: list[tuple[str, int, int]] = []  # (tag, instruction index, Toffoli-like gates so far)
    total_tof = 0
    cur_tof = 0
    cur_ids: set[int] = set()
    stack: list[str] = []
    cond_bits: list[int] = []  # PUSH_CONDITION bit ids
    origin: dict[int, str] = {}  # classical bit id -> 'hmr' or 'derived'
    cond_mix: dict[str, collections.Counter[str]] = {o: collections.Counter() for o in COND_OPS}
    cond_depth_tof: collections.Counter[int] = collections.Counter()
    cond_origin: dict[str, collections.Counter[str]] = {o: collections.Counter() for o in COND_OPS}
    paths: dict[str, dict[str, Any]] = {}
    i = 0
    for i, line in enumerate(lines):
        op = line.split(" ", 1)[0].rstrip("\n")
        mix[op] += 1
        if op == "INFO_TAG":
            m = TAG.match(line)
            if m:
                name = m.group(1)
                if name.startswith("@enter:"):
                    stack.append(name[7:])
                    rec = paths.setdefault(
                        " > ".join(stack[:3]), {"enter": 0, "toffoli": 0, "first": i, "ids": set()}
                    )
                    if len(stack) <= 3:
                        rec["enter"] += 1
                elif name.startswith("@exit:") and stack:
                    stack.pop()
                if len(tags) < 5000:
                    tags.append((i, name))
                    tag_cum.append((name, i, total_tof))
        elif op == "PUSH_CONDITION":
            bits = [int(x) for x in BRE.findall(line)]
            cond_bits.append(bits[0] if bits else -1)
        elif op == "POP_CONDITION":
            if cond_bits:
                cond_bits.pop()
        elif op.startswith("BIT_") or op == "HMR":
            bits = [int(x) for x in BRE.findall(line)]
            if bits:  # the first classical operand is the one written
                origin.setdefault(bits[0], "hmr" if op == "HMR" else "derived")
                if op == "HMR":
                    origin[bits[0]] = "hmr"
        elif op not in ("APPEND_TO_REGISTER", "REGISTER"):
            if op in COND_OPS:
                inline = BRE.findall(line)
                cbit = int(inline[0]) if inline else (cond_bits[-1] if cond_bits else None)
                cond_mix[op]["conditioned" if cbit is not None and cbit >= 0 else "plain"] += 1
                if cbit is not None and cbit >= 0:
                    cond_origin[op][origin.get(cbit, "unknown")] += 1
                if op in TOFFOLI:
                    cond_depth_tof[len(cond_bits) + (1 if inline else 0)] += 1
            ids = [int(x) for x in QRE.findall(line)]
            for q in ids:
                first.setdefault(q, i)
                last[q] = i
            cur_ids.update(ids)
            if stack:
                prec = paths[" > ".join(stack[:3])]
                prec["ids"].update(ids)
                if op in TOFFOLI:
                    prec["toffoli"] += 1
            if op in TOFFOLI:
                cur_tof += 1
                total_tof += 1
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
        "tag_cum": tag_cum,
        "total_toffoli": total_tof,
        "cond_mix": {o: dict(c) for o, c in cond_mix.items()},
        "cond_origin": {o: dict(c) for o, c in cond_origin.items()},
        "cond_depth_toffoli": {str(k): v for k, v in sorted(cond_depth_tof.items())},
        "paths": {
            k: {"enter": v["enter"], "toffoli": v["toffoli"], "first": v["first"], "qubits": len(v["ids"])}
            for k, v in paths.items()
        },
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
