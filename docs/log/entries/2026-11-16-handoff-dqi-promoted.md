---
id: 2026-11-16-handoff-dqi-promoted
date: 2026-11-16
title: "HANDOFF said our DQI was not promoted; the promotion ledger and best/ say it was, on 2026-11-14"
type: decision
benchmark: docs
methods: [housekeeping]
status: done
outcome: n/a
commit: 164c02e
prs: []
rows: [37d8047d]
studies: []
corrects: []
backfilled: false
licence_touched: false
---

## Question

`docs/HANDOFF.md` said our own DQI `fixed.kmb` is not promoted. Which is right?

## Setup

Compared `ledger/promotions.jsonl`, the sha256 of `best/dqi/dqi.kmb` and the HANDOFF text at `164c02e`.

## Results

### Quantitative

`ledger/promotions.jsonl` has one row: dqi, sha256 `37d8047d5f4b...`, 10 salts, cost 371,563,918,246, 2026-11-14. `sha256sum best/dqi/dqi.kmb`
gives the same hash. [M]

### Qualitative

HANDOFF (table row "What is in `best/`", the paragraph under it, the `best/` row in the not-in-git table and backlog item 1)
still named the public `e9f54be3` or asked for the promotion. All four now say `37d8047d` is promoted.

## Decision

Fix HANDOFF only. Pandan card QCC-54 ("Promote own DQI fixed.kmb into best/", `needs_human`) describes work that is done; whether to close it is
the owner's call, so it is left open and asked about.

## Reproduce

```
sha256sum best/dqi/dqi.kmb
cat ledger/promotions.jsonl
```

## Links

`docs/HANDOFF.md`; ledger row `37d8047d`.
