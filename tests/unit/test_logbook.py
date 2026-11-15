"""The log book: front-matter grammar, lint rules, generated pages, and the checked-in entries."""

from pathlib import Path

import pytest

from bench import logbook
from bench.logbook import Entry, lint, parse_front_matter

GOOD = """---
id: 2026-11-15-x
date: 2026-11-15
title: "A title: with a colon"
type: experiment
benchmark: dqi
methods: [a, b]
status: done
outcome: negative
prs: [1, 2]
rows: [37d8047d]
backfilled: false
---

## Question
## Setup
## Results
## Decision
## Reproduce
## Links
"""


def entry(text: str, name: str = "2026-11-15-x.md") -> Entry:
    meta, body, problems = parse_front_matter(text)
    return Entry(Path(name), meta, body, problems)


def run_lint(*entries: Entry, shas: set[str] | None = None) -> list[str]:
    return lint(list(entries), {"E001"}, shas or {"37d8047d" + "0" * 56})


def test_parser_reads_scalars_lists_and_quotes() -> None:
    meta, body, problems = parse_front_matter(GOOD)
    assert not problems
    assert meta["title"] == "A title: with a colon"
    assert meta["methods"] == ["a", "b"] and meta["prs"] == [1, 2]
    assert meta["backfilled"] is False and meta["date"] == "2026-11-15"
    assert body.lstrip().startswith("## Question")


def test_parser_reports_bad_lines() -> None:
    _, _, problems = parse_front_matter("---\nid 2026\nlist: [a, b\n---\nbody\n")
    assert len(problems) == 2
    assert parse_front_matter("no front matter")[2]


def test_good_entry_is_clean() -> None:
    assert run_lint(entry(GOOD)) == []


@pytest.mark.parametrize(
    ("old", "new", "fragment"),
    [
        ("type: experiment", "type: idea", "type 'idea'"),
        ("outcome: negative", "outcome: great", "outcome 'great'"),
        ("date: 2026-11-15", "date: 2026-13-45", "not YYYY-MM-DD"),
        ("id: 2026-11-15-x", "id: other", "must equal the file name"),
        ("prs: [1, 2]", "prs: [one]", "integers"),
        ("rows: [37d8047d]", "rows: [deadbeef]", "ledger row"),
        ("rows: [37d8047d]", "rows: [37d8]", "8 hex"),
        ("backfilled: false", "bogus: 1", "unknown field"),
        ("## Decision", "## Next", "missing section '## Decision'"),
    ],
)
def test_lint_rejects(old: str, new: str, fragment: str) -> None:
    errs = run_lint(entry(GOOD.replace(old, new)))
    assert any(fragment in e for e in errs), errs


def test_lint_experiment_and_correction_rules() -> None:
    assert any("E999" in e for e in run_lint(entry(GOOD.replace("prs: [1, 2]", "experiments: [E999]"))))
    corr = GOOD.replace("type: experiment", "type: correction").replace(
        "id: 2026-11-15-x", "id: 2026-11-16-c"
    )
    corr = corr.replace("date: 2026-11-15", "date: 2026-11-16")
    assert any("must list" in e for e in run_lint(entry(corr, "2026-11-16-c.md")))
    ok = corr.replace("backfilled: false", "corrects: [2026-11-15-x]")
    assert run_lint(entry(GOOD), entry(ok, "2026-11-16-c.md")) == []
    sup = GOOD.replace("status: done", "status: superseded")
    assert any("superseded_by" in e for e in run_lint(entry(sup)))


def test_generated_pages_group_and_sort(tmp_path: Path) -> None:
    a = entry(GOOD)
    b = entry(
        GOOD.replace("2026-11-15-x", "2026-11-16-y")
        .replace("date: 2026-11-15", "date: 2026-11-16")
        .replace("outcome: negative", "outcome: positive"),
        "2026-11-16-y.md",
    )
    pages = logbook.render_log([a, b])
    idx = pages[Path("log/index.md")]
    assert idx.index("2026-11-16-y") < idx.index("2026-11-15-x")  # newest first
    assert "2026-11-15-x" in pages[Path("log/negative-results.md")]
    assert "2026-11-16-y" not in pages[Path("log/negative-results.md")]
    assert "## a" in pages[Path("log/by-method.md")]


def test_checked_in_entries_lint_clean() -> None:
    assert logbook.lint_repo() == []


def test_checked_in_generated_pages_are_current() -> None:
    assert logbook.stale() == [], "run `make log` and commit the generated pages"


def test_every_entry_is_linked_from_the_timeline() -> None:
    idx = (logbook.DOCS / "log" / "index.md").read_text()
    for e in logbook.load_entries():
        assert f"entries/{e.path.name}" in idx, e.path.name


def test_template_example_passes_the_lint() -> None:
    text = (logbook.DOCS / "log" / "template.md").read_text()
    block = text.split("````markdown\n", 1)[1].split("\n````", 1)[0]
    meta, _, problems = parse_front_matter(block)
    assert not problems
    for k in logbook.REQUIRED:
        assert k in meta


def test_relative_links_in_log_and_results_pages_resolve() -> None:
    import re

    pages = [
        *logbook.DOCS.glob("log/*.md"),
        *logbook.DOCS.glob("log/entries/*.md"),
        *logbook.DOCS.glob("results/*.md"),
    ]
    for page in pages:
        for target in re.findall(r"\]\((?!https?:|#)([^)#\s]+)", page.read_text()):
            assert (page.parent / target).resolve().exists(), (
                f"{page.relative_to(logbook.DOCS)}: broken link {target}"
            )


def test_pr_numbers_are_checked_against_the_snapshot_only_up_to_its_newest() -> None:
    shas = {"37d8047d" + "0" * 56}
    unknown = entry(GOOD.replace("prs: [1, 2]", "prs: [2]"))
    assert any("PR 2" in e for e in lint([unknown], {"E001"}, shas, {1, 3}, 3))
    newer = entry(GOOD.replace("prs: [1, 2]", "prs: [4]"))  # snapshot not refreshed yet: allowed
    assert lint([newer], {"E001"}, shas, {1, 3}, 3) == []
