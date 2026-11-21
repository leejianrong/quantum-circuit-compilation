---
id: 2026-11-21-invsqrt-v17-verified-promoted
date: 2026-11-21
title: "syed3000 v17 invsqrt (43 qubits) verifies at 72,440.37 on 10 salts and is promoted: 28.67x"
type: run
benchmark: invsqrt
methods: [public-diff, promotion]
status: done
outcome: positive
commit: 9048d0a
prs: []
experiments: []
rows: [70fe5f79]
studies: []
backfilled: false
licence_touched: true
---

## Question

Does the invsqrt circuit in syed3000's v17 dataset ([refetch](2026-11-21-public-refetch-v17.md)) pass the official verifier on every salt, and does it beat `best/`?

## Setup

`70fe5f79...` copied byte-identically to `~/qcc-circuits/invsqrt/syed3000_70fe5f79.kmb`; `bench verify invsqrt --salts 10`, full shots, official verifier, under the heavy lock; then `bench promote` (dry run first).

## Results

### Quantitative

PASS, 0 failures in 10 salts, worst cost 72,440.37 (28.67x), 1,043 s wall [M]. His claim was 72,440.35, so the receipt reproduces. `best/invsqrt` goes from 74,797.40 (`0af21cb8`, 27.77x) to 72,440.37, 3.2% lower; the geometric-mean contribution rises with it (see `docs/knowledge/benchmarks.md`).

### Qualitative

The circuit uses 43 qubits against 44, so the public invsqrt line moved again within four days of the v13 promotion.

## Decision

Promoted by `bench promote` (rule: 10 salts, 0 failures, better worst cost). Not submitted: submission needs the owner. The DQI circuit of the same dataset is being verified on Kaggle. Next: study the v17 `invsqrt_generator` for the port.

## Reproduce

`QCC_DATA=$PWD/data uv run bench verify invsqrt ~/qcc-circuits/invsqrt/syed3000_70fe5f79.kmb --salts 10`.

## Links

QCC-65, QCC-68, [v13 promotion](2026-11-17-public-v13-verified-promoted.md).
