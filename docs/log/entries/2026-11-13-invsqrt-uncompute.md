---
id: 2026-11-13-invsqrt-uncompute
date: 2026-11-13
title: "invsqrt ratio 12.34 (93 qubits, 168,237.5): lean qubits and exhaustive windows pay, the Horner mirror cannot be removed"
type: experiment
benchmark: invsqrt
methods: [generator, uncompute, qubit-reduction]
status: done
outcome: positive
prs: [87, 88]
experiments: [E023, E024, E025]
rows: [cc5472d2]
studies: [docs/experiments/invsqrt-uncompute.md]
backfilled: true
licence_touched: true
---

## Question

Starting from the 101-qubit generator (195,062.72, ratio 10.65), can attacking the doubled uncomputation (the
Horner mirror, 53% of Toffolis) and the qubit peak reach ratio 12, then 15, then the frontier (94,599.6)?

## Setup

This entry was backfilled from the study note and git history on 2026-11-15. Everything is our own derivation (ADR-0009 stage 1); the only look at a
public circuit was aggregate statistics logged in `docs/PROVENANCE.md`, and no change derives from it. All builds
are predicted with `predict.py` and checked against the bit-exact model (unit tests plus 67k simulated inputs on
the full circuit). Commit and machine: not recorded.

## Results

### Quantitative

| Build | Qubits | Toffolis | Cost | Ratio |
|---|---:|---:|---:|---:|
| Start 29,19,10 g3 (E018) | 101 | 1,609 | 195,062.7 | 10.65 |
| + no ancilla for last carry, constant top bits, lent `x[21]` | 97 | 1,605 | 186,949 | 11.11 |
| + 28,19,10 g2 table, exhaustive row windows | 95 | 1,507 | 176,268 | 11.78 |
| + one extension qubit | 94 | 1,493 | 173,096 | 12.00 |
| + polish radius 2 | 94 | 1,489 | 170,103 | 12.21 |
| + V_2 at 9 bits (28,19,9, E023) | 93 | 1,487 | 168,237.5 | 12.34 |

E023 passes 5 of 5 salts with 0 failures (168,237.44 to 168,237.59; sixth digit moves because 11 conditional
Toffolis run on about half the shots), circuit sha256 prefix `cc5472d2` [M]. Ratio 15 (E024) and the frontier (E025)
were not reached.

### Qualitative

* All the gains were removal of work that bought nothing: no ancilla for the carry into the top bit, constant-zero
  table bits, the always-one leading qubit `x[21]` lent as scratch, and carry ripples cut at the highest bit a row can
  ever change, computed exhaustively over the 2,350,089 reachable inputs (70 Toffolis at 28,19,10) [M].
* Measurement-based uncompute fails for in-place sums: nothing alive can pay the phase, so erasing costs a carry
  chain again. The Horner mirror (372 of 1,489) cannot be replaced by measurement [I, derived].
* Carry-save trees, gradient catalyst, higher degree or larger table, Estrin, shared products, qubit reuse and
  copy-and-measure all land at wash or loss, with qubit and Toffoli costs given in the note [I].
* Earlier infeasible 28,19,10 g2 became the best set once a qubit and a row were gone; polish radius 2 mattered, 3 and 4 did not [M].
* CORRECTION inside the study: an earlier 28,19,9 fit had not used `--reachable`, which is why it looked infeasible.
* Ratio 15 needs both the frontier's cheaper `2^s` shifts and a polynomial stage in 35 qubits above `x`; neither follows from anything here [I].

## Decision

Horner family stalls near 90 qubits. E024 and E025 closed as not reached. Nothing touches `best/`.

## Reproduce

```bash
uv run python -m invsqrt_gen.cli --a 7 --frac 28,19,9 --guard 2 --pm1 --rnd --polish --reachable --radius 2 out/e023
flock /tmp/qcc-heavy.lock env QCC_DATA=$PWD/data uv run bench verify invsqrt out/e023.kmb --salts 5
```

## Links

PRs 87, 88; E023, E024, E025; row `cc5472d2`; `docs/experiments/invsqrt-uncompute.md`.
