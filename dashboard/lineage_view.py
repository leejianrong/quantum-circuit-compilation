"""Pure view model for the Lineage tab: ledger/lineage.json to Graph nodes and edges, and the detail text.

No indah import. The layout is left to right (baseline, ancestors, public circuits, ours), one lane per
benchmark, because indah's Graph draws no arrowheads: position carries the direction. When Graph gets
arrows and a dashed node style, `node_spec` is the one place to change.
"""

import json
import pathlib
from typing import Any

LINEAGE = pathlib.Path("ledger/lineage.json")
BENCHES = ("invsqrt", "dqi", "dfthcsos")
GROUPS = {
    "baseline": "baseline (host)",
    "public": "public circuit (unverified)",
    "ancestor": "ancestor (not a circuit file)",
    "ours": "ours (generator)",
    "no_licence": "NO LICENCE in ancestry",
}
COLORS = {
    "baseline": "#7A7A7A",
    "public": "#0072B2",
    "ancestor": "#9B7FC4",
    "ours": "#009E73",
    "no_licence": "#CC3311",
}
LANE = 420.0
COL = 330.0
ROW = 64.0


def load(path: pathlib.Path = LINEAGE) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {"nodes": [], "edges": [], "sources": []}


def depths(lin: dict[str, Any]) -> dict[str, int]:
    """Longest path from a root, so every edge points rightwards."""
    parents: dict[str, list[str]] = {n["id"]: [] for n in lin["nodes"]}
    for e in lin["edges"]:
        parents[e["target"]].append(e["source"])
    memo: dict[str, int] = {}

    def depth(i: str) -> int:
        if i not in memo:
            memo[i] = 1 + max((depth(p) for p in parents[i]), default=-1)
        return memo[i]

    return {i: depth(i) for i in parents}


def group_of(n: dict[str, Any]) -> str:
    return "no_licence" if n["no_licence"] and n["kind"] != "ours" else n["kind"]


def node_spec(n: dict[str, Any], x: float, y: float) -> dict[str, Any]:
    """The Graph node dict. A no-licence node has its own colour and group AND a label suffix, because
    colour alone is not enough (Graph has no dashed outline yet)."""
    g = group_of(n)
    label = n["label"]
    if g == "no_licence":
        label += " [NO LICENCE]"
    elif n["kind"] == "ours":
        label = "OURS: " + label
    return {
        "id": n["id"],
        "label": label,
        "group": GROUPS[g],
        "color": COLORS[g],
        "size": 16 if n["kind"] == "ours" else 8,
        "x": x,
        "y": y,
    }


def graph(lin: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    d = depths(lin)
    top = max(d.values(), default=0)
    slot: dict[tuple[str, int], int] = {}
    nodes: list[dict[str, Any]] = []
    for n in lin["nodes"]:
        lane = BENCHES.index(n["bench"])
        if n["kind"] == "ours":  # our generators sit in a column of their own, below the public chain
            nodes.append(node_spec(n, (top + 1) * COL, lane * LANE + 2.5 * ROW))
            continue
        col = d[n["id"]]
        k = slot.get((n["bench"], col), 0)
        slot[(n["bench"], col)] = k + 1
        nodes.append(node_spec(n, col * COL, lane * LANE + k * ROW + (col % 2) * ROW * 0.75))
    edges = [
        {
            "source": e["source"],
            "target": e["target"],
            "label": e["label"] if e["kind"] == "derived" else "idea: " + e["label"],
            "color": "#009E73" if e["kind"] == "idea" else "#9a9a9a",
        }
        for e in lin["edges"]
    ]
    return nodes, edges


def ours_ids(lin: dict[str, Any]) -> list[str]:
    return [n["id"] for n in lin["nodes"] if n["kind"] == "ours"]


def detail(lin: dict[str, Any], node_id: str | None) -> str:
    """Markdown for the clicked node: what it is, who made it, licence, provenance rows, neighbours."""
    nodes = {n["id"]: n for n in lin["nodes"]}
    n = nodes.get(node_id or "")
    if n is None:
        return "Click a node to see its authors, licence, cost and where it came from."
    sources = {s["id"]: s for s in lin.get("sources", [])}
    lines = [f"**{n['label']}** ({n['kind']}, {n['bench']})", ""]
    if n["no_licence"]:
        lines += ["**No licence in the ancestry.** A circuit file is a derivative chain: do not submit it "
                  "until it is replaced or cleared (ADR-0007 rule 2).", ""]  # fmt: skip
    lines.append(f"- Authors: {n['authors']}")
    lines.append(f"- Licence: {n['licence']}")
    if n.get("sha256"):
        lines.append(f"- sha256: `{n['sha256']}`")
    if n.get("cost"):
        lines.append(f"- Reported cost: {n['cost']:,.2f} (not verified by us)")
    if n.get("note"):
        lines.append(f"- Note: {n['note']}")
    for s in n.get("sources", []):
        src = sources.get(s)
        if src:
            lines.append(f"- Provenance {s}: {src['author']}, {src['url']}, licence {src['licence']}")
    for idea in n.get("ideas", []):
        lines.append(f"- Learned: {idea['technique']} ({idea['from']}, {idea['date']})")
    parents = [f"{nodes[e['source']]['label']} ({e['kind']})" for e in lin["edges"] if e["target"] == n["id"]]
    children = [nodes[e["target"]]["label"] for e in lin["edges"] if e["source"] == n["id"]]
    if parents:
        lines.append(f"- Built on: {'; '.join(parents)}")
    if children:
        lines.append(f"- Led to: {'; '.join(children)}")
    return "\n".join(lines)


def legend_svg() -> str:
    """A data: URI SVG legend in our own colours: Graph's built-in legend uses its own palette, not ours."""
    items = "".join(
        f'<circle cx="{12 + i * 215}" cy="12" r="6" fill="{COLORS[k]}"/>'
        f'<text x="{24 + i * 215}" y="16" font-size="12" fill="#777" '
        f'font-family="sans-serif">{GROUPS[k]}</text>'
        for i, k in enumerate(GROUPS)
    )
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="24">{items}</svg>'
    return "data:image/svg+xml;utf8," + svg.replace("#", "%23").replace("<", "%3C").replace(">", "%3E")
