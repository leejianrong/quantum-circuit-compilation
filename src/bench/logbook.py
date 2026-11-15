"""The log book (docs/log/): front-matter parser, linter and generated index pages.

    uv run python -m bench.logbook            # rewrite the generated pages
    uv run python -m bench.logbook --check    # lint entries, fail if a generated page is stale

Entries are hand-written markdown in docs/log/entries/<id>.md with a small front-matter block (see
docs/log/template.md). The indexes (docs/log/*.md except the template) and docs/results/*.md are generated
from the entries and from ledger/*.jsonl, committed, and checked for drift by tests/unit/test_logbook.py.

The front matter is a restricted YAML subset so that no dependency is needed: `key: value` lines, where a
value is a bare or quoted string, an integer, true/false, or a flat list `[a, b, 3]`.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from bench import experiments, ledger
from bench.plots import BASELINES

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
ENTRIES = DOCS / "log" / "entries"
PR_SNAPSHOT = ROOT / "analysis" / "numbers" / "prs.json"

TYPES = ("experiment", "run", "decision", "reading", "correction", "incident")
BENCHMARKS = ("invsqrt", "dqi", "dfthcsos", "infra", "docs")
STATUSES = ("open", "done", "superseded")
OUTCOMES = ("positive", "negative", "inconclusive", "correction", "n/a")
REQUIRED = ("id", "date", "title", "type", "benchmark", "status", "outcome")
LISTS = ("methods", "prs", "experiments", "rows", "studies", "corrects")
OPTIONAL = (*LISTS, "commit", "superseded_by", "backfilled", "licence_touched")
FRONT = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)


@dataclass
class Entry:
    path: Path
    meta: dict[str, Any]
    body: str
    errors: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return str(self.meta.get("id", self.path.stem))


def _scalar(text: str) -> Any:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    if text in ("true", "false"):
        return text == "true"
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


def parse_front_matter(text: str) -> tuple[dict[str, Any], str, list[str]]:
    """Return (meta, body, problems). Lines that do not fit the restricted grammar are reported."""
    m = FRONT.match(text)
    if not m:
        return {}, text, ["no front matter (file must start with a --- block)"]
    meta: dict[str, Any] = {}
    problems: list[str] = []
    for n, line in enumerate(m.group(1).splitlines(), start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        key = key.strip()
        if not sep or not re.fullmatch(r"[a-z_]+", key):
            problems.append(f"line {n}: expected `key: value`, got {line!r}")
            continue
        if key in meta:
            problems.append(f"line {n}: duplicate key {key!r}")
        value = value.strip()
        if value[:1] not in ("'", '"'):
            value = value.split(" #", 1)[0].strip()  # trailing comment
        if value.startswith("["):
            if not value.endswith("]"):
                problems.append(f"line {n}: list must close on the same line")
                continue
            inner = value[1:-1].strip()
            meta[key] = [_scalar(x) for x in inner.split(",")] if inner else []
        else:
            meta[key] = _scalar(value)
    return meta, m.group(2), problems


def load_entries(directory: Path = ENTRIES) -> list[Entry]:
    out = []
    for path in sorted(directory.glob("*.md")):
        meta, body, problems = parse_front_matter(path.read_text(encoding="utf-8"))
        out.append(Entry(path, meta, body, problems))
    return out


def lint(
    entries: list[Entry],
    exp_ids: set[str],
    sha_prefixes: set[str],
    pr_exists: set[int] | None = None,
    pr_max: int = 0,
) -> list[str]:
    """Problems as `file: message` strings; empty means clean."""
    errs: list[str] = []
    ids = {e.id for e in entries}
    seen: dict[str, Path] = {}
    for e in entries:
        name = e.path.name

        def err(msg: str, name: str = name) -> None:
            errs.append(f"{name}: {msg}")

        for p in e.errors:
            err(p)
        for k in REQUIRED:
            if k not in e.meta:
                err(f"missing required field {k!r}")
        for k in e.meta:
            if k not in REQUIRED and k not in OPTIONAL:
                err(f"unknown field {k!r}")
        if e.errors or any(k not in e.meta for k in REQUIRED):
            continue
        m = e.meta
        if m["id"] != e.path.stem:
            err(f"id {m['id']!r} must equal the file name {e.path.stem!r}")
        if m["id"] in seen:
            err(f"duplicate id {m['id']!r}")
        seen[m["id"]] = e.path
        try:
            d = date.fromisoformat(str(m["date"]))
            if not e.path.stem.startswith(d.isoformat()):
                err(f"file name must start with the date {d.isoformat()}")
        except ValueError:
            err(f"date {m['date']!r} is not YYYY-MM-DD")
        for key, allowed in (
            ("type", TYPES),
            ("benchmark", BENCHMARKS),
            ("status", STATUSES),
            ("outcome", OUTCOMES),
        ):
            if m[key] not in allowed:
                err(f"{key} {m[key]!r} not in {allowed}")
        for k in LISTS:
            if k in m and not isinstance(m[k], list):
                err(f"{k} must be a list like [a, b]")
        for pr in m.get("prs", []):
            if not isinstance(pr, int):
                err(f"prs must be integers, got {pr!r}")
            elif pr_exists is not None and pr <= pr_max and pr not in pr_exists:
                err(f"PR {pr} is not in the PR snapshot (analysis/numbers/prs.json)")
        for x in m.get("experiments", []):
            if x not in exp_ids:
                err(f"experiment {x!r} is not in ledger/experiments.jsonl")
        for s in m.get("rows", []):
            if not any(p.startswith(str(s)) for p in sha_prefixes) or len(str(s)) < 8:
                err(f"ledger row {s!r}: need at least 8 hex characters of a sha in ledger/results.jsonl")
        for s in m.get("studies", []):
            if not (ROOT / str(s)).is_file():
                err(f"study {s!r} does not exist")
        for k in ("corrects", "superseded_by"):
            for t in m[k] if isinstance(m.get(k), list) else ([m[k]] if k in m else []):
                if t not in ids:
                    err(f"{k} {t!r} is not an entry id")
        if m["type"] == "correction" and not m.get("corrects"):
            err("a correction entry must list the entries it corrects in `corrects`")
        if m["status"] == "superseded" and not m.get("superseded_by"):
            err("status superseded needs superseded_by")
        for heading in ("## Question", "## Setup", "## Results", "## Decision", "## Reproduce", "## Links"):
            if not re.search(rf"^{re.escape(heading)}\b", e.body, re.MULTILINE):
                err(f"missing section {heading!r}")
    return errs


# --- generated pages -----------------------------------------------------------------------------

HEADER = (
    "<!-- Generated by `python -m bench.logbook`; edit the entries or the ledgers, not this file. -->\n\n"
)


def _link(e: Entry, prefix: str = "entries/") -> str:
    return f"[{e.meta['title']}]({prefix}{e.path.name})"


def _prs(e: Entry) -> str:
    return ", ".join(f"#{p}" for p in e.meta.get("prs", [])) or ""


def _sorted(entries: list[Entry]) -> list[Entry]:
    ok = [e for e in entries if not e.errors and all(k in e.meta for k in REQUIRED)]
    return sorted(ok, key=lambda e: (str(e.meta["date"]), e.id), reverse=True)


def render_log(entries: list[Entry]) -> dict[Path, str]:
    es = _sorted(entries)
    pages: dict[Path, str] = {}
    rows = ["| Date | Type | Benchmark | Outcome | Entry | PRs |", "|---|---|---|---|---|---|"]
    for e in es:
        m = e.meta
        mark = " (backfilled)" if m.get("backfilled") else ""
        rows.append(
            f"| {m['date']} | {m['type']} | {m['benchmark']} | {m['outcome']} "
            f"| {_link(e)}{mark} | {_prs(e)} |"
        )
    pages[Path("log/index.md")] = (
        HEADER + "# Log book\n\nOne dated entry per piece of work: what we tried, the setup, the numbers, "
        "what we learned, what we decided. Newest first. How to write one: [entry template](template.md). "
        "Also by [benchmark](by-benchmark.md), by [method](by-method.md), the "
        "[negative results](negative-results.md) and the [corrections](corrections.md); numbers live under "
        "[results](../results/scoreboard.md).\n\n"
        "Project and infrastructure work (the harness, the dashboard, the Kaggle runners, the ADRs) sits "
        "beside the studies and has no entries here; see "
        "[ADR-0008](../adr/0008-measurement-ledger-v2-and-dashboard.md), "
        "[measurement](../MEASUREMENT.md) and the git history.\n\n"
        + (("\n".join(rows) + "\n") if es else "No entries yet.\n")
    )

    def grouped(title: str, intro: str, keyf: Any, order: list[str] | None = None) -> str:
        groups: dict[str, list[Entry]] = {}
        for e in es:
            for k in keyf(e):
                groups.setdefault(str(k), []).append(e)
        keys = order if order else sorted(groups)
        out = [HEADER, f"# {title}\n\n{intro}\n"]
        for k in keys:
            if k in groups:
                out.append(f"\n## {k}\n")
                out += [f"- {e.meta['date']}: {_link(e)} ({e.meta['outcome']})" for e in groups[k]]
        return "\n".join(out) + "\n"

    pages[Path("log/by-benchmark.md")] = grouped(
        "Log by benchmark",
        "Entries grouped by the benchmark they concern.",
        lambda e: [e.meta["benchmark"]],
        list(BENCHMARKS),
    )
    pages[Path("log/by-method.md")] = grouped(
        "Log by method",
        "Entries grouped by the `methods` tags in their front matter.",
        lambda e: e.meta.get("methods", []),
    )
    neg = [e for e in es if e.meta["outcome"] == "negative"]
    body = [
        HEADER,
        "# Negative results\n\nIdeas that were tried and did not work, with the reason. "
        "They are as useful as the wins: they tell the next person where not to dig.\n",
    ]
    body += [f"- {e.meta['date']}, {e.meta['benchmark']}: {_link(e)}" for e in neg] or ["No entries yet."]
    pages[Path("log/negative-results.md")] = "\n".join(body) + "\n"
    cor = [e for e in es if e.meta["type"] == "correction" or e.meta["outcome"] == "correction"]
    body = [
        HEADER,
        "# Corrections\n\nEarlier claims that turned out to be wrong. The original entry is never "
        "rewritten; it gets a pointer to the entry that corrects it.\n",
    ]
    for e in cor:
        tgt = ", ".join(f"[{t}](entries/{t}.md)" for t in e.meta.get("corrects", []))
        body.append(f"- {e.meta['date']}: {_link(e)}" + (f" corrects {tgt}" if tgt else ""))
    if not cor:
        body.append("No entries yet.")
    pages[Path("log/corrections.md")] = "\n".join(body) + "\n"
    return pages


def _cell(text: str, limit: int) -> str:
    text = " ".join(str(text).split()).replace("|", "\\|")
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def render_results(rows: list[ledger.Row], exps: dict[str, experiments.Experiment]) -> dict[Path, str]:
    out = [
        HEADER,
        "# Scoreboard\n\nBest verified runs per benchmark: official verifier, full shots, status PASS, "
        "one line per circuit (the run with the most salts). **Includes public circuits we verified "
        "ourselves**, so a row here is not necessarily ours; the provenance of each is in "
        "[PROVENANCE](../PROVENANCE.md). Ratio is `baseline_cost / worst-salt cost`. Cost is the "
        "official cost; `toffolis` is a static count and not the cost.\n",
    ]
    for bench, base in BASELINES.items():
        best: dict[str, ledger.Row] = {}
        for r in rows:
            if (
                r.bench != bench
                or r.status != "PASS"
                or r.reduced_shots
                or not r.cost
                or getattr(r, "engine", None)
                or r.kind in ("screen", "leaderboard")
            ):
                continue
            cur = best.get(r.circuit_sha256)
            if cur is None or (r.salts, r.ts or "") > (cur.salts, cur.ts or ""):
                best[r.circuit_sha256] = r
        top = sorted(best.values(), key=lambda r: r.cost or float("inf"))[:8]
        out.append(f"\n## {bench}\n")
        out.append("| Ratio | Cost | Qubits | Toffolis (static) | Salts | Circuit | Date |")
        out.append("|---:|---:|---:|---:|---:|---|---|")
        for r in top:
            assert r.cost
            out.append(
                f"| {base / r.cost:.2f} | {r.cost:,.0f} | {r.qubits or ''} | "
                f"{f'{r.toffolis:,.0f}' if r.toffolis else ''} | {r.salts} | `{r.circuit_sha256[:8]}` | "
                f"{(r.ts or '')[:10]} |"
            )
    pages = {Path("results/scoreboard.md"): "\n".join(out) + "\n"}
    out = [
        HEADER,
        "# Experiments\n\nOne row per experiment in `ledger/experiments.jsonl` (the latest snapshot of "
        "each id). Hypotheses and notes are shortened; the full text is in the ledger and in the study "
        "linked from the [log](../log/index.md).\n",
        "| Id | Benchmark | Opened | Status | Hypothesis | Outcome notes |",
        "|---|---|---|---|---|---|",
    ]
    for e in exps.values():
        out.append(
            f"| {e.id} | {e.benchmark} | {e.opened[:10]} | {e.outcome or e.status} | "
            f"{_cell(e.hypothesis, 150)} | {_cell(e.notes or '', 220)} |"
        )
    pages[Path("results/experiments.md")] = "\n".join(out) + "\n"
    return pages


def load_prs(root: Path = ROOT) -> list[dict[str, Any]]:
    path = root / "analysis" / "numbers" / "prs.json"
    return json.loads(path.read_text()) if path.exists() else []


def render_prs(prs: list[dict[str, Any]], entries: list[Entry]) -> dict[Path, str]:
    by_pr: dict[int, list[Entry]] = {}
    for e in _sorted(entries):
        for n in e.meta.get("prs", []):
            by_pr.setdefault(n, []).append(e)
    out = [
        HEADER,
        "# Pull requests\n\nEvery pull request of the repository, from a snapshot taken with "
        "`python -m bench.logbook --refresh-prs` (needs the `gh` CLI). The last column lists the log "
        "entries that cite the PR.\n",
        "| PR | Merged | State | Title | Log entries |",
        "|---:|---|---|---|---|",
    ]
    for pr in sorted(prs, key=lambda x: -x["number"]):
        links = ", ".join(f"[{e.id}](../log/entries/{e.path.name})" for e in by_pr.get(pr["number"], []))
        out.append(
            f"| #{pr['number']} | {(pr.get('mergedAt') or '')[:10]} | {pr['state'].lower()} | "
            f"{_cell(pr['title'], 140)} | {links} |"
        )
    return {Path("results/prs.md"): "\n".join(out) + "\n"}


def refresh_prs(root: Path = ROOT) -> int:
    res = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "all",
            "--limit",
            "1000",
            "--json",
            "number,title,state,mergedAt,headRefName",
        ],
        capture_output=True,
        text=True,
        cwd=root,
    )
    if res.returncode != 0:
        print("error: gh pr list failed:", res.stderr.strip())
        return 1
    prs = sorted(json.loads(res.stdout), key=lambda x: x["number"])
    (root / "analysis" / "numbers" / "prs.json").write_text(json.dumps(prs, indent=1, sort_keys=True) + "\n")
    print(f"wrote analysis/numbers/prs.json ({len(prs)} pull requests)")
    return 0


def generate(root: Path = ROOT) -> dict[Path, str]:
    """All generated pages, keyed by path relative to docs/."""
    entries = load_entries(root / "docs" / "log" / "entries")
    rows = ledger.read(root / "ledger" / "results.jsonl")
    exps = experiments.read(root / "ledger" / "experiments.jsonl")
    pages = {**render_log(entries), **render_results(rows, exps), **render_prs(load_prs(root), entries)}
    return {k: re.sub(r"\n{3,}", "\n\n", v) for k, v in pages.items()}


def lint_repo(root: Path = ROOT) -> list[str]:
    entries = load_entries(root / "docs" / "log" / "entries")
    exp_ids = set(experiments.read(root / "ledger" / "experiments.jsonl"))
    shas = {r.circuit_sha256 for r in ledger.read(root / "ledger" / "results.jsonl")}
    shas |= {
        str(json.loads(line)["sha256"])
        for line in (root / "ledger" / "promotions.jsonl").read_text().splitlines()
        if line
    }
    return lint(entries, exp_ids, shas)


def stale(root: Path = ROOT) -> list[str]:
    bad = []
    for rel, text in generate(root).items():
        path = root / "docs" / rel
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            bad.append(str(rel))
    return bad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--check", action="store_true", help="lint and fail on stale generated pages; write nothing"
    )
    ap.add_argument("--refresh-prs", action="store_true", help="re-snapshot the pull requests with gh first")
    a = ap.parse_args(argv)
    if a.refresh_prs and refresh_prs():
        return 1
    errs = lint_repo()
    for e in errs:
        print("lint:", e)
    if a.check:
        old = stale()
        for name in old:
            print("stale:", name, "(run `make log`)")
        return 1 if errs or old else 0
    if errs:
        return 1
    for rel, text in generate().items():
        path = DOCS / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print("wrote", path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
