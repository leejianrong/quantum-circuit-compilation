---
id: 2026-11-28-public-refetch-1126-checked
date: 2026-11-28
title: "The 2026-11-26 refetch: a new dfthcsos package is 0.77% cheaper and is promoted (13.46x); the new dqi differs from best/ by 9 Toffolis; the new invsqrt is a repack"
type: run
benchmark: infra
methods: [public-diff, promotion]
status: done
outcome: positive
commit: a5607ea
prs: []
experiments: []
rows: [aa9b2f60, 6b592145, 24516e97]
studies: []
corrects: []
backfilled: false
licence_touched: true
---

## Question

Do any of the 21 files that `bench public-diff -20261126` found beat what is in `best/`?

## Setup

Official verifier, one salt then ten (`flock /tmp/qcc-heavy.lock`, CPU). The dfthcsos package is the `ozertuu/vqcc-super-sota-verified-portfolio-28-091` output (directory `dfthcsos/`, 15 `angle_k` files plus `submission.npz`). The DQI file was only indexed (`bench index`), not run: DQI verifies on Kaggle only.

## Results

### Quantitative

| File | Result [M] |
|---|---|
| dfthcsos `aa9b2f60` | cost 249,169,842 against 251,089,558 for `24516e97` (-0.77%), 10 salts and the 1-salt run, 0 failures; ratio about 13.46 against 13.36 |
| invsqrt `6b592145` | 60,927.58, equal to `bb676b95` (a repack, 1 salt) |
| dqi `dbb2ada3` | same 69,836,332 instructions and 900 peak width as `141f02ac`; CCX 312,245 against 312,254, CCZ 6,716 against 6,717 (static counts, [M]); not run |

### Qualitative

The dfthcsos gain is a different `submission.npz` (the words changed) with 5 changed `angle_k` files. It is worth about 0.26% on the geometric mean. The dqi file is a re-save of the same circuit with 9 Toffolis fewer; at about 830 Toffolis per qubit that is below any measurable cost change, so it is not worth a Kaggle run on its own.

## Decision

`bench promote dfthcsos` (dry run first, 11 salts, worst cost 2.4917e+08): `best/dfthcsos` is now `aa9b2f60`. Nothing is submitted. dqi and invsqrt in `best/` are unchanged.

## Reproduce

`QCC_DATA=$PWD/data uv run bench verify dfthcsos public/ozertuu__vqcc-super-sota-verified-portfolio-28-091-20261126/files/submission/dfthcsos --salts 10`, then `bench promote dfthcsos <dir>`. DQI: `uv run bench index --bench dqi <file>`.

## Links

[Previous promotion](2026-11-24-public-portfolio-verified-promoted.md), `ledger/promotions.jsonl`.
