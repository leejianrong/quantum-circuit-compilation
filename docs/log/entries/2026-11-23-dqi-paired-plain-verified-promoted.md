---
id: 2026-11-23-dqi-paired-plain-verified-promoted
date: 2026-11-23
title: "Our sandbox build of the DQI paired-plain profile verifies at 3.381e11 on 10 salts and is promoted: 0.085% under the stack100 circuit"
type: run
benchmark: dqi
methods: [sandbox-build, promotion]
status: done
outcome: positive
commit: 2bc7149
prs: [245]
experiments: []
rows: [fc2564c6]
studies: [docs/experiments/ideas-adjacent-fields.md]
backfilled: false
licence_touched: true
---

## Question

Does the `paired-plain` profile of the v17 DQI generator, built by us in the sandbox container (`scripts/dqi_v17_build.sh`), pass the official verifier on every salt and beat `best/dqi` (`a31716fa`)?

## Setup

The build gave `fc2564c6...` (829 MB, 890 qubits, 359,293 static Toffolis, 10,320 Fredkins lowered), equal to the generator's own manifest hash [M]. The file went up as a private Kaggle dataset (`leejianrong/qcc-dqi-paired-plain-fc2564c6`, owner-approved route) and `bench kaggle run notebooks/dqi_verify_fc25` ran `bench verify dqi --salts 10` with the official verifier: 2,124 s, peak child RSS 9.86 GB. The dataset is private and can be deleted.

## Results

### Quantitative

PASS, 0 failures in 10 salts, worst cost 338,105,618,600 [M]; `a31716fa` was 338,393,910,566, so 0.085% lower. Eight salts sit near 3.3656e11 and two near 3.3811e11, the same two-cluster pattern as before. Ratio about 72.26 (72.2 x 338.394 / 338.106, using the baseline implied by the public table) [I]. `bench promote` ran as a dry run first, then for real; `best/dqi` is now `fc2564c6`. The geometric mean moves by about 0.03% [I].

### Qualitative

The sandbox route reproduces a public profile byte for byte, so the generators we now own can be changed and verified without the third-party archive's own build.

## Decision

Promoted by `bench promote`. Not submitted (owner decision). The refreshed `best/` is not on the leaderboard: the hosted score is still the earlier submission.

## Reproduce

`bash scripts/dqi_v17_build.sh` (profile `paired-plain`), then `uv run bench kaggle run notebooks/dqi_verify_fc25` against a private dataset holding the file; `uv run bench promote dqi ~/qcc-circuits/dqi/syed3000_fc2564c6.kmb --dry-run`.

## Links

QCC-19, [DQI v17 promoted](2026-11-21-dqi-v17-verified-promoted.md), [DQI generator reading](2026-11-22-dqi-v17-generator-reading.md).
