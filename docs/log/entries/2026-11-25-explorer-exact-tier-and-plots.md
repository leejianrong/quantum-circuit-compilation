---
id: 2026-11-25-explorer-exact-tier-and-plots
date: 2026-11-25
title: "Circuit Explorer: invsqrt firing counts take 38 s, so the exact tier is cheap; the Circuits tab joins make plots-readme; no old analysis script is retired"
type: run
benchmark: infra
methods: [circuit-viewer, indexing]
status: done
outcome: positive
commit: 870411b
prs: []
experiments: []
rows: [bb676b95]
studies: []
backfilled: false
licence_touched: true
---

## Question

The last items of the Circuit Explorer plan (QCC-71): a firing-weighted cost tier for invsqrt, the Circuits tab in `make plots-readme`, and retiring the one-off analysis scripts the explorer replaces.

## Setup

`bench index --exact` and `bench view --exact` run `invsqrt_gen.port.activity` over the whole domain (3,133,452 inputs, one random HMR outcome each, in chunks of 262,144) and store, per Toffoli-like gate, the fraction of inputs on which it fires. Pages gain a `fires` column and modules gain `toffoli_expected` and `toffoli_never`. `bench promote` (not a dry run) builds the page with this tier. `make circuits` stays static, and an exact entry is not downgraded by it. `make plots-readme` now depends on `make circuits` and takes a `dashboard-circuits.png`. Analyser version 5. The tab's links are grouped per benchmark.

## Results

### Quantitative

The firing pass for `bb676b95` takes 38 s in the index (the standalone script took about the same) and gives 1,406.3 expected Toffoli-like gates firing against 1,470 CCX in the text, from 1,553 Toffoli-like gates (CCX, CCZ, CSWAP) of which 1,289 always fire, 204 fire about half the time and 2 never fire [M]. Module M8 holds 308.8 of them (22.0%), M4 227.0 (16.1%) and M5 221.0 (15.7%). This is not the official cost: 60,927.6 / 37 qubits is 1,646.7, which is 240 above 1,406.3, and I have not explained the difference (rotations and the CCZ and CSWAP weights are the candidates). The page therefore says "expected Toffolis firing", not cost.

### Qualitative

Two labelling mistakes in the previous change were fixed here. The page tag read "inferred from sampled live width" although modules have come from width plus Toffoli and classical density since the last change, and the first cache served stale entries after a segmentation change (the version bump is the guard). Chromium for `make plots-readme` needed `playwright install chromium` with the same extras the target uses (`--extra plots --extra dashboard --extra shots`); the plots-only extra installed a different revision.

The analysis scripts were not retired. `analysis/dqi_figures.py` draws eight figures from `analysis/numbers/dqi.json`, and they compare our generator's stages and versions (stage ledger, patch waterfall, profile diff, j-min sweep, extractor nodes). The explorer shows one circuit file at a time and does not have those numbers, so only the qubit timeline and instruction mix overlap, and the report and tests use the whole set.

## Decision

The explorer plan is complete apart from retirement, which stays open until the stage-level comparisons exist as an index of generator stages, a different piece of work. The unexplained 240 between expected firing and cost/Q is worth a short look before anyone treats the firing column as a cost.

## Reproduce

`uv run bench view --exact best/invsqrt/invsqrt.kmb`; `make circuits`; `make plots-readme`; `uv run pytest tests/unit/test_circindex.py tests/unit/test_circview.py tests/unit/test_dashboard_circuits.py`.

## Links

QCC-71, [explorer for DQI and dfthcsos](2026-11-25-explorer-dqi-dfthcsos.md), [firing fractions on the old circuit](2026-11-24-invsqrt-firing-fractions.md).
