---
id: 2026-11-12-invsqrt-generator
date: 2026-11-12
title: "invsqrt: our own generator takes the reference from ratio 1.0 to 7.00 (136 qubits), then 8.40 (121 qubits)"
type: experiment
benchmark: invsqrt
methods: [generator, qubit-reduction, cost-breakdown]
status: done
outcome: positive
prs: [46, 54, 57]
studies: [docs/experiments/invsqrt-generator.md]
backfilled: true
licence_touched: true
---

## Question

Can a generator written from the benchmark paper, the host's Apache-2.0 reference builder and standard numerics
(ADR-0009 stage 1) get a verifying circuit well below the reference's 2,076,774, and what then drives its cost?

## Setup

This entry was backfilled from the study note and git history on 2026-11-15. `src/invsqrt_gen/` (named so because the host package is `invsqrt`)
builds from `Params`: `a` segment bits, `frac` fractional bits, `guard`. Design: normalise, one unary-iteration
lookup, Horner with radix-4 Booth rows, borrow trick, phase by controlled-swap shift plus `Z_POW`, exact mirror
uncompute. A bit-exact numpy model (`tests/unit/test_invsqrt_gen.py`) fixes the error before any verifier run.
Public circuits were cost oracles only (totals), plus one aggregate-only look logged at the end of the note.
Commit, machine: not recorded.

## Results

### Quantitative

| Step | Qubits | Static Toffolis | Cost | Ratio |
|---|---:|---:|---:|---:|
| Baseline (host reference) | 260 | 7,735 | 2,076,774 | 1.00 |
| v1: pair normalisation, library adders | 151 | 3,252 | 524,931 | 3.96 |
| + borrow-window trick, own ripple adder | 146 | 2,400 | 383,157 | 5.42 |
| + lazy scratch, bit normalisation | 133 | 2,271 | not run | |
| + radix-4 Booth (`--a 7 --frac 30,20,11 --guard 4`) | 136 | 1,949 | 296,738.6 | 7.00 |
| + centered remainder, split phase, tuned widths (QCC-13) | 121 | 1,710 | 247,262.5 | 8.40 |

The Booth build passed 5 salts with 0 failures and identical cost [M]. Horner is about 57% of its cost, lookup 14%,
the two shifts 22%, 33 rotations 11% [M].

### Qualitative

* The borrow trick alone removed about 18% of Toffolis (carry chains 30 to 24 bits) [M].
* The step-0 product `r V_1` dominates, and the uncompute mirror pays it twice.
* The 136 qubits are 22 `x`, 5 flags, 67 Horner registers and about 40 transient [M].
* The aggregate look at the public frontier gave two structural facts (one working qubit with `HMR` per rotation;
  two rotation blocks with overlapping angle ranges, i.e. coarse plus fine word). Both were tried next and neither pays alone
  (see `2026-11-12-invsqrt-bitserial`). The note counts 43 rotations; later notes say 42 or 45, so the count is not consistent across notes.

## Decision

Next lever: never hold the full `V_0`; phase the coarse word, clear it by measurement, then build and phase only the
small residual. That became QCC-13.

## Reproduce

```bash
uv run python -m invsqrt_gen.cli --a 7 --frac 30,20,11 --guard 4 out/g4   # writes out/g4.kmb and out/g4.kmx
QCC_DATA=$PWD/data uv run bench verify invsqrt out/g4.kmb --salts 5
```

## Links

PRs 46, 54, 57; `docs/experiments/invsqrt-generator.md`; `docs/PROVENANCE.md`.
