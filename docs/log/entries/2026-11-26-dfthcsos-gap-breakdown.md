---
id: 2026-11-26-dfthcsos-gap-breakdown
date: 2026-11-26
title: "dfthcsos: the 4.07x gap to the public package is T x Q, and nearly all of it is brot 7 against 11"
type: experiment
benchmark: dfthcsos
methods: [verifier-breakdown, cost-model]
status: done
outcome: positive
commit: d5e67db
prs: []
experiments: []
rows: [24516e97, 09324acd]
studies: [docs/experiments/dfthcsos-gap-2026-11-26.md]
corrects: []
backfilled: false
licence_touched: true
---

## Question

Which verifier terms separate our `09324acd` (3.28x) from the public package `24516e97` (13.36x in `best/`), so that the next work goes to the largest one?

## Setup

Official `verify.py` with one salt on each directory (CPU, `CUDA_VISIBLE_DEVICES=` empty, under `flock /tmp/qcc-heavy.lock`), reading the `resources` and `metrics` blocks of its JSON output. The public package is only measured (output files, no source read).

## Results

### Quantitative

`lambda_eff` 46.92 against 48.09 (1.025x); `T_total` 13,214 against 29,293 (2.22x); `Q_total` 405 against 726 (1.79x). The public words are 7-bit (0 to 127, 1,219 rows, shape (9, 127, 46)); ours are 11-bit (2,047, 1,484 rows, shape (8, 176, 56)). Loaders 15 against 25; Toffolis per loader 224 against 435. Full table in the study note.

### Qualitative

The `Lambda` work of S4 is finished as a lever. `brot` scales the loader count, the Givens cost and the inner-prep workspace together, which the old low-brot note priced as a 3% effect on a different shape.

## What we learned

1. The next gain is a passing 7-bit table (QCC-55, QCC-62), then the loader (about 1.9x per circuit), then the shape.
2. The old claim that 7 bits is not worth optimiser effort is superseded by this measurement.

## Next

Read syed3000's word-move polish scripts and the 7-bit reasoning once more against this table; build the 7-bit pipeline on our penalised fit.

## Decision

dfthcsos is the first target (largest gap, exact cost model, verify in minutes). DQI is second, invsqrt stays parked.

## Reproduce

`uv run python data/verifiers/dfthcsos/verify.py best/dfthcsos --salt x` and the same on `~/qcc-circuits/own_dfthcsos_11bit_pen` (`CUDA_VISIBLE_DEVICES=` empty, under `flock /tmp/qcc-heavy.lock`).

## Links

[Study note](../../experiments/dfthcsos-gap-2026-11-26.md), [S4 lambda](../../experiments/spike-s4-lambda.md), [low-brot note (superseded on 7 bits)](../../experiments/dfthcsos-low-brot.md).
