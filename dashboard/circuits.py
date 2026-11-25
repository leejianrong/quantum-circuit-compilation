"""Pure view model for the Circuits tab: the explorer index on disk to table rows (QCC-71).

No indah import. ``bench index`` writes ``out/circuit-index/<sha8>/summary.json`` and ``bench view`` writes
``out/circuit-view/<sha8>.html``; this reads the summaries and says where each page is served. The dashboard
mounts the page directory at ``PAGES_URL``, because indah's render protocol cannot embed a page.
"""

import functools
import json
import pathlib
from typing import Any

INDEX = pathlib.Path("out/circuit-index")
VIEW = pathlib.Path("out/circuit-view")
BEST = pathlib.Path("best")
PAGES_URL = "/circuits"
BENCH_ORDER = ("invsqrt", "dqi", "dfthcsos")


@functools.cache
def _sha(path: str, size: int, mtime_ns: int) -> str:
    """sha256 of a file, remembered per (path, size, mtime) because DQI's circuit is 618 MB."""
    from bench import ledger

    return ledger.sha256_path(pathlib.Path(path))


def best_shas(best: pathlib.Path, benches: set[str]) -> set[str]:
    """sha256 of the single-file circuits in ``best/<bench>/`` for the benches we need to compare."""
    out: set[str] = set()
    for b in benches:
        for f in sorted((best / b).glob("*.kmb")) if (best / b).is_dir() else []:
            st = f.stat()
            out.add(_sha(str(f), st.st_size, st.st_mtime_ns))
    return out


def entries(
    index: pathlib.Path = INDEX, view: pathlib.Path = VIEW, best: pathlib.Path = BEST
) -> list[dict[str, Any]]:
    sums = []
    for f in sorted(index.glob("*/summary.json")) if index.is_dir() else []:
        try:
            sums.append(json.loads(f.read_text()))
        except (OSError, ValueError):
            continue
    current = best_shas(best, {s["bench"] for s in sums})
    rows = []
    for s in sums:
        sha8 = s["sha256"][:8]
        page = view / f"{sha8}.html"
        rows.append(
            {
                "bench": s["bench"],
                "circuit": sha8,
                "file": s["name"],
                "instructions": s["instructions"],
                "ccx": s["ccx"],
                "peak_width": s["peak_width"],
                "modules": len(s["modules"]),
                "cost_tier": s["cost_tier"],
                "in_best": "yes" if s["sha256"] in current else "",
                "url": f"{PAGES_URL}/{sha8}.html" if page.exists() else "",
            }
        )
    order = {b: i for i, b in enumerate(BENCH_ORDER)}
    rows.sort(key=lambda r: (order.get(r["bench"], 99), r["in_best"] != "yes", r["circuit"]))
    return rows


def links_markdown(rows: list[dict[str, Any]]) -> str:
    """One bullet per benchmark, with a markdown link to the explorer page of each circuit."""
    by_bench: dict[str, list[str]] = {}
    for r in rows:
        if r["url"]:
            label = r["file"].removesuffix(".kmb") + (" (best/)" if r["in_best"] else "")
            by_bench.setdefault(r["bench"], []).append(f"[{label}]({r['url']})")
    lines = [f"- **{b}**: " + " · ".join(links) for b, links in by_bench.items()]
    return "\n".join(lines) if lines else "No explorer pages yet. Run `make circuits`."
