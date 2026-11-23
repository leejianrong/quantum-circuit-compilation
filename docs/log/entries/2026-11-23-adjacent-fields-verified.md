---
id: 2026-11-23-adjacent-fields-verified
date: 2026-11-23
title: "Adjacent-fields note checked against the v17 sources and the literature: one claim corrected, search harness now ranked first"
type: reading
benchmark: docs
methods: [literature, source-reading]
status: done
outcome: positive
commit: bb5fed4
prs: []
experiments: []
rows: []
studies: [docs/experiments/ideas-adjacent-fields.md]
backfilled: false
licence_touched: true
---

## Question

Which of the ideas in [the adjacent-fields note](../../experiments/ideas-adjacent-fields.md) are real, and which are already inside the public v17 lineage?

## Setup

Greps over the vendored v17 invsqrt tree, our sandbox copy of the v17 DQI generator and the dfthcsos decode notes; web searches for the references (snippets only).

## Results

### Qualitative

The references exist. Exact AND-minimisation is already used in part by the invsqrt lineage (solver not shipped). No search harness exists in the invsqrt or DQI sources. GF(64)-Karatsuba and tower-field inversion are used in DQI. The "rank-23 tensor" claim I wrote from memory is not supported and is corrected in the note. Revised first-test costs are in the note.

## Decision

Rank the search harness first, exact synthesis of one loader second. Neither is started.

## Reproduce

`grep -rlE "pysat|z3|anneal|tempering" third_party/syed_invsqrt_v17/src` (no hits) and the same pattern over a `scripts/dqi_v17_build.sh` copy of the generator.

## Links

QCC-65, [adjacent fields note](2026-11-22-adjacent-fields-ideas.md).
