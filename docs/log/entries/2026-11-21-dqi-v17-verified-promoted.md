---
id: 2026-11-21-dqi-v17-verified-promoted
date: 2026-11-21
title: "syed3000 v17 dqi verifies at 3.384e11 on 10 salts on Kaggle and is promoted: about 72.2x"
type: run
benchmark: dqi
methods: [public-diff, promotion]
status: done
outcome: positive
commit: 890d004
prs: []
experiments: []
rows: [a31716fa]
studies: []
backfilled: false
licence_touched: true
---

## Question

Does the DQI circuit in syed3000's v17 dataset ([refetch](2026-11-21-public-refetch-v17.md)) pass the official verifier on every salt, and does it beat `best/`?

## Setup

`bench kaggle run notebooks/dqi_verify_syed` (DQI never runs locally, ADR-0002): the kernel reads the dataset's `dqi.kmb` and runs `bench verify dqi --salts 10` with the official verifier; peak child RSS 9.85 GB. The same bytes (`a31716fa...`) were copied to `~/qcc-circuits/dqi/syed3000_a31716fa.kmb` and `bench promote` ran on the merged ledger row (dry run first).

## Results

### Quantitative

PASS, 0 failures in 10 salts, worst cost 338,393,910,565.64 [M]; his receipt says 336,846,688,159 (one salt, so 0.5% lower than our worst of ten). Ratio about 72.2 using the baseline implied by his table (the repo's own baseline row is in `docs/COMPETITION.md`). `best/dqi` goes from 348,953,023,428 (`00ac37d4`, 70.04x), 3.0% lower. With the invsqrt promotion of the same day and `best/dfthcsos` unchanged (11.38x), the geometric mean is about 28.67 [I, ratios from the implied baselines].

### Qualitative

His claim reproduces within the salt spread. His generator source (`dqi_generator.zip`, profile `stack100`) is now in our `public/` and has not been read yet.

## Decision

Promoted by `bench promote`. Not submitted (owner decision). Next: read the v17 generators for invsqrt (port, S3) and DQI (our `fixed4` is 67.30x against 72.2x).

## Reproduce

`uv run bench kaggle run notebooks/dqi_verify_syed`; `uv run bench promote dqi ~/qcc-circuits/dqi/syed3000_a31716fa.kmb --dry-run`.

## Links

QCC-65, QCC-19, [invsqrt v17](2026-11-21-invsqrt-v17-verified-promoted.md).
