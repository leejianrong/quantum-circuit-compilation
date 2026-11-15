---
id: 2026-11-14-syed-portfolio-verified
date: 2026-11-14
title: "syed3000's portfolio verified by us: invsqrt 25.91x, DQI 67.44x, dfthcsos 11.31x (geometric mean about 27.0)"
type: run
benchmark: infra
methods: [verify, public-reference]
status: done
outcome: positive
commit: 8ac3eae
prs: [183]
rows: [321aff83, 7cbe8ecf, 30285faf]
studies: [docs/PROVENANCE.md]
backfilled: true
licence_touched: true
---

## Question

What do the best public circuits actually score under the official verifier, with several salts, so that
our own work is measured against a verified frontier and not against a leaderboard number?

## Setup

The three circuits of the Kaggle dataset `syed3000/vqcc-own-circuit-portfolio` (Apache-2.0 as stated),
fetched with `scripts/fetch_public.sh`, verified unmodified with the official verifier, 5 salts each, full
shots, on 2026-11-14 (ledger timestamps 18:27 to 18:49 UTC). All three runs were made on the 31 GB machine.
Reconstructed from ledger rows and PR 183.

## Results

### Quantitative

| Benchmark | Circuit | Qubits | Worst-salt cost | Ratio | Failures |
|---|---|---:|---:|---:|---:|
| invsqrt | `321aff83` | 46 | 80,163 | 25.91 [M] | 0 |
| dqi | `7cbe8ecf` | 889 | 3.6239e11 | 67.44 [M] | 0 |
| dfthcsos | `30285faf` | n/a | 2.9664e8 | 11.31 [M] | 0 |

The geometric mean of the three ratios is about 27.0 [M]. For comparison, our leaderboard entry is 25.218
(a portfolio of other participants' public circuits, from `docs/HANDOFF.md`).

### Qualitative

* Every circuit passed at every salt, so none of the ratios depends on a lucky salt.
* Our own best at the time was invsqrt 12.34, DQI 65.77 and dfthcsos 2.50, so only DQI was within 3%.

## Decision

Use these three as the reference frontier. Decode each builder (PRs 181, 184, 185) before deciding
what to build ourselves.

## Reproduce

```
bash scripts/fetch_public.sh
QCC_DATA=$PWD/data uv run bench verify invsqrt public/<path>/invsqrt.kmb --salts 5
```

## Links

PR 183, `docs/PROVENANCE.md`, `ledger/results.jsonl` rows above.
