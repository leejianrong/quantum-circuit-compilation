"""Derive ledger/lineage.json (the Lineage tab's graph) from docs/PROVENANCE.md.

Run `uv run python -m bench.lineage` after editing PROVENANCE.md; a test fails if the checked-in JSON is
stale. What is read from the tables: the sources (S1..S13 with licence text), every candidate circuit
(prefix, sha256, where it was seen, reported cost, authors) and the "Ideas learned" rows (our
generators). What is hand-written below: who built on whom, which the prose only gives in sentences.

Edges have a kind. `derived` means the circuit file descends from the parent, so a missing licence
passes down. `idea` means we studied the parent and rewrote the technique ourselves (ADR-0009), so it
does not. A node is flagged `no_licence` when a `derived` ancestor states no licence.
"""

import json
import pathlib
import re
import sys
from typing import Any

PROVENANCE = pathlib.Path("docs/PROVENANCE.md")
OUT = pathlib.Path("ledger/lineage.json")
BENCHES = ("invsqrt", "dqi", "dfthcsos")
BASELINE_NAMES = {
    "invsqrt": "Newton-Raphson reference circuit",
    "dqi": "reference Reed-Solomon syndrome decoder",
    "dfthcsos": "reference QROM angle loaders and example submission",
}

# Ancestors that are not circuit files in the tables: id -> (bench, label, authors, licence, note).
# licence "none" means the source states no licence (docs/PROVENANCE.md, "DQI risk").
ANCESTORS: dict[str, tuple[str, str, str, str, str]] = {
    "anc:jday96314": (
        "dqi",
        "jday96314 repo",
        "jday96314",
        "none",
        "Root of every public DQI circuit. It states no licence: only the compiled circuit, as published "
        "in public Kaggle notebook outputs, is included by the later authors.",
    ),
    "anc:ozertuu-v70": (
        "dqi",
        "ozertuu V70 rewrite",
        "ozertuu",
        "unstated",
        "The decoder line that Atakan Aldemir's phase folds were applied to.",
    ),
    "anc:13b5bf7a": (
        "invsqrt",
        "13b5bf7a line",
        "ozertuu, kirilltym, Atakan Aldemir, Hosen42, syed3000, mrmeows, busyaprime, yoyobar",
        "unstated",
        "The community invsqrt circuit that all public variants descend from; credit chain in each "
        "source's CREDITS.md.",
    ),
    "anc:syed3000-loaders": (
        "dfthcsos",
        "syed3000 angle loaders",
        "syed3000",
        "unstated",
        "The angle-loader circuits that every public dfthcsos refit reuses.",
    ),
}

# (parent, child, kind, label). Prefixes are circuit nodes; "baseline:<bench>" and "anc:..." as above.
EDGES: list[tuple[str, str, str, str]] = [
    ("baseline:invsqrt", "anc:13b5bf7a", "derived", "community rewrites"),
    ("anc:13b5bf7a", "034c7c2a", "derived", "maoxin123"),
    ("034c7c2a", "c6519219", "derived", "CSWAP-reduced"),
    ("anc:13b5bf7a", "46743f7f", "derived", "yoyobar"),
    ("anc:13b5bf7a", "95621d7e", "derived", "Hosen42 rewrite"),
    ("anc:13b5bf7a", "1c5b1ee2", "derived", "Hosen42 q25 merge"),
    ("anc:13b5bf7a", "3132ecab", "derived", "alexchilton"),
    ("baseline:dqi", "anc:jday96314", "derived", "decoder design"),
    ("anc:jday96314", "anc:ozertuu-v70", "derived", "readout rewrite"),
    ("anc:ozertuu-v70", "e9f54be3", "derived", "phase folds (Aldemir)"),
    ("anc:jday96314", "4432ec5f", "derived", "Tymchishin and others"),
    ("anc:jday96314", "b71b21ca", "derived", "Isabe11aM00re"),
    ("baseline:dfthcsos", "anc:syed3000-loaders", "derived", "loaders"),
    ("anc:syed3000-loaders", "91d0ad25", "derived", "maoxin123 weight refit"),
    ("anc:syed3000-loaders", "ad1a4d28", "derived", "heliosli refit"),
    ("anc:syed3000-loaders", "8faa7e0b", "derived", "Aldemir"),
    ("anc:syed3000-loaders", "3f72cbe5", "derived", "yoyobar polish"),
    ("anc:syed3000-loaders", "5bd35757", "derived", "Isabe11aM00re"),
    ("anc:syed3000-loaders", "9cd87121", "derived", "Isabe11aM00re"),
    # what we learned from public work, rewritten from scratch (the "Ideas learned" table)
    ("e9f54be3", "dqi_gen", "idea", "reported qubit total only"),
    ("baseline:dqi", "dqi_gen", "idea", "Khattar et al. 2025 (paper)"),
    ("baseline:invsqrt", "invsqrt_gen", "derived", "starts from the reference"),
    ("baseline:dfthcsos", "dfthcsos_gen", "derived", "starts from the reference"),
]

SOURCE_LICENCE = re.compile(r"metadata (apache-2\.0|\"other\")", re.I)


