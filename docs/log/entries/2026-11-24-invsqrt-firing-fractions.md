---
id: 2026-11-24-invsqrt-firing-fractions
date: 2026-11-24
title: "Where the invsqrt Toffoli mass sits: 91% unconditioned, and the conditioned gates are all measurement corrections firing half the time"
type: experiment
benchmark: invsqrt
methods: [search-harness, firing-fraction, expected-cost]
status: done
outcome: negative
commit: 0bac7e2
prs: []
experiments: []
rows: [70fe5f79]
studies: [docs/experiments/ideas-adjacent-fields.md]
backfilled: false
licence_touched: true
---

## Question

The cost model charges a conditioned gate by how often it fires. On the final 43-qubit circuit, where does the expected Toffoli mass sit, and is there a conditioned group whose firing rate could be lowered by reordering or merging conditions? (Last probe of the harness before parking invsqrt.)

## Setup

`activity.py --out` over all 3,133,452 inputs with random HMR outcomes gives a firing count per CCX, CCZ and CSWAP gate; fractions are count / inputs. Groups are by the innermost enclosing condition bit, read from the kmx text.

## Results

### Quantitative

Expected Toffoli-class cost 1,436.09 over 1,622 gates [M]; the model check is that 1,684.66 total less rotations (about 248) is about 1,437. 1,313 gates are unconditioned and carry 1,313 (91%); 309 are conditioned and carry 123.09 (8.6%). Of those 309: 10 never fire, 17 fire 1% to 10% (1.16 expected), 181 fire 10% to 50% (70.91) and 101 fire at least 50% (51.03). The largest groups are `b359` (22 gates, 11.0), `b361` (21, 10.5), `b192` (25, 5.56), `b13109` (11, 5.5) and `b360` (11, 5.5); `b359` and `b361` are exactly half-probability groups (0.5 per gate) [M].

### Qualitative

By the literal kill rule (a group above 5 expected Toffolis) five groups pass. I read the rule by its purpose, which is that the firing rate can be lowered, and by that reading it fails: the big groups fire at exactly 1/2 because they are the corrections that follow a measure-and-reset outcome bit, so reordering conditions does not change their rate. Cutting 5% of the whole conditioned mass would save about 6 Toffolis, 0.35% of the cost, and would need fewer measurement corrections, which is a redesign of the uncompute steps rather than a patch.

## Decision

Invsqrt harness work is parked here (outcome negative). The tools stay (`ccx_rank.py`, `activity.py`); the remaining invsqrt levers are the pebbling optimiser on the four slack regions (ceiling about 0.65%) and anything the public team ships next, found by `bench public-diff`.

## Reproduce

`uv run python src/invsqrt_gen/port/activity.py ~/qcc-builds/out7/invsqrt.kmx --out ~/qcc-builds/activity_counts.json` (about 40 minutes under `flock /tmp/qcc-heavy.lock`), then group the counts by enclosing `PUSH_CONDITION` bit.

## Links

QCC-61, [harness stage 1](2026-11-23-search-harness-stage1-dead-gates.md), [width profile](2026-11-22-invsqrt-v17-width-profile.md).
