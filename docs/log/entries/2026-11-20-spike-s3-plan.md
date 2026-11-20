---
id: 2026-11-20-spike-s3-plan
date: 2026-11-20
title: "S3 plan: table and loader co-design has a 1% target, but only on the 46-qubit port, below best/"
type: decision
benchmark: invsqrt
methods: [spike, exact-synthesis]
status: open
outcome: n/a
commit: cedc0c1
prs: []
experiments: []
rows: []
studies: [docs/experiments/spike-s3-table-loader.md]
backfilled: false
licence_touched: true
---

## Question

What is the hypothesis and the kill rule for S3, now that the port reproduces the 46-qubit line?

## Setup

Reading of `docs/experiments/invsqrt-syed-decode.md` section 4 and the C2 ledger; no code run.

## Results

### Qualitative

The loaders and coefficient rows are 244 of 1,511.57 Toffolis (16%) [V, decode study]. The accuracy slack is 2.7% of the tolerance.
The port builds the 46-qubit line (25.91x), while `best/` holds the 44-qubit circuit (27.77x) for which we have no source. A 1% gain on
the port is about 26.2x, so S3 cannot lift the score unless the technique is carried to a 44-qubit build of our own or combined with
width reductions. Four stages, each with a kill rule (the first: fewer than 16 feasible single-bit flips of the table kills it).

## Decision

Run stage 1 (read-only table freedom) first, because it is cheap and can falsify the idea. The card's "1% on the 44-qubit frontier" is
read as 1% on the 46-qubit port; the owner may prefer to deprioritise S3 against the public-frontier re-check and dfthcsos.

## Reproduce

Nothing to run yet.

## Links

QCC-61, `docs/experiments/spike-s3-table-loader.md`.