def tables(text: str) -> dict[str, list[list[str]]]:
    """Markdown tables keyed by the nearest heading above them; rows are lists of cell strings."""
    out: dict[str, list[list[str]]] = {}
    head = ""
    for line in text.splitlines():
        if line.startswith("#"):
            head = line.lstrip("# ").strip()
        elif line.startswith("|") and not re.match(r"^\|[-| ]+\|$", line):
            out.setdefault(head, []).append([c.strip() for c in line.strip().strip("|").split("|")])
    return out


def number(cell: str) -> float | None:
    m = re.match(r"(?:about )?\d[\d,]*(?:\.\d+)?", cell)
    return float(m.group().removeprefix("about ").replace(",", "")) if m else None


def licence_of(cell: str) -> str:
    """Short status of a source's licence text."""
    if cell.lower().startswith("unstated"):
        return "unstated"
    m = SOURCE_LICENCE.search(cell)
    return (
        {"apache-2.0": "apache-2.0 (dataset metadata)", '"other"': "other (see its LICENSE)"}[
            m.group(1).lower()
        ]
        if m
        else "see source"
    )


def build(text: str) -> dict[str, Any]:
    tabs = tables(text)
    sources: dict[str, dict[str, str]] = {}
    for r in tabs.get("Sources", [])[1:]:
        author = r[1].split(",")[0].strip()
        sources[r[0]] = {"id": r[0], "author": author, "url": r[2], "licence": licence_of(r[3]), "text": r[3]}

    nodes: dict[str, dict[str, Any]] = {}
    for b in BENCHES:
        nodes[f"baseline:{b}"] = {
            "id": f"baseline:{b}", "kind": "baseline", "bench": b, "label": f"{b} baseline",
            "authors": "host (Google Quantum AI)", "licence": "apache-2.0 (host data)", "sources": [],
            "note": BASELINE_NAMES[b],
        }  # fmt: skip
    for id_, (bench, label, authors, licence, note) in ANCESTORS.items():
        nodes[id_] = {
            "id": id_, "kind": "ancestor", "bench": bench, "label": label, "authors": authors,
            "licence": licence, "sources": [], "note": note,
        }  # fmt: skip
    for head, rows in tabs.items():
        found = next((b for b in BENCHES if head.startswith(b)), None)
        if found is None or "Candidates" in head or head.startswith("Best"):
            continue
        pub_bench = found
        for r in rows:
            if not re.fullmatch(r"[0-9a-f]{8}", r[0]):
                continue
            seen = sorted(set(re.findall(r"S\d+", r[2])), key=lambda s: int(s[1:]))
            lic = sorted({sources[s]["licence"] for s in seen if s in sources})
            nodes[r[0]] = {
                "id": r[0], "kind": "public", "bench": pub_bench, "label": f"{pub_bench} {r[0]}",
                "sha256": re.sub(r"[^0-9a-f]", "", r[1]), "cost": number(r[3]),
                "authors": r[4], "sources": seen, "licence": "; ".join(lic) or "unknown",
                "note": r[3],
            }  # fmt: skip

    for r in tabs.get("Ideas learned (ADR-0009 stage 2)", [])[1:]:
        m = re.search(r"src/(\w+_gen)", r[2])
        if m and m.group(1) not in nodes:
            bench = m.group(1).split("_")[0]
            nodes[m.group(1)] = {
                "id": m.group(1), "kind": "ours", "bench": bench, "label": f"our {bench} generator",
                "authors": "us", "licence": "ours (Apache-2.0)", "sources": [],
                "note": "", "ideas": [],
            }  # fmt: skip
        if m:
            nodes[m.group(1)]["ideas"].append(
                {"technique": r[0], "from": r[1], "generator": r[2], "date": r[3]}
            )
    for n in nodes.values():
        if n["kind"] == "ours":
            n["note"] = f"{len(n['ideas'])} technique(s) learned and rewritten; see docs/PROVENANCE.md"

    edges = [{"source": s, "target": t, "kind": k, "label": lab} for s, t, k, lab in EDGES]
    for e in edges:
        for end in (e["source"], e["target"]):
            if end not in nodes:
                raise KeyError(f"lineage edge names {end}, which is not in PROVENANCE.md or ANCESTORS")
    flag(nodes, edges)
    used = {k for e in edges for k in (e["source"], e["target"])}
    return {
        "generated_from": str(PROVENANCE),
        "sources": list(sources.values()),
        "nodes": [n for n in nodes.values() if n["id"] in used],
        "edges": edges,
    }


def flag(nodes: dict[str, dict[str, Any]], edges: list[dict[str, str]]) -> None:
    """Set `no_licence` on every node with a `derived` ancestor that states none (or is none itself)."""
    for n in nodes.values():
        n["no_licence"] = n["licence"] == "none"
    changed = True
    while changed:
        changed = False
        for e in edges:
            if (
                e["kind"] == "derived"
                and nodes[e["source"]]["no_licence"]
                and not nodes[e["target"]]["no_licence"]
            ):
                nodes[e["target"]]["no_licence"] = True
                changed = True


def main() -> int:
    OUT.write_text(json.dumps(build(PROVENANCE.read_text()), indent=1, sort_keys=True) + "\n")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
