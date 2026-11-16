---
id: 2026-11-16-promote-fixed3s
date: 2026-11-16
title: "Promoted fixed3s (DQI 66.75x) into best/; the owner now leaves promotion to the agent"
type: decision
benchmark: dqi
methods: [promotion]
status: done
outcome: n/a
commit: eb74b80
prs: [204]
rows: [f983871e]
studies: []
corrects: []
backfilled: false
licence_touched: false
---

## Question

Promote `fixed3s`, and what is the rule for promotions from now on?

## Setup

`bench promote dqi --dry-run`, then `bench promote dqi` on the Kaggle output `fixed3s.kmb` (sha256 `f983871ec620...`):
10 salts, 0 failures, worst cost 3.66149e11 against 3.67525e11 for the previous `best/dqi` (`c9d53c1f`).

## Results

### Quantitative

`ledger/promotions.jsonl` third row, prev sha `c9d53c1f`. Ratio 66.75. [M]

### Qualitative

The owner said on 2026-11-16 to stop asking before promotions. The rule recorded in `AGENTS.md` and `HANDOFF.md`: promote only after
an official 10-salt verify with 0 failures and a better worst cost, dry run first; never submit without the owner.

## Decision

`best/dqi` is `fixed3s`. Still below the public 67.44. Nothing submitted.

## Reproduce

```
uv run bench promote dqi out/kaggle/leejianrong__qcc-dqi-gen/fixed3s.kmb --dry-run
```

## Links

`2026-11-16-dqi-synthesis-nested-norm`; PR 204; ledger row `f983871e`.
