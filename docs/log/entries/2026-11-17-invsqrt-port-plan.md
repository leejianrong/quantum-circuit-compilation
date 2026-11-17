---
id: 2026-11-17-invsqrt-port-plan
date: 2026-11-17
title: "invsqrt port plan: the builder is a pinned base plus 13 live-module patches, so the closure needs a runtime trace"
type: reading
benchmark: invsqrt
methods: [port, source-study]
status: done
outcome: inconclusive
commit: b41f7fa
prs: []
experiments: []
rows: []
studies: [docs/experiments/invsqrt-port-plan.md]
backfilled: false
licence_touched: true
---

## Question

What does a staged port of syed3000's invsqrt builder, in the way DQI was done, need?

## Setup

v12 `invsqrt_source_zip` (Apache-2.0) unpacked with a path-checked `zipfile` into a scratch directory; `build.sh`,
`tools/build_variant.py` and `patches/PATCH_ORDER.txt` read as text, import structure scanned with `ast`. Nothing was
imported or run.

## Results

### Quantitative

561 files, 255 Python files (43k lines); a name-based static closure of the generator entry and the 13 patches finds only 19
files [M], because modules are located by `sys.path` edits and `spec_from_file_location`.

### Qualitative

The 13 patches in `PATCH_ORDER.txt` are the natural stage ledger. The v13 dataset dropped the source archives, so the
44-qubit and 27.77x circuits have no source we hold; the port targets the 46-qubit line. Two things block progress
without an owner decision: a runtime trace of one build (a third-party builder run, forbidden outside the container route)
and the pinned `kickmix.so`, which needs a newer libstdc++ than this WSL has.

## Decision

Ask the owner whether the container route may be used once for the invsqrt builder. Meanwhile do Stage A (inventory) of
the plan.

## Reproduce

`docs/experiments/invsqrt-port-plan.md`.

## Links

QCC-68, PROVENANCE S14.
