---
id: 2026-11-19-dqi-condition-statistics
date: 2026-11-19
title: "DQI: the public 70x circuit conditions its gates the same way we do; the gap is unconditioned Toffolis (our 12,384 CSWAPs)"
type: experiment
benchmark: dqi
methods: [study, conditions]
status: done
outcome: negative
commit: 19101a0
prs: [227]
experiments: []
rows: [599cb515, 00ac37d4]
studies: [docs/experiments/dqi-70x-study.md]
backfilled: false
licence_touched: true
---

## Question

Is the public circuit's advantage in how it uses classical conditions (it runs 5x the `PUSH_CONDITION` and `BIT_INVERT` instructions)?

## Setup

`dqi_gen.study` extended (PR 227) to count, per op, conditioned versus plain, the condition bit's origin (HMR or derived) and the
condition nesting depth of Toffolis; Kaggle kernel `qcc-dqi-study-public` on `00ac37d4` and our `fixed4`.

## Results

### Quantitative

Conditioned and plain counts and origins agree to within a few percent for `SWAP`, `CX`, `CCX`, `CCZ`, `Z`, `X`, `R`. Toffolis by
depth 0/1/2: ours 332,006 / 48,171 / 4,585; public 317,446 / 46,498 / 5,047 [M]. The depth-0 difference of 14,560 contains our 12,384
unconditioned `CSWAP`s (85%).

### Qualitative

No. The extra classical instructions are bookkeeping. Hypothesis "conditions" is closed negative (the earlier "measured flag"
hypothesis was withdrawn as invalid). What remains is an algorithm that needs no data-dependent swap, a design question.

## Decision

Park S5 at low confidence; keep the adaptive gauge scan as the small sure item; start S6.

## Reproduce

`uv run bench kaggle run notebooks/dqi_study_public`; numbers in `docs/experiments/dqi-70x-study.md`.

## Links

QCC-63, PR 227.
