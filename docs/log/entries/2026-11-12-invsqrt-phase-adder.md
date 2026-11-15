---
id: 2026-11-12-invsqrt-phase-adder
date: 2026-11-12
title: "invsqrt 101 qubits, ratio 10.65: the phase adder loses, signed-digit rows and lazy allocation win"
type: experiment
benchmark: invsqrt
methods: [generator, phase-adder, qubit-reduction]
status: done
outcome: positive
prs: [70, 71]
experiments: [E018]
studies: [docs/experiments/invsqrt-phase-adder.md]
backfilled: true
licence_touched: false
---

## Question

Can a phase adder (rotate sum bits as the adder produces them, drop the stored phased word and both barrel
shifters) beat the 121-qubit centered build (247,262.49, ratio 8.40, E016)?

## Setup

This entry was backfilled from the study note and git history on 2026-11-15. All derivation is ours from the paper and the host reference builder
(ADR-0009 stage 1); no public circuit was read, so nothing was added to `docs/PROVENANCE.md`. Phase-adder variants
were built with `--fine serial` and `--split ... serial`. Commit, machine: not recorded.

## Results

### Quantitative

| Build | Qubits | Toffolis | Predicted cost | Verifier |
|---|---:|---:|---:|---|
| E016 centered Booth 28,19,9 g2 | 121 | 1,710 | 247,262 | 5 salts |
| signed-digit rows, 30,20,11 g4 | 106 | 1,700 | 213,686 | screen 213,685.64 |
| + rounding rows, 28,20,11 g2 | 104 | 1,631 | 202,564 | screen 202,564.53 |
| + tables allocated after normalising | 101 | 1,631 | 196,721 | |
| + 29,19,10 g3 (E018) | 101 | 1,609 | 195,063 | 195,062.72, 5 of 5 salts |

Phase-adder variants against the barrel (195,063): mux coarse +8.8%, mux fine +3.3%, both +12.2% [M, predicted].

### Qualitative

* The phase adder fails structurally: position `p` needs bit `p - s` for the live `s`, so every sum bit must exist
  when any multiplexer reads it. A streaming adder produces each bit once, so it needs either the stored word again or
  11 times the rotations. At best it saves its own mirror (about 1%) [I].
* Signed digits `e_i = +-1` mean one plain add per remainder bit, with no Booth operand register or selects. The
  widest row drops from 43 to 20 transient qubits; the price was accuracy (13 floors instead of 7) [M].
* Rounding is free: the carry-in of the adder rounds the slice to nearest, buying back one to two guard bits [M].
* A stray allocation: the library `multi_controlled_x` allocated 14 ancillas inside a call, so the real peak was 104,
  invisible to the builder's counter. Allocating the tables after normalising fixed it for 3 qubits, free [M].
* Measurement-cleared flags in the un-normalisation make 22 Toffoli-like gates conditional, so 11 executed fewer [M].
* Every qubit-for-Toffoli trade costed sits within a few percent of break-even (a qubit is about 19
  Toffoli-equivalents). What moved cost was removing work that bought nothing [I].

## Decision

Nothing touches `best/`. Next lever: rows are 53% of the Toffolis (846 of 1,609); narrow rows pay a full window of
carry ripple. The peak is flat across the Horner, coarse and lookup stages (101, 100, 98), so a further qubit needs all three to move.

## Reproduce

`uv run python -m invsqrt_gen.cli --a 7 --frac 29,19,10 --guard 3 --pm1 --rnd --polish --reachable out/e017`

## Links

PRs 70, 71; E018; follows `2026-11-12-invsqrt-bitserial`; `docs/experiments/invsqrt-phase-adder.md`.
