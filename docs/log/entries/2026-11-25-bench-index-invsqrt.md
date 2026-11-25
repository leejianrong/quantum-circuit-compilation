---
id: 2026-11-25-bench-index-invsqrt
date: 2026-11-25
title: "bench index: a sha-keyed per-circuit index with inferred modules, built for invsqrt bb676b95 in 0.8 s"
type: run
benchmark: infra
methods: [circuit-viewer, indexing, segmentation]
status: done
outcome: positive
commit: b8ef9c5
prs: []
experiments: []
rows: [bb676b95]
studies: []
backfilled: false
licence_touched: true
---

## Question

Phase 1 of the Circuit Explorer plan (QCC-71): can one command turn a circuit file into a small, cached index that a page can read, with modules we can defend?

## Setup

`src/bench/circindex.py` and `bench index`. Per file it writes `out/circuit-index/<sha8>/summary.json` and `pages/NNN.json` (2,000 instruction lines each). Modules come from greedy binary segmentation of the sampled live-width series (256 inputs, seed 0, 24 modules, minimum length 50): the split that cuts the squared error most is taken first. Only invsqrt is supported, because the width simulation is specific to its 22-bit input. Tests are in `tests/unit/test_circindex.py` (6 tests: segmentation, coverage without gaps, counts, determinism, cache).

## Results

### Quantitative

For `bb676b95`: 60,789 instructions, 1,470 CCX, peak width 37, 31 pages. The first run builds in 0.8 s and a second run is a cache hit in 0.2 s [M]. The 24 modules cover the circuit without gaps and their CCX counts sum to 1,470. The width rises from 22 to 29 in M1, holds between 34 and 37 through M3 to M15, and falls back to 22 in M24. Five modules (M7, M9, M13, M6, M12) hold 1,154 of the 1,470 CCX.

### Qualitative

The modules follow the width profile, so they match its load, compute and uncompute phases. They are not the builder's own stages, and the summary says so (`module_source`). Cost is static for now (`cost_tier: static`): firing-weighted figures need the sampled or exact tier, which comes later.

## Decision

Phase 1 is done for invsqrt. Next is phase 2, `bench view`: the standalone HTML page from this index.

## Reproduce

`uv run bench index` (default `best/invsqrt/*.kmb`); `--force` rebuilds; `uv run pytest tests/unit/test_circindex.py`.

## Links

QCC-71, [spike](2026-11-25-circuit-explorer-spike.md).
