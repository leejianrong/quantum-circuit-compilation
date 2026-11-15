---
id: 2026-11-16-knowledge-benchmarks-and-glossary
date: 2026-11-16
title: "Knowledge section extended: a state-of-knowledge page per benchmark and a project glossary"
type: decision
benchmark: docs
methods: [docs-site, knowledge]
status: done
outcome: positive
prs: [199]
backfilled: false
licence_touched: false
---

## Question

The first knowledge pages (claims, assumptions, open questions, environment) answer "what do we believe", but a reader
who wants "where do we stand on dqi" has to assemble it from claims and entries. And the project's own vocabulary
(salt, ledger, promotion, screening) was only defined in AGENTS.md and the measurement page.

## Setup

Written from the merged log entries, the claims register, `docs/HANDOFF.md` and `AGENTS.md`; no new measurement. Numbers are
the ledger rows already cited by the entries. Commit: not recorded (branch `qcc-58-knowledge-benchmarks`).

## Results

### Quantitative

| Page | Content |
|---|---|
| `knowledge/benchmarks.md` | one section each for invsqrt, dqi and dfthcsos: score formula, our best against the best verified public circuit, what we know, what failed, what is open; every number links its entry |
| `knowledge/glossary.md` | 21 project terms, each defined from the docs or entries that use it |

### Qualitative

* Writing the per-benchmark pages showed which statements were looser than the evidence. Three were tightened before the
  merge: the GF(2^24) pivot (holds classically, not a statement about the published design), the QAT definition (the
  notes do not say the objective is refit), and what the official cost includes (T gates and rotations, per salt).
* The static Toffoli count is not the official cost; the glossary and the scoreboard both say so.

## Decision

Keep these pages hand-written and link-checked (`tests/unit/test_knowledge.py`). When a log entry corrects a claim,
update the claims register and the benchmark page in the same PR.

## Reproduce

```
make log
make docs
uv run pytest tests/unit/test_knowledge.py tests/unit/test_logbook.py
```

## Links

PR 199; `docs/knowledge/benchmarks.md`, `docs/knowledge/glossary.md`.
