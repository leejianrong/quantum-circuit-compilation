---
id: 2026-11-25-circuits-tab
date: 2026-11-25
title: "Circuits tab in the dashboard: make circuits runs before make dashboard, and bench promote builds the page for a promoted invsqrt circuit"
type: run
benchmark: infra
methods: [circuit-viewer, dashboard]
status: done
outcome: positive
commit: b44a219
prs: []
experiments: []
rows: [bb676b95]
studies: []
backfilled: false
licence_touched: true
---

## Question

Phase 3 of the Circuit Explorer plan (QCC-71): can the dashboard always show the latest explorer pages without a manual step, given that indah cannot embed a page?

## Setup

`dashboard/circuits.py` (pure view model) and `dashboard/circuits_view.py` (the tab): a table of every indexed circuit and a markdown link to its page. The dashboard app mounts `out/circuit-view/` at `/circuits` as static files, first in the route list. `make circuits` runs `bench view --if-present`, and `make dashboard` depends on it. `bench promote` (not a dry run) builds the page for a promoted invsqrt circuit, and a failure there only prints a note. Tests are in `tests/unit/test_dashboard_circuits.py`: the view model, a missing page, no index, `--if-present`, the promote hook, and a GET through the ASGI app (200 for a page, 404 for a missing one).

## Results

### Quantitative

`make circuits` on `best/invsqrt` takes under a second once the index exists [M]. Driven in headless Chromium against a running dashboard: the Circuits tab lists `bb676b95` (60,789 instructions, 1,470 CCX, peak width 37, 24 modules, in best/), its link goes to `/circuits/bb676b95.html`, the explorer script runs there and the page shows `invsqrt bb676b95`, with no page errors.

### Qualitative

The link opens the page in the same tab, so the browser's back button returns to the dashboard. Only invsqrt is indexed, so the tab has one row; DQI and dfthcsos need their adapters. The promote hook sits in the CLI dispatch, not in `promote.run`, so the promotion tests do not write into `out/`.

## Decision

Phase 3 is done. Phase 4 is the DQI and dfthcsos adapters, retiring the one-off analysis scripts whose pictures the explorer now covers, and adding the tab to `make plots-readme`.

## Reproduce

`make circuits && make dashboard`, then open the Circuits tab; `uv run pytest tests/unit/test_dashboard_circuits.py`.

## Links

QCC-71, [bench view](2026-11-25-bench-view-invsqrt.md).
