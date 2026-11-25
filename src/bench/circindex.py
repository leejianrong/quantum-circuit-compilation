"""`bench index`: a cached, per-circuit index for the Circuit Explorer (QCC-71).

For one circuit file this writes ``<out>/<sha8>/summary.json`` (counts, a width series, inferred modules with
their gate mix and wires) and ``<out>/<sha8>/pages/NNN.json`` (listed instructions in chunks of rows
``[line, text, conditioned]``). The key is the file's sha256, the same id the ledger uses, and an entry is
skipped when it already exists at the current ``ANALYSER_VERSION``. Nothing here is committed: the pages are
the circuit itself.

Circuits carry no module tags (spike, 2026-11-25), so modules are *inferred*: a live-width series is cut into
``k`` pieces by greedy binary segmentation on three block-averaged features: the live width, the density of
Toffoli-like gates and the density of classical-only bookkeeping. invsqrt uses
the sampled simulation of ``invsqrt_gen.port.width``, which needs its 22-bit input. Every other benchmark
uses the touch-interval width, the number of qubits between their first and last use, which needs no
semantics. Small circuits list every instruction; large ones (DQI has 70 million) list only the priced
gates: Toffoli-like gates and non-Clifford ``Z_POW`` rotations. Clifford counts stay in each module's mix.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import tempfile
from array import array
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import numpy as np

from bench import ledger
from invsqrt_gen.port import activity as activitymod
from invsqrt_gen.port import width as widthmod

ANALYSER_VERSION = 5
DEFAULT_OUT = pathlib.Path("out/circuit-index")
BENCHES = ("invsqrt", "dqi", "dfthcsos")
PAGE_SIZE = 2000
STRIP_POINTS = 600
LIST_ALL_MAX = 200_000  # instructions; above this only priced gates are listed
SEGMENT_BLOCKS = 20_000  # the series is block-averaged to at most this many points before segmentation
MIN_MODULE = 50  # instructions
FIRING_CHUNK = 262_144
TOFFOLI_LIKE = frozenset({"CCX", "CCZ", "CSWAP"})
CLASSICAL_ONLY = ("PUSH_CONDITION", "POP_CONDITION")


def segment(series: np.ndarray, k: int, min_len: int = 50) -> list[tuple[int, int]]:
    """Cut a series (1-D, or one column per feature) into at most ``k`` runs, half-open ``(start, end)``.

    Greedy binary segmentation: the split that cuts the summed squared error most is taken first.
    """
    w = series.astype(float)
    if w.ndim == 1:
        w = w[:, None]
    n = len(w)
    z = np.zeros((1, w.shape[1]))
    c1 = np.concatenate([z, np.cumsum(w, axis=0)])
    c2 = np.concatenate([z, np.cumsum(w * w, axis=0)])

    def sse(a: int, b: int) -> float:
        s, s2, m = c1[b] - c1[a], c2[b] - c2[a], b - a
        return float((s2 - s * s / m).sum())

    def best_split(a: int, b: int) -> tuple[float, int]:
        if b - a < 2 * min_len:
            return 0.0, -1
        cuts = np.arange(a + min_len, b - min_len + 1)
        na, nb = (cuts - a)[:, None], (b - cuts)[:, None]
        left = (c2[cuts] - c2[a]) - (c1[cuts] - c1[a]) ** 2 / na
        right = (c2[b] - c2[cuts]) - (c1[b] - c1[cuts]) ** 2 / nb
        gain = sse(a, b) - (left + right).sum(axis=1)
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


def features(s: Scan, widths: np.ndarray, f: int) -> np.ndarray:
    """Per-block width, Toffoli density and classical-only density, each scaled to unit variance."""
    n = s.n
    pad = -n % f

    def blocks(v: np.ndarray) -> np.ndarray:
        v = v.astype(float)
        return np.concatenate([v, np.full(pad, v[-1])]).reshape(-1, f).mean(axis=1)

    code = {name: i for i, name in enumerate(s.opnames)}
    ccx = np.isin(s.ops, [code[o] for o in TOFFOLI_LIKE if o in code])
    classical = np.isin(s.ops, [code[o] for o in s.opnames if o.startswith("BIT_") or o in CLASSICAL_ONLY])
    cols = np.stack([blocks(widths), blocks(ccx), blocks(classical)], axis=1)
    sd = cols.std(axis=0)
    return cols / np.where(sd > 0, sd, 1.0)


def segment_modules(s: Scan, widths: np.ndarray, k: int) -> list[tuple[int, int]]:
    """Modules as half-open instruction ranges, from block-averaged width and gate densities."""
    f = max(1, -(-s.n // SEGMENT_BLOCKS))
    cuts = [min(s.n, a * f) for a, _ in segment(features(s, widths, f), k, max(2, MIN_MODULE // f))]
    return list(zip(cuts, cuts[1:] + [s.n], strict=True))


@dataclass
class Scan:
    n: int
    opnames: list[str]
    ops: np.ndarray  # opcode per instruction (index into opnames)
    qubits: np.ndarray  # (n, 3) int16, -1 where absent
    first: dict[int, int]
    last: dict[int, int]
    rows: list[tuple[int, str, bool]]  # listed instructions: (line, text, conditioned)
    listing: str  # "all" or "priced"


def is_listed(op: str, parts: list[str]) -> bool:
    if op in TOFFOLI_LIKE:
        return True
    if op == "Z_POW":
        try:
            return (float(parts[-1]) * 2) % 1.0 != 0.0  # a multiple of 1/2 is Clifford
        except ValueError:
            return True
    return False


def scan(lines: Iterable[str], *, list_all: bool) -> Scan:
    codes: dict[str, int] = {}
    ops = array("B")
    qs = [array("h"), array("h"), array("h")]
    first: dict[int, int] = {}
    last: dict[int, int] = {}
    rows: list[tuple[int, str, bool]] = []
    depth = 0
    n = 0
    for raw in lines:
        ln = raw.strip()
        if not ln or ln[0] == "#":
            continue
        parts = ln.split()
        op = parts[0]
        ops.append(codes.setdefault(op, len(codes)))
        j = 0
        for t in parts[1:]:
            if t[0] == "q" and t[1:].isdigit() and j < 3:
                q = int(t[1:])
                qs[j].append(q)
                j += 1
                if q not in first:
                    first[q] = n
                last[q] = n
        for k in range(j, 3):
            qs[k].append(-1)
        if op == "POP_CONDITION":
            depth -= 1
        if list_all or is_listed(op, parts):
            cond = depth > 0 or (op != "PUSH_CONDITION" and " if b" in ln)
            rows.append((n, ln, cond))
        if op == "PUSH_CONDITION":
            depth += 1
        n += 1
    names = [k for k, _ in sorted(codes.items(), key=lambda kv: kv[1])]
    if n:
        operands = np.stack([np.frombuffer(a, dtype=np.int16) for a in qs], axis=1)
    else:
        operands = np.zeros((0, 3), np.int16)
    listing = "all" if list_all else "priced"
    return Scan(n, names, np.frombuffer(ops, dtype=np.uint8), operands, first, last, rows, listing)


def interval_width(s: Scan) -> np.ndarray:
    """Qubits between their first and last use, at every instruction. Needs no input semantics."""
    diff = np.zeros(s.n + 1, dtype=np.int32)
    for q, a in s.first.items():
        diff[a] += 1
        diff[s.last[q] + 1] -= 1
    return np.cumsum(diff[:-1]).astype(np.int64)


def sampled_width(s: Scan, samples: int, seed: int) -> np.ndarray:
    """invsqrt: the sampled live-width simulation, one value per instruction (condition lines repeat)."""
    assert s.listing == "all", "the sampled width needs every instruction"
    lines = [r[1] for r in s.rows]
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


def exact_firing(s: Scan, limit: int = widthmod.MAX_X) -> dict[int, int]:
    """invsqrt: per Toffoli-like gate, on how many of ``limit`` inputs it fires (one random HMR outcome each).

    Runs the whole domain in chunks (about 40 s for ``bb676b95``). Keys are instruction indices.
    """
    assert s.listing == "all", "the firing pass needs every instruction"
    text = "\n".join(r[1] for r in s.rows)
    total: dict[int, int] = {}
    for lo in range(1, limit + 1, FIRING_CHUNK):
        xs = np.arange(lo, min(lo + FIRING_CHUNK, limit + 1), dtype=np.int64)
        for k, v in activitymod.activity(text, xs, seed=lo).items():
            total[k] = total.get(k, 0) + v
    return total


def build(
    s: Scan,
    *,
    bench: str,
    name: str,
    sha256: str,
    k: int = 24,
    samples: int = 256,
    seed: int = 0,
    page_size: int = PAGE_SIZE,
    firing: dict[int, int] | None = None,
    inputs: int = 0,
) -> dict[str, Any]:
    sampled = bench == "invsqrt"
    widths = sampled_width(s, samples, seed) if sampled else interval_width(s)
    modules = []
    for i, (a, b) in enumerate(segment_modules(s, widths, k), start=1):
        counts = np.bincount(s.ops[a:b], minlength=len(s.opnames))
        ops = {s.opnames[c]: int(counts[c]) for c in np.argsort(-counts, kind="stable") if counts[c]}
        wires = np.unique(s.qubits[a:b])
        modules.append(
            {
                "id": f"M{i}",
                "start": a,
                "end": b,
                "ops": ops,
                "ccx": ops.get("CCX", 0),
                "peak_width": int(widths[a:b].max()),
                "min_width": int(widths[a:b].min()),
                "wires": [int(q) for q in wires if q >= 0],
            }
        )
        if firing is not None:
            fired = [v / inputs for k, v in firing.items() if a <= k < b]
            modules[-1]["toffoli_expected"] = round(sum(fired), 3)
            modules[-1]["toffoli_never"] = sum(1 for x in fired if x == 0)
    step = max(1, -(-len(widths) // STRIP_POINTS))
    strip = [int(widths[i : i + step].max()) for i in range(0, len(widths), step)]
    total = np.bincount(s.ops, minlength=len(s.opnames))
    all_ops = {s.opnames[c]: int(total[c]) for c in np.argsort(-total, kind="stable") if total[c]}
    return {
        "analyser_version": ANALYSER_VERSION,
        "bench": bench,
        "name": name,
        "sha256": sha256,
        "instructions": s.n,
        "ops": all_ops,
        "ccx": all_ops.get("CCX", 0),
        "peak_width": int(widths.max()),
        "modules": modules,
        "module_source": "inferred from width, Toffoli density and classical density",
        "width_method": "sampled simulation" if sampled else "touch interval (first to last use of a qubit)",
        "cost_tier": "exact" if firing is not None else "static",
        "toffoli_expected": round(sum(firing.values()) / inputs, 3) if firing is not None else None,
        "firing_inputs": inputs if firing is not None else None,
        "width_strip": {"step": step, "values": strip},
        "samples": samples if sampled else None,
        "seed": seed if sampled else None,
        "listing": s.listing,
        "listed": len(s.rows),
        "page_size": page_size,
        "pages": -(-len(s.rows) // page_size),
    }


def write(
    out: pathlib.Path,
    summary: dict[str, Any],
    rows: list[tuple[int, str, bool]],
    firing: dict[int, int] | None = None,
) -> None:
    pages = out / "pages"
    pages.mkdir(parents=True, exist_ok=True)
    size = summary["page_size"]
    for p in range(summary["pages"]):
        chunk = [
            [
                ln,
                text,
                int(c),
                None
                if firing is None or ln not in firing
                else round(firing[ln] / summary["firing_inputs"], 4),
            ]
            for ln, text, c in rows[p * size : (p + 1) * size]
        ]
        (pages / f"{p:03d}.json").write_text(json.dumps({"rows": chunk}, separators=(",", ":")))
    (out / "summary.json").write_text(json.dumps(summary, indent=1))


def bench_of(path: pathlib.Path) -> str:
    for part in reversed(path.resolve().parts):
        if part in BENCHES:
            return part
    raise ValueError(f"cannot tell the benchmark of {path}: put it under a directory named one of {BENCHES}")


def index_file(
    path: pathlib.Path,
    root: pathlib.Path = DEFAULT_OUT,
    *,
    bench: str | None = None,
    force: bool = False,
    k: int = 24,
    samples: int = 256,
    exact: bool = False,
    limit: int = widthmod.MAX_X,
) -> tuple[str, pathlib.Path]:
    """Index one circuit file. Returns ``("cached" | "built", entry directory)``."""
    sha = ledger.sha256_path(path)
    out = root / sha[:8]
    summary = out / "summary.json"
    bench = bench or bench_of(path)
    exact = exact and bench == "invsqrt"  # only invsqrt has a firing pass
    if not force and summary.exists():
        have = json.loads(summary.read_text())
        if have.get("analyser_version") == ANALYSER_VERSION and (
            not exact or have.get("cost_tier") == "exact"
        ):
            return "cached", out
    import kickmix as km  # type: ignore[import-not-found,unused-ignore]

    root.mkdir(parents=True, exist_ok=True)
    circuit = km.Circuit.from_file(path)
    with tempfile.TemporaryDirectory(dir=root) as d:
        txt = pathlib.Path(d) / "c.txt"
        circuit.to_file(txt)
        with txt.open() as f:
            s = scan(f, list_all=len(circuit) <= LIST_ALL_MAX)
    firing = None
    if exact:
        firing = exact_firing(s, limit)
    data = build(
        s, bench=bench, name=path.name, sha256=sha, k=k, samples=samples, firing=firing, inputs=limit
    )
    write(out, data, s.rows, firing)
    return "built", out


def add_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser("index", help="index circuit files for the Circuit Explorer (cached by sha256)")
    p.add_argument("paths", nargs="*", type=pathlib.Path, help="default: every .kmb in best/<bench>/")
    p.add_argument("--bench", choices=BENCHES, help="default: the benchmark directory the file is in")
    p.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    p.add_argument("--force", action="store_true", help="rebuild even if the entry is current")
    p.add_argument(
        "--exact", action="store_true", help="invsqrt: add the full-domain firing pass (about a minute)"
    )
    p.add_argument("--modules", type=int, default=24, help="number of inferred modules")
    p.add_argument("--samples", type=int, default=256, help="inputs sampled for the invsqrt width series")


def best_files(best: pathlib.Path = pathlib.Path("best")) -> list[pathlib.Path]:
    return [f for b in BENCHES for f in sorted((best / b).glob("*.kmb"))]


def run(a: argparse.Namespace) -> int:
    paths = a.paths or best_files()
    if not paths:
        print("error: no circuit files (best/ has no .kmb files)")
        return 2
    for p in paths:
        status, out = index_file(
            p, a.out, bench=a.bench, force=a.force, k=a.modules, samples=a.samples, exact=a.exact
        )
        print(f"{status}\t{out}")
    return 0
