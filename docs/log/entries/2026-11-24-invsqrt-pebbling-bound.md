---
id: 2026-11-24-invsqrt-pebbling-bound
date: 2026-11-24
title: "Pebbling bound on the 43-qubit line: all 473 repeated Toffoli products span the peak width, so holding saves nothing"
type: experiment
benchmark: invsqrt
methods: [pebbling, rematerialisation, width-profile]
status: done
outcome: negative
commit: 8f7e04b
prs: []
experiments: []
rows: [70fe5f79]
studies: [docs/experiments/ideas-adjacent-fields.md]
backfilled: false
licence_touched: true
---

## Question

Before building a pebbling or rematerialisation optimiser for `70fe5f79` (QCC-61): what is the most such an optimiser could save from products the circuit computes more than once, if holding the first result in a spare wire is allowed wherever the width has room?

## Setup

`src/invsqrt_gen/port/repeats.py` (ours, tested): one classical simulation of the kmx text on 2,048 sampled inputs with random HMR outcomes (two seeds), recording each CCX's product vector, its firing condition, and the live-wire count after every step. Two CCX with the same product vector and condition are a repeat. A hold is possible only if the live width in the whole gap between the two is below the circuit's peak of 43.

## Results

### Quantitative

1,452 CCX had a non-zero product; 473 consecutive repeated pairs; **0 holdable**: the peak live width in every gap is 43 (both seeds, a histogram with a single bin) [M]. Only 1 pair has fewer than 40 steps between its two gates. The expected Toffolis a hold could save is 0.0 of 473.

### Qualitative

The repeats are almost all the compute and uncompute copies of the same product, far apart, and every pair is separated by a stretch at the 43-qubit peak (27% of the steps, in 287 segments). A spare wire exists only in the four slack regions, and no repeated pair has its gap inside one. So rematerialisation by holding has no room on this circuit, and a pebbling optimiser over repeats has a ceiling of zero. What remains is a scheduler that changes which products exist, which is a redesign of the stages.

## Decision

The pebbling candidate is closed for invsqrt (outcome negative). The invsqrt harness work stays parked; the only remaining lever is what the public team ships next.

## Reproduce

`uv run python src/invsqrt_gen/port/repeats.py ~/qcc-builds/out7/invsqrt.kmx --samples 2048 --seed 1`; `tests/unit/test_invsqrt_repeats.py`.

## Links

QCC-61, [firing fractions](2026-11-24-invsqrt-firing-fractions.md), [width profile](2026-11-22-invsqrt-v17-width-profile.md).
