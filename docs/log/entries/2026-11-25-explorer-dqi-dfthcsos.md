---
id: 2026-11-25-explorer-dqi-dfthcsos
date: 2026-11-25
title: "Circuit Explorer covers DQI and dfthcsos: DQI's 70 million instructions index in 71 s, and modules now come from width plus Toffoli and classical density"
type: run
benchmark: infra
methods: [circuit-viewer, indexing, segmentation]
status: done
outcome: positive
commit: 9058aa6
prs: []
experiments: []
rows: [bb676b95, 141f02ac, 24516e97]
studies: []
backfilled: false
licence_touched: true
---

## Question

Phase 4 of the Circuit Explorer plan (QCC-71): can the same index and page serve DQI (70 million instructions) and the 15 dfthcsos circuits, and are the inferred modules useful there?

## Setup

`src/bench/circindex.py` was generalised. The text export is scanned in one streaming pass into compact arrays (opcode per instruction, three operand qubits, first and last use per qubit). Width is the sampled simulation for invsqrt and the touch interval (qubits between first and last use) for the others, since that needs no input semantics. Circuits above 200,000 instructions list only priced gates: Toffoli-like gates and non-Clifford `Z_POW` rotations. Modules come from greedy binary segmentation on three block-averaged features (width, Toffoli density, classical-only density), at most 20,000 blocks. Pages now hold rows `[line, text, conditioned]`, so a sparse listing keeps its real line numbers. The benchmark comes from the directory (`best/<bench>/`) or `--bench`. `make circuits` and `bench view` with no arguments cover every `.kmb` in `best/`. The `Circuits` tab hashes `best/` files once per file and mtime. Analyser version 3.

## Results

### Quantitative

- DQI `141f02ac`: 69,836,332 instructions (text lines, a few dozen more than kickmix counts), 312,254 CCX, peak width 900. Indexing took 71 s wall and 2.3 GB peak memory under a 24 GB address cap [M]. 318,971 rows are listed (160 pages), the page is 10.6 MB and opens in 0.3 s in headless Chromium with no errors. Module M1 is 20.0 million instructions with 3 CCX, the classical table setup; the other 23 modules hold the rest, between 0 and 47,347 CCX each (M15 holds 15.2%).
- dfthcsos: 15 `angle_k_*.kmb` files of 29 to 52 thousand instructions, peak width 128, each with 129 to 164 CCX concentrated in one long block (about 28,000 to 40,000 instructions at width 126 to 128), a ramp up before it and a ramp down after it.
- invsqrt `bb676b95` with the new features: 24 modules, with Toffolis spread over M4, M5, M8, M14 and M15 to M19 (M8 holds 365 of 1,470).
- The sampled-width cache key is the analyser version, so changing the segmentation needs a version bump; I had to bump it once during this work because the first re-run served stale entries.

### Qualitative

The touch-interval width is flat at 900 for most of DQI, because every qubit is touched early and never leaves the interval, so the width curve is uninformative there. The modules separate by gate density instead, which is why the density features were added. The dfthcsos modules show the shape of each circuit, a loader ramp, a long main block and an unloading ramp, but they are still inferred: the loaders' real structure is in `submission.npz`, which this index does not read. DQI cost is static counts only.

## Decision

The explorer now covers all three benchmarks in `best/`. Remaining: retire the one-off analysis scripts whose pictures the explorer replaces, add the Circuits tab to `make plots-readme`, and a firing-weighted cost tier for invsqrt.

## Reproduce

`uv run bench view` (all `best/`; DQI takes about a minute the first time), `make circuits && make dashboard`; `uv run pytest tests/unit/test_circindex.py tests/unit/test_circview.py tests/unit/test_dashboard_circuits.py`.

## Links

QCC-71, [Circuits tab](2026-11-25-circuits-tab.md).
