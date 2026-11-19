---
id: 2026-11-19-invsqrt-reference-build
date: 2026-11-19
title: "invsqrt builder reproduced byte for byte in a sandbox; it executes 78 of its 255 Python files"
type: run
benchmark: invsqrt
methods: [port, reference-build, trace]
status: done
outcome: positive
commit: 81a2863
prs: []
experiments: []
rows: []
studies: [docs/experiments/invsqrt-port-plan.md]
backfilled: false
licence_touched: true
---

## Question

What exactly does syed3000's v12 invsqrt builder execute, so that the port can vendor the true closure?

## Setup

Owner approval (2026-11-19) for one container build. `scripts/invsqrt_reference_build.sh`: rootless podman, no network, source
read-only, glibc 2.39 image, CPython 3.13.13 + numpy 2.2.4, competition `kickmix.so` and verifier read-only (pinned SHA-256
matched). An audit hook in the venv logged opened files and executed code objects. Run twice.

## Results

### Quantitative

Both runs: `BUILT invsqrt.kmb 321aff83...` (the dataset's 46-qubit circuit, 80,162.76), exact full-domain proof PASS, 63 s and 65 s
[M]. 78 Python files (536 KB) executed, all from the archive; 302 non-Python files (16.3 MB) opened [M]. A name-based static scan
had found 19 files [M].

### Qualitative

The builder looked like 43k lines of research tree but runs a 78-file generator plus pinned data. The opened data over-counts what is
needed because pinned sources hash-check files they never read for content. The first trace used the `import` audit event, which
carries no path for ordinary source imports; the `exec` event with the code object's filename is the right one.

## Decision

Stage C: vendor the 78 modules byte-identically, wire the 13 patches ourselves, per-patch ledger, exact proof, official verifier.
dfthcsos builder: separate decision, not taken.

## Reproduce

`scripts/invsqrt_reference_build.sh` (variables in its header); outputs in `~/qcc-builds/`.

## Links

QCC-68, PROVENANCE S14 and the 2026-11-19 row, `docs/experiments/data/invsqrt_v12_executed_py.txt`.
