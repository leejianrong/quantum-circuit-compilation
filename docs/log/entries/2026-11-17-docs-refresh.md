---
id: 2026-11-17-docs-refresh
date: 2026-11-17
title: "Docs refresh after the promotion and S2/S4: README status, AGENTS resources and worktree gotcha, HANDOFF backlog"
type: decision
benchmark: docs
methods: [docs]
status: done
outcome: n/a
commit: db79df4
prs: []
experiments: []
rows: []
studies: []
backfilled: false
licence_touched: false
---

## Question

Do the README, AGENTS.md and HANDOFF describe the state after the 2026-11-17 promotion and the first two spikes?

## Setup

README audited against the readme-playbook (status paragraph shortened, table matches `best/`); AGENTS.md audited
against the agent-brief filter (stale resource line fixed, worktree gotcha and spike pointer added, 41 lines).

## Results

### Quantitative

README 93 lines, AGENTS.md 41 lines. Plots under `docs/img/` redrawn from the ledger; the dashboard screenshots were not
redrawn (Playwright's Chromium is not installed on this machine).

### Qualitative

The worktree `uv run` trap cost about an hour, so it earned a line. Quick start steps were not re-run in a clean checkout.

## Decision

Re-run `make plots-readme` with Chromium installed when the next result lands.

## Reproduce

`make log`, `make plots-readme`.

## Links

QCC-67.
