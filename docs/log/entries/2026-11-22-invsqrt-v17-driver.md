---
id: 2026-11-22-invsqrt-v17-driver
date: 2026-11-22
title: "invsqrt port v17 Stage C1: our driver reproduces 70fe5f79 byte for byte, with a ledger row per stage"
type: run
benchmark: invsqrt
methods: [port, stage-ledger]
status: done
outcome: positive
commit: ce0b2ed
prs: []
experiments: []
rows: [70fe5f79]
studies: [docs/experiments/invsqrt-port-plan.md]
backfilled: false
licence_touched: true
---

## Question

Can our own driver, not his `build.py`, run the 30 stage exports, the packing, the lineage and the finishing passes of the v17 generator from the vendored modules, and what does each stage contribute?

## Setup

`src/invsqrt_gen/port/v17.py` in the sandbox of the reference build (`scripts/invsqrt_v17_port.sh`: podman, no network, inputs read-only). It assembles the download (checked byte-equal to the 220 vendored files), makes the two packaging repairs explicit (copy `syed_source`, gzip siblings for the decompressed witnesses), applies the path rewrite and `prepare`, runs each stage as a subprocess, checks every export hash, and writes a ledger row per export (seconds; for kmx candidates the exact expectation and modelled cost through the generator's own cost code).

## Results

### Quantitative

The run ends `BYTE-IDENTICAL 70fe5f79d56bd48cd8fc9602757a0520b4d11859967627906cccb3dec25b7692`; all 30 export hashes match; 295 s wall in total, of which the 30 stages take about 252 s [M]. Ledger (`docs/experiments/data/invsqrt_v17_ledger.json`): the stage kmx candidates are 44-qubit texts with modelled costs between 73,296 and 74,813 (1,428.6 to 1,462.0 Toffolis), not monotone: later stages trade Toffolis for width. The packing step turns the last stage (1,461.25 Toffolis, 44 qubits) into the original Q43 circuit `38a1ccdc` (1,465.25 Toffolis, 43 qubits, modelled cost 73,252.6). The lineage (F01 to F16+) and the finishing passes then take it to 72,440.35 [V, official cost] with 34 rotations, a further -812 or 1.1%. Largest single stage times: `frozen_native_builder` 67.6 s, `integrated` 38.0 s, `frozen_finisher` 28.3 s, lineage 31.5 s.

### Qualitative

One thing did not work and was dropped: a cost row for the lineage and finishing texts (the exact expectation of the F16+ text ran for an hour without finishing, so those rows carry the hash only; the official cost is the reference). Three kinds of knobs now exist for our own work: the stage scripts and their pinned inputs (30 exports), the packing to 43 qubits, and the lineage and finishing passes (about 1.1%).

## Decision

Stage C is done for v17. Next candidates, all on a source we can now modify: (1) per-stage exchange rates (S2) applied to the 30 stages to find where a Toffoli or a qubit is cheapest to remove; (2) the finishing passes on our own invsqrt circuits (they gave 0.5% on the 46-qubit line and 1.1% here); (3) S3 stays parked on the 0.3% slack. Any change must keep the exact proof and then the official verifier at 10 salts.

## Reproduce

`GEN=... PY313=... VENV=... IMG=... bash scripts/invsqrt_v17_port.sh WORK OUT` (variables in the header); ledger in `docs/experiments/data/invsqrt_v17_ledger.json`.

## Links

QCC-68, [vendored](2026-11-21-invsqrt-v17-vendored.md), [reference build](2026-11-21-invsqrt-v17-reference-build.md).
