---
id: 2026-11-22-adjacent-fields-ideas
date: 2026-11-22
title: "Broad pass over adjacent fields: our scores are AND-count and width minimisation, a problem cryptography and logic synthesis already know"
type: reading
benchmark: infra
methods: [literature, brainstorm]
status: done
outcome: n/a
commit: 94db67e
prs: []
experiments: []
rows: []
studies: [docs/experiments/ideas-adjacent-fields.md]
backfilled: false
licence_touched: false
---

## Question

Which methods from other fields (cryptography, logic synthesis, computer arithmetic, coding theory, machine learning, chemistry, compilers, biology and physics) could transfer to our three scores?

## Setup

Written from memory, no web search, no code; references are pointers to be verified. Output: `docs/experiments/ideas-adjacent-fields.md`.

## Results

### Qualitative

Clifford gates are free and only Toffoli/AND count, rotations and peak width are priced, so each task is multiplicative-complexity minimisation under a width cap with an exact, cheap check. Cryptography (AND-minimal circuits, bilinear complexity), logic synthesis (XAG rewriting, don't-cares), reversible pebbling and register allocation (the width problem), and LLM-guided evolutionary search (our generators are programs with an exact automatic score) are the closest fits. Six candidates are ranked; several are already inside the public lineage (tensor ranks in the DQI field chart, hold passes, coded batches, window searches).

## Decision

Verification pass next (confirm references, check the v17 sources for what is already used, size each first test), then choose one or two of: AND-minimisation of recurring blocks, a pebbling/rematerialisation optimiser over the width profile, an evolutionary harness over the owned generators.

## Reproduce

Not applicable.

## Links

[S2 v17 width profile](2026-11-22-invsqrt-v17-width-profile.md), [dfthcsos reading](2026-11-22-dfthcsos-v17-generator-reading.md).
