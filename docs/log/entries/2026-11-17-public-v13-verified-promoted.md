---
id: 2026-11-17-public-v13-verified-promoted
date: 2026-11-17
title: "Public frontier moved to GM 28.1: v13-class circuits verified at 10 salts and promoted, invsqrt 27.77x, DQI 70.04x, dfthcsos 11.38x"
type: run
benchmark: infra
methods: [verify, public-reference, promotion]
status: done
outcome: positive
commit: a7986be
prs: []
experiments: []
rows: [0af21cb8, 00ac37d4, 4c6e5963, 47b31838, 46446af1, 66b4f18b, 6f79152c]
studies: [docs/PROVENANCE.md]
backfilled: false
licence_touched: true
---

## Question

The leaderboard top moved (about 30.96, ours 25.218) and syed3000's dataset was updated on 2026-11-15. What do the new
public circuits score under the official verifier, and do they beat `best/`?

## Setup

Refetched into new directories on 2026-11-17: syed3000 v13, heliosli (re-uploaded 2026-11-15), and seven notebook outputs
of the 28.1 class (koushikrudra v54, balramsrinivasan, ozertuu, adityaravi2, drpatrickchan, jeffemerson, alexchilton;
`scripts/fetch_public.sh`). Zips extracted by a path-checked `zipfile` script, nothing executed. Official verifier,
10 salts each, full shots. invsqrt and dfthcsos locally under the heavy lock; DQI on Kaggle (`notebooks/dqi_verify_syed`,
`notebooks/dqi_verify_public`). Promotion through `bench promote` (dry run first).

## Results

### Quantitative

| Track | Circuit | Worst-salt cost | Ratio | Failures |
|---|---|---:|---:|---:|
| invsqrt | koushik v54 `0af21cb8` (44 q) | 74,797.40 | 27.77 [M] | 0/10 |
| invsqrt | syed v13 `47b31838` | 75,170.65 | 27.63 [M] | 0/10 |
| dqi | koushik v54 `00ac37d4` (890 q) | 3.4895e11 | 70.04 [M] | 0/10 |
| dqi | syed v13 `46446af1` | 3.4950e11 | 69.93 [M] | 0/10 |
| dqi | balram `66b4f18b` | 3.5008e11 | 69.81 [M] | 0/10 |
| dfthcsos | koushik v54 npz `703843d3` | 294,762,513 | 11.38 [M] | 0/10 |
| dfthcsos | syed v13 | 295,445,306 | 11.36 [M] | 0/10 |

Geometric mean of the promoted set: 28.12 [M]. Before: invsqrt 21.95, dqi 67.30 (ours), dfthcsos 11.20.

### Qualitative

koushik's notebook is an aggregator that verified every public member and picked the cheapest per task, which is why
one package wins all three. DQI cost varies by salt (3.4895e11 worst here against 3.4736e11 at its default salt), so
only the 10-salt worst counts. Our own `fixed4` (67.30x) is now 4% behind on DQI. syed3000's v13 dropped the source
archives; the builders stay in v12. derrickirons' notebook has no circuit.

## Decision

Promoted `0af21cb8`, `00ac37d4`, `4c6e5963` into `best/` (`ledger/promotions.jsonl`). Nothing is submitted. DQI task 2
(study `00ac37d4`, port the adaptive gauge) now has a 4% target. The lineage of the invsqrt and DQI circuits is syed3000's
Apache-2.0 builders (NOTICE and attribution apply, PROVENANCE S15 to S18).

## Reproduce

`bash scripts/fetch_public.sh <slug>`; `QCC_DATA=$PWD/data uv run bench verify invsqrt <file> --salts 10`;
`uv run bench kaggle run notebooks/dqi_verify_public`; `uv run bench promote <bench> <candidate> --dry-run`.

## Links

PROVENANCE S15 to S18, QCC-66, `ledger/results.jsonl`, `ledger/promotions.jsonl`.
