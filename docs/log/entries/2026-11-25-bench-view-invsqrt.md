---
id: 2026-11-25-bench-view-invsqrt
date: 2026-11-25
title: "bench view: a self-contained explorer page with a module strip, gate mix, wire filter and paged gate list, for invsqrt bb676b95"
type: run
benchmark: infra
methods: [circuit-viewer]
status: done
outcome: positive
commit: c7d15af
prs: []
experiments: []
rows: [bb676b95]
studies: []
backfilled: false
licence_touched: true
---

## Question

Phase 2 of the Circuit Explorer plan (QCC-71): can the index become one page that shows the modules as a strip, and lets you open a module to see its gate mix and its gates?

## Setup

`src/bench/circview.py` and `src/bench/templates/circuit_view.html`. `bench view` indexes the circuit if needed, then inlines the index (summary plus every instruction line) into the template as JSON, with `<` escaped so no line can close the data script. The page is plain HTML, CSS and JavaScript with no network use and theme tokens for light and dark. Tests are in `tests/unit/test_circview.py`: the inlined data, the script-injection escape, determinism, and `node --check` on the page script.

## Results

### Quantitative

The page for `bb676b95` is 868 KB and builds in under a second from the cached index [M]. Checked in headless Chromium: no console errors, selecting module M7 sets the hash `#M7`, the CCX-only filter lists 353 rows (matching the index), and there is no horizontal scroll at 400 px width.

### Qualitative

The page has an overview strip (live width as a line over inferred module bands, coloured by width or Toffoli density, clickable and arrow-key navigable), a module panel (instructions, CCX, share of all CCX, width range, gate mix bars, wires touched as filter chips) and a gate list (all, CCX only or conditioned only, paged by 50, with go to line). Conditioned rows are amber. For this circuit most bands sit at the peak width of 37, so the width colouring is nearly flat and the Toffoli-density colouring is the useful one. The strip's width axis starts at 0, which is honest but hides the 22 to 37 range; a tighter axis is a possible later change.

## Decision

Phase 2 is done for invsqrt. Next is phase 3: a Circuits tab in the dashboard that links to these pages, `make circuits` as a dependency of `make dashboard`, and an index step in `bench promote`.

## Reproduce

`uv run bench view` (default `best/invsqrt/*.kmb`) writes `out/circuit-view/<sha8>.html`; `uv run pytest tests/unit/test_circview.py`.

## Links

QCC-71, [bench index](2026-11-25-bench-index-invsqrt.md).
