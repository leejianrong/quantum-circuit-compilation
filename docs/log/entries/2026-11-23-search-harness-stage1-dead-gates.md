---
id: 2026-11-23-search-harness-stage1-dead-gates
date: 2026-11-23
title: "Harness stage 1 on the 43-qubit line: no redundant Toffoli, and 10 never-firing gates cost nothing to keep"
type: experiment
benchmark: invsqrt
methods: [search-harness, dead-gate, reachability]
status: done
outcome: negative
commit: 3e5eb9d
prs: []
experiments: []
rows: [4091b3af]
studies: [docs/experiments/ideas-adjacent-fields.md]
backfilled: false
licence_touched: true
---

## Question

First stage of the search harness (QCC-61): on the final 43-qubit circuit `70fe5f79`, does any Toffoli-class gate disappear if we ask about reachable states instead of the whole state space?

## Setup

Two new tools, both ours and tested (`src/invsqrt_gen/port/ccx_rank.py`, `activity.py`, `tests/unit/test_invsqrt_activity.py`), classical simulation of the kmx text with random HMR outcomes, as in the width profile.
(a) For each CCX, is the AND of its controls in the GF(2) span of the other live wires and the constant 1 on N sampled inputs (restricted to the samples where the gate fires)?
(b) For each CCX, CCZ and CSWAP, on how many of all 3,133,452 inputs does the gate fire?
Candidate for (b): delete the gates with count zero, convert with `kickmix` (converting the unmodified text reproduces `70fe5f79` byte for byte), official verifier locally at 2 salts.

## Results

### Quantitative

(a) 0 of 1,456 CCX are affine-redundant at 1,024 and 8,192 samples (two seeds): the lineage's own audit passes have already taken everything of this kind [M].
(b) 10 of 1,622 gates never fire on the whole domain: 4 CCX and 6 CCZ, in one branch under `b365 & ~b363 & ~b364` and in two small `b15009`/`b15012` conditioned gates plus a lone CCZ [M]. Deleting them gives a circuit (`4091b3af`) that PASSES the official verifier at 2 salts with cost 72,440.355, **identical** to `70fe5f79` (72,440.355) [M].

### Qualitative

Cost is charged by how often a gate runs, so a gate that never runs is free to keep, and removing it gains nothing. The real lever on conditioned gates is lowering how often they fire, not deleting them. The per-gate firing counts from (b) would show where the expected Toffoli mass sits; that table is not yet made.

## Decision

Stage 1 is a negative result: no static redundancy and no dead-weight gain. Not promoted, nothing submitted. Next: weight the CCX list by firing fraction, and see whether any frequently firing conditioned gate can be re-ordered or merged under a cheaper condition.

## Reproduce

`uv run python src/invsqrt_gen/port/ccx_rank.py ~/qcc-builds/out7/invsqrt.kmx --samples 8192`; `uv run python src/invsqrt_gen/port/activity.py ~/qcc-builds/out7/invsqrt.kmx` (about 40 minutes, one heavy job).

## Links

QCC-61, [adjacent fields, verified](2026-11-23-adjacent-fields-verified.md), [width profile](2026-11-22-invsqrt-v17-width-profile.md).
