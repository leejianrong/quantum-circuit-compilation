---
id: 2026-11-17-dqi-70x-correction
date: 2026-11-17
title: "Correction: routing under a measured flag is not a valid way to remove the DQI CSWAPs"
type: correction
benchmark: dqi
methods: [study, correction]
status: done
outcome: correction
commit: b41f7fa
prs: []
experiments: []
rows: []
studies: [docs/experiments/dqi-70x-study.md]
corrects: [2026-11-17-dqi-70x-study]
backfilled: false
licence_touched: false
---

## Question

The 70x study proposed that the public circuit removes our 12,384 CSWAPs by routing under a measured flag. Is that valid?

## Setup

Read the vendored window code (`transpose_handoff_window.py`): `query` builds the flag by `toggle_zero(B[-1], flag)`,
`route` swaps under it, `release` measures it with `hmr` and keeps a phase debt.

## Results

### Quantitative

None new. The gap decomposition (CSWAP 12,384 of 15,771 T, 92% of the CSWAPs in the outer window transposes) stands [M].

### Qualitative

The flag is a function of quantum data, so the branch it controls cannot be taken classically: `hmr` measures in the X basis
for uncomputation only. A computational-basis measurement would pass basis-state checks and break superposition. The earlier
"Hypothesis" and the prediction of about 69.5x from it are withdrawn. The mechanism by which the public circuit avoids the
CSWAPs is unknown.

## Decision

Replace the S5 plan: look at the gate context of the public circuit's swaps (study extension, Kaggle), then try to absorb the
routing swap into a tracked relabelling in our own wiring. Keep the adaptive gauge scan as the small sure item.

## Reproduce

`docs/experiments/dqi-70x-study.md`.

## Links

QCC-63, corrects `2026-11-17-dqi-70x-study`.
