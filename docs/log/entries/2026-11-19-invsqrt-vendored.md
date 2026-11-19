---
id: 2026-11-19-invsqrt-vendored
date: 2026-11-19
title: "invsqrt port Stage C0: the 78 executed modules of the v12 builder vendored byte for byte"
type: run
benchmark: invsqrt
methods: [port, vendoring]
status: done
outcome: positive
commit: 0477830
prs: []
experiments: []
rows: []
studies: [docs/experiments/invsqrt-port-plan.md]
backfilled: false
licence_touched: true
---

## Question

Can the traced closure of the invsqrt builder be vendored under `third_party/` verbatim, as was done for DQI?

## Setup

78 files from the executed list copied from the path-checked unpacked v12 archive with their layout (`src/...`), plus LICENSE and
NOTICE. Compared with the archive's own `SHA256SUMS`.

## Results

### Quantitative

78 of 78 files match the archive's checksums; 848 KB on disk; none missing from the archive's checksum list [M]. A unit test
pins the manifest. Data files (302, 16 MB) are not vendored.

### Qualitative

Vendoring is mechanical now that the closure is traced. The hard part is the wiring: the pinned base modules locate their data
by path (`FG`, `work/c10/narrow/...`) and hash-check it, so our wiring must assemble a work tree from vendored code plus the
downloaded data before it can call the generator.

## Decision

Stage C1: our own wiring in `src/invsqrt_gen/port/` that assembles the tree and applies the 13 patches in order, starting with the
base build, and records qubits and Toffolis per prefix of patches.

## Reproduce

`tests/unit/test_vendored_invsqrt.py`; `third_party/syed_invsqrt/NOTICE_VENDORED.md`.

## Links

QCC-68, PROVENANCE 2026-11-19 rows, THIRD_PARTY_NOTICES.
