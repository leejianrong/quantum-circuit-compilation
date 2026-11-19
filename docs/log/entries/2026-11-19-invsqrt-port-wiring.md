---
id: 2026-11-19-invsqrt-port-wiring
date: 2026-11-19
title: "invsqrt port Stage C1: our wiring builds the 46-qubit line to within 0.5% of the reference and gives a per-patch ledger"
type: run
benchmark: invsqrt
methods: [port, stage-ledger]
status: done
outcome: positive
commit: cf9e748
prs: []
experiments: []
rows: []
studies: [docs/experiments/invsqrt-port-plan.md]
backfilled: false
licence_touched: true
---

## Question

Can our own driver, not his `build.sh`, assemble the tree and build the 46-qubit line from the vendored modules, and what does each patch contribute?

## Setup

`src/invsqrt_gen/port/stages.py` in the sandbox of the reference build (podman, no network, CPython 3.13 + numpy, competition
`kickmix.so` and verifier read-only). Vendored files checked byte-equal to the archive; every prefix of the 13 patches in its own
process, at the patch's own width and at width 46.

## Results

### Quantitative

Full set at width 46: 46 qubits, 1,519.57 Toffolis, modelled cost 80,565 (25.78x); reference 80,162.76 (25.91x). Unpatched base
`candidate10`: 48 qubits, 85,469 (24.30x). The 13 patches add 3.3% at width 48; `endpoint_v9e2` is -1,152, the largest [M, modelled cost].

### Qualitative

The 0.5% gap is the finishing passes our wiring does not yet run. Prefixes are not independent (a later patch's import-time code
supplies a plan file for prefix 10; width 46 only builds for the last two prefixes).

## Decision

Stage C2: the finishing passes from our wiring and byte-identity with `321aff83`; then S3 on the working port.

## Reproduce

`ARCHIVE=... PY313=... VENV=... IMG=... bash scripts/invsqrt_port_stages.sh WORK OUT` (variables in the script header);
data in `docs/experiments/data/invsqrt_port_ledger.json`.

## Links

QCC-68, `docs/experiments/invsqrt-port-plan.md`.
