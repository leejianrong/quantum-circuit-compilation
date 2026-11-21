"""`bench public-diff`: which circuit files in a fresh public fetch are new to us (QCC-65).

``scripts/fetch_public.sh`` with ``FETCH_SUFFIX=-YYYYMMDD`` downloads every source into new directories and
rewrites ``public/MANIFEST.tsv`` (path, size, sha256; zip members as ``zip!member``). A circuit file is *new*
if its hash occurs in a directory with the suffix, in no other directory and in no ledger row. Hashes are of
the file bytes, which is what ``circuit_sha256`` is for single-file benchmarks; dfthcsos is a set of files,
so every changed file is listed.
"""

import argparse
import csv
import pathlib
import re
from dataclasses import dataclass

from bench import ledger

CIRCUIT = re.compile(r"\.kmb(\.xz!decompressed)?$")
BENCHES = ("invsqrt", "dqi", "dfthcsos")
DEFAULT_MANIFEST = pathlib.Path("public/MANIFEST.tsv")


@dataclass(frozen=True)
class New:
    sha256: str
    path: str
    size: int
    bench: str


def bench_of(path: str) -> str:
    low = path.lower()
    return next((b for b in BENCHES if b in low), "?")


def diff(rows: list[tuple[str, int, str]], suffix: str, known: set[str]) -> list[New]:
    """Circuit files only in ``*suffix`` directories and not in ``known`` (ledger hashes), once per hash."""
    seen_elsewhere: set[str] = set()
    fresh: dict[str, New] = {}
    for path, size, sha in rows:
        if not CIRCUIT.search(path) or sha == "SKIPPED_OVER_CAP":
            continue
        top = path.split("/", 1)[0]
        if not top.endswith(suffix):
            seen_elsewhere.add(sha)
        elif sha not in fresh:
            fresh[sha] = New(sha, path, size, bench_of(path))
    return sorted(
        (n for s, n in fresh.items() if s not in seen_elsewhere and s not in known),
        key=lambda n: (n.bench, n.path),
    )


def read_manifest(path: pathlib.Path) -> list[tuple[str, int, str]]:
    with path.open(newline="") as f:
        return [(r[0], int(r[1]), r[2]) for r in csv.reader(f, delimiter="\t") if len(r) == 3]


def add_parser(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    p = sub.add_parser("public-diff", help="list circuit files in a fresh public fetch that we have not seen")
    p.add_argument("suffix", help="directory suffix of the fresh fetch, e.g. -20261121")
    p.add_argument("--manifest", type=pathlib.Path, default=DEFAULT_MANIFEST)
    p.add_argument("--ledger", type=pathlib.Path, default=ledger.DEFAULT_LEDGER)


def run(a: argparse.Namespace) -> int:
    known = {r.circuit_sha256 for r in ledger.read(a.ledger)}
    new = diff(read_manifest(a.manifest), a.suffix, known)
    for n in new:
        print(f"{n.bench}\t{n.sha256[:8]}\t{n.size}\t{n.path}")
    print(f"{len(new)} new circuit files")
    return 0
