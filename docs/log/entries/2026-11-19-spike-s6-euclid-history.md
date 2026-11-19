---
id: 2026-11-19-spike-s6-euclid-history
date: 2026-11-19
title: "S6: the in-place Euclid history is moot; the frontier already scans at 11 Toffolis per position, the reciprocal scan needs 23"
type: decision
benchmark: dqi
methods: [spike, kill]
status: done
outcome: negative
commit: 0477830
prs: []
experiments: []
rows: []
studies: [docs/experiments/spike-s6-euclid-history.md]
backfilled: false
licence_touched: false
---

## Question

Is an in-place Euclid history for the reciprocal scan worth pursuing now?

## Setup

Re-read `dqi-psi.md` (design, the 2026-11-13 dead end) and the stage ledger of `fixed4` (scan 4,095 x 11 = 45,045 T).

## Results

### Quantitative

Reciprocal scan 23 per position (about 94k) against the frontier's 11 (45k): twice as much [M, from the notes and the ledger].

### Qualitative

The idea was costed against the old BM design (ratio 7.76) that the frontier left behind. The history problem itself was already
a time-boxed dead end.

## Decision

Kill S6. Close QCC-64. DQI effort goes to the CSWAP question (S5, parked) and the adaptive gauge scan (759 T).

## Reproduce

`docs/experiments/spike-s6-euclid-history.md`.

## Links

QCC-64.
