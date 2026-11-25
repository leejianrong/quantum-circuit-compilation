"""`bench index`: a cached, per-circuit index for the Circuit Explorer (QCC-71, phase 1).

For one circuit file this writes ``<out>/<sha8>/summary.json`` (counts, a width series, inferred modules with
their gate mix and wires) and ``<out>/<sha8>/pages/NNN.json`` (the instruction text in fixed-size chunks). The
key is the file's sha256, the same id the ledger uses, and an entry is skipped when it already exists at the
current ``ANALYSER_VERSION``. Nothing here is committed: the pages are the circuit itself.

Circuits carry no module tags (spike, 2026-11-25), so modules are *inferred*: the sampled live-width series is
cut into ``k`` pieces by greedy binary segmentation (each split chosen to cut the squared error most). The
summary records that source so a page can say so. Only invsqrt is supported so far, because the width
simulation is specific to its 22-bit input.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import tempfile
from collections import Counter
from typing import Any

import numpy as np

from bench import ledger
from invsqrt_gen.port import width as widthmod

ANALYSER_VERSION = 1
DEFAULT_OUT = pathlib.Path("out/circuit-index")
PAGE_SIZE = 2000
STRIP_POINTS = 600
QUBIT = re.compile(r"q(\d+)")
CLASSICAL_ONLY = ("PUSH_CONDITION", "POP_CONDITION")


def segment(width: np.ndarray, k: int, min_len: int = 50) -> list[tuple[int, int]]:
    """Cut ``width`` into at most ``k`` runs, half-open ``(start, end)``, by greedy binary segmentation."""
    n = len(width)
    w = width.astype(float)
    c1 = np.concatenate([[0.0], np.cumsum(w)])
    c2 = np.concatenate([[0.0], np.cumsum(w * w)])

    def sse(a: int, b: int) -> float:
        s, s2, m = c1[b] - c1[a], c2[b] - c2[a], b - a
        return float(s2 - s * s / m)

    def best_split(a: int, b: int) -> tuple[float, int]:
        if b - a < 2 * min_len:
            return 0.0, -1
        cuts = np.arange(a + min_len, b - min_len + 1)
        left = (c2[cuts] - c2[a]) - (c1[cuts] - c1[a]) ** 2 / (cuts - a)
        right = (c2[b] - c2[cuts]) - (c1[b] - c1[cuts]) ** 2 / (b - cuts)
        gain = sse(a, b) - (left + right)
        i = int(np.argmax(gain))
        return float(gain[i]), int(cuts[i])

    segs = [(0, n)]
    cand = {(0, n): best_split(0, n)}
    while len(segs) < k:
        pick = max(segs, key=lambda s: cand[s][0])
        gain, cut = cand[pick]
        if cut < 0 or gain <= 1e-9:
            break
        segs.remove(pick)
        for s in ((pick[0], cut), (cut, pick[1])):
            segs.append(s)
            cand[s] = best_split(*s)
    return sorted(segs)


def instructions(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]


def line_widths(lines: list[str], samples: int, seed: int) -> np.ndarray:
    """Live width at every instruction line. Condition push/pop lines carry the previous width."""
    prof = widthmod.profile("\n".join(lines), samples, seed)
    out = np.empty(len(lines), dtype=np.int64)
    step, prev = 0, int(prof.width[0])
    for i, ln in enumerate(lines):
        if ln.split()[0] in CLASSICAL_ONLY:
            out[i] = prev
        else:
            prev = out[i] = int(prof.width[step])
            step += 1
    return out


def build(
    text: str,
    *,
    name: str,
    sha256: str,
    k: int = 24,
    samples: int = 256,
    seed: int = 0,
    page_size: int = PAGE_SIZE,
) -> dict[str, Any]:
    lines = instructions(text)
    ops = [ln.split()[0] for ln in lines]
    widths = line_widths(lines, samples, seed)
    modules = []
    for i, (a, b) in enumerate(segment(widths, k), start=1):
        mix = Counter(ops[a:b])
        wires: set[int] = set()
        for ln in lines[a:b]:
            wires.update(int(m) for m in QUBIT.findall(ln))
        modules.append(
            {
                "id": f"M{i}",
                "start": a,
                "end": b,
                "ops": dict(mix.most_common()),
                "ccx": mix.get("CCX", 0),
                "peak_width": int(widths[a:b].max()),
                "min_width": int(widths[a:b].min()),
                "wires": sorted(wires),
            }
        )
    step = max(1, -(-len(widths) // STRIP_POINTS))
    strip = [int(widths[i : i + step].max()) for i in range(0, len(widths), step)]
    return {
        "analyser_version": ANALYSER_VERSION,
        "bench": "invsqrt",
        "name": name,
        "sha256": sha256,
        "instructions": len(lines),
        "ops": dict(Counter(ops).most_common()),
        "ccx": ops.count("CCX"),
        "peak_width": int(widths.max()),
        "modules": modules,
        "module_source": "inferred from sampled live width",
        "cost_tier": "static",
        "width_strip": {"step": step, "values": strip},
        "samples": samples,
        "seed": seed,
        "page_size": page_size,
        "pages": -(-len(lines) // page_size),
    }


def write(out: pathlib.Path, summary: dict[str, Any], lines: list[str]) -> None:
    page_size = summary["page_size"]
    pages = out / "pages"
    pages.mkdir(parents=True, exist_ok=True)
    for p in range(summary["pages"]):
        chunk = lines[p * page_size : (p + 1) * page_size]
        (pages / f"{p:03d}.json").write_text(json.dumps({"first": p * page_size, "lines": chunk}))
    (out / "summary.json").write_text(json.dumps(summary, indent=1))


def to_text(path: pathlib.Path) -> str:
    import kickmix as km  # type: ignore[import-not-found,unused-ignore]

    with tempfile.TemporaryDirectory() as d:
        dst = pathlib.Path(d) / "c.txt"
        km.Circuit.from_file(path).to_file(dst)
        return dst.read_text()


def index_file(
    path: pathlib.Path,
    root: pathlib.Path = DEFAULT_OUT,
    *,
    force: bool = False,
    k: int = 24,
    samples: int = 256,
) -> tuple[str, pathlib.Path]:
    """Index one circuit file. Returns ``("cached" | "built", entry directory)``."""
    sha = ledger.sha256_path(path)
    out = root / sha[:8]
    summary = out / "summary.json"
    if (
        not force
        and summary.exists()
        and json.loads(summary.read_text()).get("analyser_version") == ANALYSER_VERSION
    ):
        return "cached", out
    lines = instructions(to_text(path))
    s = build("\n".join(lines), name=path.name, sha256=sha, k=k, samples=samples)
    write(out, s, lines)
    return "built", out


def add_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser("index", help="index circuit files for the Circuit Explorer (cached by sha256)")
    p.add_argument("paths", nargs="*", type=pathlib.Path, help="default: best/invsqrt/*.kmb")
    p.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    p.add_argument("--force", action="store_true", help="rebuild even if the entry is current")
    p.add_argument("--modules", type=int, default=24, help="number of inferred modules")
    p.add_argument("--samples", type=int, default=256, help="inputs sampled for the width series")


def run(a: argparse.Namespace) -> int:
    paths = a.paths or sorted(pathlib.Path("best/invsqrt").glob("*.kmb"))
    if not paths:
        print("error: no circuit files (best/invsqrt is empty)")
        return 2
    for p in paths:
        status, out = index_file(p, a.out, force=a.force, k=a.modules, samples=a.samples)
        print(f"{status}\t{out}")
    return 0
