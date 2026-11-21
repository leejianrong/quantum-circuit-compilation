---
id: 2026-11-21-invsqrt-v17-vendored
date: 2026-11-21
title: "invsqrt port v17 Stage C0: the 220 executed modules of the 43-qubit builder are vendored byte for byte"
type: run
benchmark: invsqrt
methods: [port, vendoring]
status: done
outcome: positive
commit: 3480ecd
prs: []
experiments: []
rows: []
studies: [docs/experiments/invsqrt-port-plan.md]
backfilled: false
licence_touched: true
---

## Question

Which files make up the executed closure of the v17 builder, and can they be vendored unmodified as for v12?

## Setup

The trace of the sandboxed build ([log](2026-11-21-invsqrt-v17-reference-build.md)) gave 178 stage modules and the builder files executed from the generator root. Each was looked up in the download and copied byte for byte to `third_party/syed_invsqrt_v17/src/` with its relative path; `MANIFEST.sha256`, LICENSE, NOTICE and `NOTICE_VENDORED.md` added; a test checks the hashes and that no file was added or removed.

## Results

### Quantitative

220 files, 1.6 MB of source (2.4 MB on disk with licence files) [M]: 178 stage modules and 42 builder files. The reference-build entry said 43 builder files; one of them was the `sitecustomize.py` that the build itself modified, which is not vendored. 21 of the stage modules are rewritten by `build.py` at build time (historical absolute paths), so our copies are the shipped bytes and the driver must apply that rewrite.

### Qualitative

Data files and certificates are not vendored; the driver reads them from `public/`. PROVENANCE and THIRD_PARTY_NOTICES rows added.

## Decision

Stage C1 for v17: our own driver (assemble the tree from the download plus the vendored files, apply the path rewrite, run the 30 stage exports and the lineage and finishing passes), with a ledger row per stage from the receipt, and byte identity with `70fe5f79`.

## Reproduce

`uv run pytest tests/unit/test_vendored_invsqrt_v17.py`.

## Links

QCC-68, [reference build](2026-11-21-invsqrt-v17-reference-build.md).
