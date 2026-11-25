"""`bench view`: one self-contained HTML page per indexed circuit (QCC-71, phase 2).

The page is ``templates/circuit_view.html`` with the index entry (``bench index``) inlined as JSON: the
summary and every instruction line. It parses nothing and needs no network, so it opens from disk, serves
from the dashboard's server and publishes as an artifact. A design change is an edit to the template and a
re-run of this command; the index is not rebuilt.
"""

from __future__ import annotations

import argparse
import json
import pathlib

from bench import circindex

TEMPLATE = pathlib.Path(__file__).parent / "templates" / "circuit_view.html"
MARKER = "/*__DATA__*/null"
DEFAULT_OUT = pathlib.Path("out/circuit-view")


def load_entry(entry: pathlib.Path) -> dict[str, object]:
    summary = json.loads((entry / "summary.json").read_text())
    lines: list[str] = []
    for p in range(summary["pages"]):
        lines.extend(json.loads((entry / "pages" / f"{p:03d}.json").read_text())["lines"])
    return {"summary": summary, "lines": lines}


def render(entry: pathlib.Path) -> str:
    """The page for one index entry directory. ``<`` is escaped so no line can close the data script."""
    data = json.dumps(load_entry(entry), separators=(",", ":")).replace("<", "\\u003c")
    html = TEMPLATE.read_text()
    assert html.count(MARKER) == 1, "template data marker missing or repeated"
    return html.replace(MARKER, data)


def view_file(
    path: pathlib.Path,
    index_root: pathlib.Path = circindex.DEFAULT_OUT,
    out_dir: pathlib.Path = DEFAULT_OUT,
    *,
    force_index: bool = False,
) -> pathlib.Path:
    _, entry = circindex.index_file(path, index_root, force=force_index)
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{entry.name}.html"
    dst.write_text(render(entry))
    return dst


def add_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser("view", help="write the Circuit Explorer page for circuit files (indexes them first)")
    p.add_argument("paths", nargs="*", type=pathlib.Path, help="default: best/invsqrt/*.kmb")
    p.add_argument("--index", type=pathlib.Path, default=circindex.DEFAULT_OUT)
    p.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    p.add_argument("--force-index", action="store_true", help="rebuild the index entry first")


def run(a: argparse.Namespace) -> int:
    paths = a.paths or sorted(pathlib.Path("best/invsqrt").glob("*.kmb"))
    if not paths:
        print("error: no circuit files (best/invsqrt is empty)")
        return 2
    for p in paths:
        print(view_file(p, a.index, a.out, force_index=a.force_index))
    return 0
