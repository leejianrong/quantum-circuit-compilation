---
id: 2026-11-24-public-portfolio-verified-promoted
date: 2026-11-24
title: "New public portfolio verifies on all three benchmarks and is promoted: invsqrt 34.09x on 37 qubits, dqi 79.44x, dfthcsos 13.36x, geometric mean about 33.08"
type: run
benchmark: infra
methods: [public-diff, promotion]
status: done
outcome: positive
commit: 09e0160
prs: []
experiments: []
rows: [bb676b95, 141f02ac, 24516e97]
studies: []
backfilled: false
licence_touched: true
---

## Question

The 2026-11-24 refetch of the public datasets ([QCC-65](../../knowledge/open-questions.md) tooling, `bench public-diff -20261124`) listed 18 circuit files we had never seen, all from two notebook outputs (`ozertuu/25-218-starter-notebook`, `alexchilton/28-09-lb-which-circuits-survive-private-salt`) that carry the same `submission.zip` and claim a 33.17 geometric mean. Do they pass the official verifier at 10 salts, and do they beat `best/`?

## Setup

The zip was extracted into its own empty directory (`~/qcc-circuits/p1124/ozertuu/`). invsqrt and dfthcsos: `bench verify` locally under `flock /tmp/qcc-heavy.lock`, 10 salts each. dqi: Kaggle kernel `notebooks/dqi_verify_pub1124`, which reads the zip from the public notebook output (`kernel_sources`, nothing uploaded) and runs `bench verify dqi --salts 10`; peak memory about 10 GB. Then `bench promote` per benchmark, dry run first.

## Results

### Quantitative

All PASS, 0 failures in 10 salts [M]. invsqrt `bb676b95`: worst cost 60,927.61 on 37 qubits (2,076,774.23 / 60,927.61 = 34.09x), against 72,440.37 for `70fe5f79` (15.9% lower). dqi `141f02ac`: worst cost 307,633,973,843 on 900 qubits (79.44x), against 338,105,618,600 (9.0% lower). dfthcsos `24516e97` (the directory): 251,089,557.51 on 128 qubits (13.36x), against 294,763,000 (14.8% lower). Geometric mean from the worst of 10 salts: 33.08; the same measure for the previous `best/` was 28.68 [I, baselines as in `docs/COMPETITION.md`]. The notebooks' own 33.17 uses board salts and is not ours.

### Qualitative

This is the first public improvement past the v17 line on all three at once. The notebook's Provenance section credits a chain of authors (listed in `docs/PROVENANCE.md`, row S19) and states Apache-2.0. The invsqrt circuit is 37 qubits against our 43, which our own S2 analysis had ruled out as a local lever; it comes from a different construction (phase folds), so it is a redesign the public team found, not a patch.

## Decision

Promoted by `bench promote` for all three. Not submitted: the owner decides. The submission would move the hosted 28.716 to about 33.1.

## Reproduce

`FETCH_SUFFIX=-20261124 bash scripts/fetch_public.sh && uv run bench public-diff -20261124`; `uv run bench verify invsqrt ~/qcc-circuits/p1124/ozertuu/invsqrt.kmb --salts 10`; `uv run bench verify dfthcsos ~/qcc-circuits/p1124/ozertuu/dfthcsos --salts 10`; `uv run bench kaggle run notebooks/dqi_verify_pub1124`; `uv run bench promote <bench> <candidate> --dry-run`.

## Links

QCC-65, QCC-66, [DQI paired-plain](2026-11-23-dqi-paired-plain-verified-promoted.md), [v17 invsqrt promoted](2026-11-21-invsqrt-v17-verified-promoted.md).
