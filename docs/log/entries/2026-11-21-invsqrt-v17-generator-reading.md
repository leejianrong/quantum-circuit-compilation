---
id: 2026-11-21-invsqrt-v17-generator-reading
date: 2026-11-21
title: "v17 invsqrt generator read: a 30-stage compiler plus lineage passes, and only 0.3% accuracy slack left"
type: reading
benchmark: invsqrt
methods: [source-study]
status: done
outcome: positive
commit: 31ebdd2
prs: []
experiments: []
rows: [70fe5f79]
studies: [docs/experiments/spike-s3-table-loader.md, docs/experiments/invsqrt-port-plan.md]
backfilled: false
licence_touched: true
---

## Question

What does the v17 `invsqrt_generator` (the source of the 43-qubit `70fe5f79`) consist of, and what does it change for the port (QCC-68) and S3 (QCC-61)? Static reading only; nothing was run or imported.

## Setup

`public/syed3000__vqcc-own-circuit-portfolio-20261121/files/invsqrt_generator/` (Apache-2.0 with NOTICE, untrusted data): its README, `verification.json`, `build.py`, file counts.

## Results

### Quantitative

The tree has 1,182 Python files in 139 MB [M]. His receipt for the final circuit: worst error over tolerance 0.9969164 at input 13,994, 34 generic rotations, 1,436.09 mean Toffolis, 43 qubits, 38,744 operations, verified on 200,540,928 shots [V]. The v12 line we ported (46 qubits) had 0.9736, so the slack is 2.7% there and 0.31% here [V, the two figures come from different sources: the decode study and this receipt].

### Qualitative

The build is not the v12 builder with more patches. `build.py` unpacks `syed_source.zip` (30-stage DAG of subprocesses, hash-checked exports, a path-rewriting step on every `.py` file), builds the original Q43 circuit (`38a1ccdc`), then replays lineage stages F01 to F16+ (`owner_lineage.py`) and a final `finish_f16.py` (majority cut, early phase payments, forward and inverse normalisation, three conditional cleanup passes, two growing-width coefficient accumulators). It needs `kickmix` and SciPy. The v12 wiring (`src/invsqrt_gen/port/stages.py`) does not carry over; a port needs a new closure trace of this build.

## Decision

1. S3 is effectively killed on the frontier: with 0.31% slack there is almost no room to move table bits, so stage 1 of the S3 plan is expected to fail on the 43-qubit line (it would still be valid, if small, on the 46-qubit port). Recorded in `docs/experiments/spike-s3-table-loader.md`. Not run.
2. The v17 builder runs a 30-stage chain of third-party subprocesses. The owner's approval covers one sandboxed container build of the v12 invsqrt builder only, so no v17 build has been run. Asking the owner for the same sandboxed route (rootless podman, no network, read-only inputs, audit hook) for the v17 builder, to get a closure trace and byte-identity before vendoring.

## Reproduce

Read the files named under Setup; nothing to run.

## Links

QCC-68, QCC-61, [v17 promoted](2026-11-21-invsqrt-v17-verified-promoted.md).
