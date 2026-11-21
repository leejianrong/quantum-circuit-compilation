---
id: 2026-11-21-public-refetch-v17
date: 2026-11-21
title: "Public refetch: syed3000 v17 claims 28.71 (invsqrt 43 qubits) with generator sources; bench public-diff finds it"
type: run
benchmark: infra
methods: [public-diff, fetch]
status: open
outcome: positive
commit: 44f7173
prs: []
experiments: []
rows: []
studies: []
backfilled: false
licence_touched: true
---

## Question

What changed in the public frontier since the 2026-11-17 fetch, and can the diff be automatic (QCC-65)?

## Setup

`FETCH_SUFFIX=-20261121 bash scripts/fetch_public.sh` refetched all 23 sources into new directories (no failures); new `bench public-diff -20261121` lists circuit files whose hash is in a fresh directory only and in no ledger row (`src/bench/publicdiff.py`, tested). Downloaded files are untrusted data and were only hashed and read as text.

## Results

### Quantitative

90 new circuit files [M]: 6 invsqrt, 4 dqi, 61 dfthcsos (15 per set plus generator intermediates), 19 other (small test fixtures, one 480 MB `gf24-merge-retained14.kmb`). syed3000's README (v17, "28.71 stack") claims, from local receipts and unverified by us [V]:

| bench | circuit | claimed cost | ratio | against `best/` |
|---|---|---|---|---|
| invsqrt | `70fe5f79`, 43 qubits, 1,436.09 Toffolis | 72,440.35 | 28.669 | 27.77 |
| dqi | `a31716fa`, 890 qubits | 336,846,688,159 | 72.554 | 70.04 |
| dfthcsos | table `07f81f5f` | 295,006,518.97 | 11.375 | 11.38 (our row 294,762,513, so v17 is slightly worse) |

### Qualitative

The dataset now ships `invsqrt_generator.zip`, `dqi_generator.zip` and `dfthcsos_generator.zip` with rebuild commands and a stage receipt for invsqrt (Q43 parent, four later stages). That is the source of the 43-qubit line that the 2026-11-19 port plan said we did not hold. Licence: Apache-2.0 with a NOTICE that must travel with derivatives and name the original builder first.

## Decision

Verify invsqrt `70fe5f79` at 10 salts locally and dqi `a31716fa` at 10 salts on Kaggle (`notebooks/dqi_verify_syed`); promote through `bench promote` (dry run first) only if both pass. dfthcsos is not verified: the claim is below our `best/`. Study the new invsqrt generator for the port (QCC-68) afterwards.

## Reproduce

`FETCH_SUFFIX=-20261121 bash scripts/fetch_public.sh && uv run bench public-diff -20261121`.

## Links

QCC-65, QCC-68, [v13 promotion](2026-11-17-public-v13-verified-promoted.md).
