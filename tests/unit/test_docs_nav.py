"""The site nav must list real pages, and every page must be reachable from it.

Zensical tolerates a missing nav target (warning, exit 0) and builds unlisted pages without a link, so
both mistakes would otherwise pass CI unnoticed.
"""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"


def nav_paths(items: object) -> list[str]:
    out: list[str] = []
    if isinstance(items, str):
        out.append(items)
    elif isinstance(items, list):
        for it in items:
            out += nav_paths(it)
    elif isinstance(items, dict):
        for v in items.values():
            out += nav_paths(v)
    return out


def listed() -> set[str]:
    cfg = tomllib.loads((ROOT / "zensical.toml").read_text())
    return set(nav_paths(cfg["project"]["nav"]))


def test_every_nav_target_exists() -> None:
    missing = sorted(p for p in listed() if not (DOCS / p).is_file())
    assert not missing, f"nav lists pages that do not exist: {missing}"


def test_every_page_is_in_the_nav() -> None:
    # Log entries are reached through the generated log indexes (test_logbook checks every entry is linked).
    pages = {str(p.relative_to(DOCS)) for p in DOCS.rglob("*.md") if "log/entries/" not in str(p)}
    orphans = sorted(pages - listed())
    assert not orphans, f"pages missing from zensical.toml nav: {orphans}"


def test_mathjax_assets_are_vendored() -> None:
    cfg = tomllib.loads((ROOT / "zensical.toml").read_text())
    for js in cfg["project"]["extra_javascript"]:
        assert (DOCS / js).is_file(), js
