---
id: 2026-11-21-invsqrt-v17-reference-build
date: 2026-11-21
title: "Sandboxed build of syed3000's v17 invsqrt generator reproduces 70fe5f79 byte for byte; 178 stage modules executed"
type: run
benchmark: invsqrt
methods: [port, reference-build]
status: done
outcome: positive
commit: 2e9f546
prs: []
experiments: []
rows: [70fe5f79]
studies: [docs/experiments/invsqrt-port-plan.md]
backfilled: false
licence_touched: true
---

## Question

Does the v17 `invsqrt_generator` rebuild `70fe5f79` (43 qubits, 28.67x, in `best/`), and which files does the build actually execute, so that the port can vendor the true closure?

## Setup

Owner approval (2026-11-21) for one container build. `scripts/invsqrt_v17_reference_build.sh`: rootless podman, no network, inputs read-only, CPython 3.13.13 with numpy 2.2.4 and SciPy 1.18.1, the competition `kickmix` module read-only, heavy lock held; an audit hook logged opened files and executed code objects. Two deviations from running `build.py` as shipped, both in a copy of the tree (the download is untouched): (1) the dataset stores the generator expanded, so the `syed_source.zip` that `build.py` unpacks and hash-checks does not exist; the copy takes the `syed_source` directory instead; (2) Kaggle stored every `*.json.gz` witness decompressed (the first run died in stage 17 on a missing `ALL_INPUT_ALL_HMR_OCCUPANCY.json.gz`), so the copy gets a gzip sibling of each such file (7 files; the sources only read their content). Every stage's expected hash and the final SHA-256 assertion are unchanged.

## Results

### Quantitative

`build.py` passed all 30 stage-export hash checks and the lineage stages (F16+ `b9f7d270`, then the finishing passes), and wrote `invsqrt.kmb` with SHA-256 `70fe5f79d56bd48cd8fc9602757a0520b4d11859967627906cccb3dec25b7692`, equal to the circuit in `best/` [M]. The trace shows 178 distinct Python files executed inside the extracted stage tree (of 576 there; 129 under `incumbent_sources/frozen_source`, 26 in `agents/temporal_merges`, 8 in `agents/paid_helper`, 3 in `agents/conditional_phase`, the rest in `root/`) and 43 top-level builder files; 1.39 MB of source in the stage tree [M]. List in `docs/experiments/data/invsqrt_v17_executed_py.txt`.

### Qualitative

The v17 build is a different animal from v12: it is a chain of subprocess stages, each with a pinned hash, so a port can be staged by stage (30 stage exports plus the lineage and finishing passes) rather than by patch prefix. The shipped copy needs the two repairs above to run from the Kaggle download; they are packaging, not content.

## Decision

Stage C for v17: vendor the 178 executed stage modules and the 43 builder files byte-identically with a MANIFEST and PROVENANCE row, then wire our own driver (per-stage ledger from the receipt, like `stages.py` for v12). The source for S3 and the 43-qubit line is now ours to modify; S3 stays parked on the 0.3% slack ([reading](2026-11-21-invsqrt-v17-generator-reading.md)).

## Reproduce

`GEN=... PY313=... VENV=... IMG=... TRACE=... bash scripts/invsqrt_v17_reference_build.sh WORK OUT` (variables in the header); outputs in `~/qcc-builds/{work6,out6}`.

## Links

QCC-68, [reading](2026-11-21-invsqrt-v17-generator-reading.md), [v12 reference build](2026-11-19-invsqrt-reference-build.md).
