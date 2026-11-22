---
id: 2026-11-22-invsqrt-v17-width-profile
date: 2026-11-22
title: "S2 on the v17 line: one qubit is 39 Toffolis, but the 43-qubit peak spans 27% of the steps in 287 segments"
type: experiment
benchmark: invsqrt
methods: [exchange-rates, width-profile]
status: done
outcome: negative
commit: 77b70fa
prs: []
experiments: []
rows: [70fe5f79]
studies: [docs/experiments/spike-s2-exchange-rates.md]
backfilled: false
licence_touched: true
---

## Question

Where on the 43-qubit invsqrt circuit is a qubit cheapest to remove, and where is spare width that could buy Toffolis? (Option 1 of the v17 driver entry.)

## Setup

`src/invsqrt_gen/port/width.py` (ours, tested): classical simulation of the final kmx text (`~/qcc-builds/out7/invsqrt.kmx`, the text of `70fe5f79`) on 256 log-uniform inputs in [1, 3,133,452] with random `HMR` outcomes; a qubit is live at a step if nonzero for any sample. Two seeds. This is a lower bound on the width: it can miss states.

## Results

### Quantitative

Rates [M]: one qubit 2.33%, one Toffoli 0.059%, one qubit = 39.2 Toffolis at 43 qubits and 72,440.35. Profile [M]: 32,911 steps, peak 43 (equal to the qubit count, so the bound is tight at the top); width 43 for 8,893 steps (27.0%) in 287 segments, at least 42 for 47.4% (134 segments), at least 41 for 58.4%; the longest peak runs are 2,357, 717, 510 and 495 steps; 694 of the 1,456 CCX gates execute at width 43. Both seeds agree exactly. Of 20 equal slices of the circuit, slices 0, 15, 18 and 19 never exceed 37, 38, 40 and 38 and hold about 225 CCX gates (98, 0, 60, 67).

### Qualitative

A one-qubit cut cannot be a local patch: it needs a live wire removed in every one of 287 segments, a 39-Toffoli budget gives 0.14 Toffoli per segment, and the decode study already found that every stage binds at once on the 46-qubit line. The tradable resource is the opposite one: in four regions there are 3 to 6 spare wires. Whether they can save Toffolis there is not shown; the passes that already use spare wires (audit and hold) ran in the generator.

## Decision

Qubit removal on this line is dropped as a local lever (outcome negative); it stays a redesign question. Next experiment, if wanted: list the Toffolis inside the four slack regions by function (which stage emits them) and try holds or recomputation caches there with the exact proof as the gate; the ceiling is the 225 CCX gates, so a 5% saving there is 11 Toffolis, 0.65%.

## Reproduce

`uv run python src/invsqrt_gen/port/width.py ~/qcc-builds/out7/invsqrt.kmx`; unit test `tests/unit/test_invsqrt_width.py`.

## Links

QCC-68, QCC-60, [v17 driver](2026-11-22-invsqrt-v17-driver.md), [S2](../../experiments/spike-s2-exchange-rates.md).
