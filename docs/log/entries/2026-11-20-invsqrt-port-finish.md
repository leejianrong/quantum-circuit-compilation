---
id: 2026-11-20-invsqrt-port-finish
date: 2026-11-20
title: "invsqrt port Stage C2: our wiring of the finishing passes reproduces 321aff83 byte for byte"
type: run
benchmark: invsqrt
methods: [port, stage-ledger]
status: done
outcome: positive
commit: e68048c
prs: []
experiments: []
rows: [321aff83]
studies: [docs/experiments/invsqrt-port-plan.md]
backfilled: false
licence_touched: true
---

## Question

Do our own driver and the vendored finishing passes, run in the order of his `pipeline.sh` and `post_inplace.sh`, turn the raw 46-qubit build into the public circuit `321aff83` exactly, and what does each pass save?

## Setup

`src/invsqrt_gen/port/stages.py finish` in the sandbox of the reference build (`scripts/invsqrt_port_finish.sh`: podman, no network, inputs read-only, CPython 3.13 + numpy, competition `kickmix.so` and verifier read-only). Our code builds the raw kmx at width 46 with the 13 patches, then runs each vendored pass as its own process (audit_affine, audit_pairs, hold_pass, up to four audit_affine/postpass rounds, merge_zpow, kmx_to_kmb, prove_any, then relocate_cs2, recompile, prove). After every pass that rewrites the text we compute the exact expectation and the modelled cost.

## Results

### Quantitative

Final file `321aff83636214196daa9cbc9dcc9c5e12a155bcff8d9989e98b8cee40935177`, identical to the public circuit; exact full-domain proof PASS on 3,133,452 inputs with every HMR transcript; the run takes about 45 s [M]. Modelled cost along the passes [M]:

| pass | Toffolis | T | modelled cost | change |
|---|---|---|---|---|
| generator (raw) | 1,519.57 | 4 | 80,565.2 | |
| hold_pass | 1,517.57 | 4 | 80,473.2 | -92.0 |
| postpass (1 round; round 2 finds nothing) | 1,512.57 | 4 | 80,243.2 | -230.0 |
| merge_zpow | 1,512.57 | 3 | 80,231.7 | -11.5 |
| relocate_cs2 | 1,511.57 | 1 | 80,162.7 | -69.0 |

The sum is 402.5 (0.5%), the gap C1 left. The same bytes have official full-verifier rows in the ledger (0 failures), so no new verify was run; byte identity is the check.

### Qualitative

Every saving is a local rewrite of the text, with no new idea: the passes fold recomputed products, affine products and rotations. This means improvements to the generator's tables and loaders (S3) will still get these 0.5% at the end, and our own outputs should go through the same passes.

## Decision

Stage C is done. S3 (QCC-61) next, on the working port. The port covers the 46-qubit line only; the 44-qubit circuits still have no source we hold.

## Reproduce

`ARCHIVE=... PY313=... VENV=... IMG=... bash scripts/invsqrt_port_finish.sh WORK OUT` (variables in the header); rows in `docs/experiments/data/invsqrt_port_finish.json`.

## Links

QCC-68, `docs/experiments/invsqrt-port-plan.md`, [C1](2026-11-19-invsqrt-port-wiring.md).
