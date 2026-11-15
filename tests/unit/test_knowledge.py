"""The knowledge pages must point at log entries that exist, and claim statuses must be valid."""

import re
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "docs"
KNOW = DOCS / "knowledge"
ENTRY_LINK = re.compile(r"\]\(\.\./log/entries/([a-z0-9-]+)\.md\)")
STATUSES = ("holds", "model only", "unverified", "refuted")


def test_every_evidence_link_names_an_entry() -> None:
    for page in KNOW.glob("*.md"):
        for entry in ENTRY_LINK.findall(page.read_text()):
            assert (DOCS / "log" / "entries" / f"{entry}.md").is_file(), f"{page.name}: no entry {entry}"


def test_claims_have_valid_status_and_evidence() -> None:
    rows = [ln for ln in (KNOW / "claims.md").read_text().splitlines() if ln.startswith("| ")]
    claims = [r for r in rows if not r.startswith("| Claim") and not r.startswith("|---")]
    assert len(claims) > 30
    for r in claims:
        cells = [c.strip() for c in r.strip("|").split("|")]
        assert len(cells) == 3, r
        assert cells[1].split(":")[0].split(" (")[0].split(" for ")[0].split(";")[0] in STATUSES or any(
            cells[1].startswith(s) for s in STATUSES
        ), r
        assert ENTRY_LINK.search(cells[2]), r


def test_every_referenced_study_and_page_exists() -> None:
    for page in KNOW.glob("*.md"):
        for target in re.findall(r"\]\((?!http)([^)#]+\.md)", page.read_text()):
            assert (page.parent / target).resolve().is_file(), f"{page.name}: broken link {target}"
