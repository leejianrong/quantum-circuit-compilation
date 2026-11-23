---
id: 2026-11-24-search-code-in-v17-correction
date: 2026-11-24
title: "Correction: the public v17 generator does ship search code (window search and evolve_cuts); our vendored copy leaves it out"
type: correction
benchmark: invsqrt
methods: [source-reading]
status: done
outcome: correction
commit: e5fcb93
prs: []
experiments: []
rows: []
studies: [docs/experiments/ideas-adjacent-fields.md]
corrects: [2026-11-23-adjacent-fields-verified]
backfilled: false
licence_touched: true
---

## Question

The verification entry said no annealing, evolutionary or search code exists in the v17 invsqrt sources. Is that true?

## Setup

Listed `search/` in the fetched generator under `public/syed3000__vqcc-own-circuit-portfolio-20261121/files/invsqrt_generator/`. The earlier grep ran on `third_party/syed_invsqrt_v17/`, which vendors only the files the build needs.

## Results

### Qualitative

It is false for the generator as published. `search/README.md` describes `window_search/` (an LLM-assisted local-window rewrite search, 16 to 17 Nov, with task lists, validators and validated results) and `evolve_cuts/` (the 43-qubit cut and evolve searches, 20 Nov, with full-verifier receipts), about 560 Python files in all. The build does not use them; they are the discovery programs behind the shipped rewrites. So candidate 3 (a search harness) is **partly used** by the public team, and it is not new. What we do not have is our own runnable harness and its raw run archives (omitted for size).

## Decision

The note is amended in the same PR: candidate 3 is "partly used", and its first test should start from their `window_search` task and validator format instead of from scratch. The earlier verification entry stays as written (corrections are new entries).

## Reproduce

`ls public/syed3000__vqcc-own-circuit-portfolio-20261121/files/invsqrt_generator/invsqrt_generator/search/ && cat .../search/README.md`.

## Links

QCC-61, [verification entry](2026-11-23-adjacent-fields-verified.md).
