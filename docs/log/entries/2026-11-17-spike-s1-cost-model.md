---
id: 2026-11-17-spike-s1-cost-model
date: 2026-11-17
title: "S1: a static-count cost model is off by 4%; reduced-shot screening is exact to 1e-5 on invsqrt"
type: experiment
benchmark: infra
methods: [cost-model, screening]
status: done
outcome: negative
commit: b41f7fa
prs: []
experiments: []
rows: [fc834b80, cc5472d2]
studies: [docs/experiments/spike-s1-cost-model.md]
backfilled: false
licence_touched: false
---

## Question

Can the official cost be predicted from the static gate count to 1%, to screen without the verifier?

## Setup

Twelve invsqrt circuits with full official rows in the ledger; linear fit with leave-one-out. Four screen/full pairs.

## Results

### Quantitative

`C = T + 239.5` per qubit; leave-one-out error 4.2% mean, 8.1% max [M]. Reduced-shot cost matches the full cost to under 1e-5 on
4 of 4 pairs [M].

### Qualitative

The offset is the rotation charge (S2). The error is the executed-versus-static gap from conditional blocks, 5 to 6.5% on the
44-qubit circuits. DQI cost also depends on failures per salt, which neither a static model nor reduced shots predict.

## Decision

Kill the static model. Use `--shots-divisor` for invsqrt and dfthcsos screening. Any DQI screen must model failure per salt.

## Reproduce

`ledger/results.jsonl` rows; see `docs/experiments/spike-s1-cost-model.md`.

## Links

QCC-59.
