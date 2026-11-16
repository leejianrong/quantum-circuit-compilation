---
id: 2026-11-16-docs-sweep
date: 2026-11-16
title: "Docs sweep after the DQI promotions: README, HANDOFF, QUESTIONS and AGENTS brought in line; six dependency PRs merged"
type: decision
benchmark: docs
methods: [housekeeping]
status: done
outcome: n/a
commit: 0daada0
prs: [208, 209, 210, 211, 212, 213]
rows: []
studies: []
corrects: []
backfilled: false
licence_touched: false
---

## Question

After three DQI promotions in one day, which docs still describe the old state, and what is waiting in the PR queue?

## Setup

Read README, AGENTS.md, HANDOFF and QUESTIONS against `ledger/promotions.jsonl` and `best/`; listed open PRs; used the
agent-brief and readme-playbook checklists.

## Results

### Qualitative

README still showed our DQI at 65.77 with public circuits in `best/` and "within 3%"; HANDOFF named the old hash in
two places; QUESTIONS asked whether `fixed.kmb` would be promoted; AGENTS.md did not mention `notebooks/dqi_gen`.
All fixed. The six open PRs were Dependabot bumps with green CI (three workflow actions, zensical, ruff,
playwright); merged one by one, no conflicts.

## Decision

Dependabot PRs with green CI are merged on sight. README states the DQI figure from `best/`, not from the older public set.

## Reproduce

```
gh pr list --state open
git grep -n "65.77" -- README.md docs/HANDOFF.md docs/QUESTIONS.md
```

## Links

PRs 208 to 213.
