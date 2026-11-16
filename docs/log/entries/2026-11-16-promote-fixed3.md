---
id: 2026-11-16-promote-fixed3
date: 2026-11-16
title: "Promoted our own fixed3 DQI circuit (66.50x) into best/ on the owner's instruction"
type: decision
benchmark: dqi
methods: [promotion]
status: done
outcome: n/a
commit: bfe6c35
prs: [202]
rows: [c9d53c1f]
studies: []
corrects: []
backfilled: false
licence_touched: false
---

## Question

Promote `fixed3` (extractor v3) into `best/`?

## Setup

The owner said yes on 2026-11-16. `bench promote dqi --dry-run` then `bench promote dqi` on the Kaggle output `fixed3.kmb`
(sha256 `c9d53c1f9889...`): 10 salts, 0 failures, worst cost 3.67525e11 against 3.71564e11 for the previous `best/dqi`.

## Results

### Quantitative

`ledger/promotions.jsonl` has a second row, prev sha `37d8047d`. Ratio 66.50. [M]

### Qualitative

Nothing is submitted; the leaderboard portfolio is unchanged. The owner also closed Pandan card QCC-54.

## Decision

`best/dqi` is our own circuit. It is still below the public 67.44.

## Reproduce

```
uv run bench promote dqi out/kaggle/leejianrong__qcc-dqi-gen/fixed3.kmb --dry-run
```

## Links

`2026-11-16-dqi-extractor-v3`; PR 202; ledger row `c9d53c1f`.
