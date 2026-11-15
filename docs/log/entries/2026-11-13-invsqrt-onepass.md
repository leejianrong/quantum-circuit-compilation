---
id: 2026-11-13-invsqrt-onepass
date: 2026-11-13
title: "invsqrt one-pass study: the frontier has a Horner unwind after all, and none of four levers moves ratio 12.34"
type: experiment
benchmark: invsqrt
methods: [source-decode, qubit-reduction, cost-breakdown, uncompute]
status: done
outcome: negative
prs: [99, 107, 112, 117, 126]
experiments: [E034, E035]
studies: [docs/experiments/invsqrt-onepass.md]
corrects: [2026-11-13-invsqrt-stage2]
backfilled: true
licence_touched: true
---

## Question

Running the whole 62-qubit public circuit and reading its registers, which of its three big levers (lookup, qubit
census, conditional fix-ups) can we implement, and at what cost? Our best stays E023 (93 qubits, 168,237.4, ratio 12.34).

## Setup

This entry was backfilled from the study note and git history on 2026-11-15. ADR-0009 stage 2. The circuit was run in the kickmix `Simulator` on 720 chosen inputs and on all 256 addresses with
four remainders, recording every qubit every 50 instructions plus the value on the rotation qubit at each of
the 45 `Z_POW`. The dump was in the agent scratchpad; nothing under `public/` was edited; no table, constant or gate
list is reproduced. Follow-ups used `src/invsqrt_gen/joint.py` and `angles.py` (scratch). Commit, machine: not recorded.

## Results

### Quantitative

| Quantity | Value |
|---|---|
| Phase reconstructed from the 45 rotations, worst relative error | 2^-24.16 (same as our E023 model) [M] |
| Arithmetic, frontier vs ours | about 760 CCX, within 2% [M] |
| Live qubits: after coarse / step 1 / step 0 / unwind / erase | 47 / 54 / 61 / 61 / 48 [M] |
| Short-carry adder, estimated | 93 to 86 qubits but +100 Toffolis, net about -2% [I] |
| Tuned angles for 28,19,8 | predicted 168,320 against 168,237, no gain [M] |
| Joint search, 28,19,8 g2 | 167,911 predicted (-0.19%), not built [I] |

### Qualitative

* CORRECTION of `2026-11-13-invsqrt-stage2`: its "no Horner mirror" reading is wrong. The table registers become functions of the remainder and
  return to functions of the address at 22,056 and 25,141, so there is a forward pass and an unwind. What differs is the unwind (measurement
  based with conditional fix-ups). Its "Reed-Muller layout with 57 extra qubits" frame is also wrong: the frontier has about 10 scratch qubits.
* The 31-qubit gap (93 to 62) is layout: a narrower table, flags inside the table, short-carry adders, recycled idle qubits. No mirror-free architecture exists [I].
* The lookup is an in-place network of ANDs of live linear forms (166 CCX, about 6,500 CNOTs) with free reverse-measurement erase.
  Our counting says a search could succeed, but a prototype could not even produce the first output: a generic degree 7 to 8 output needs a nested chain of scratch levels. Without it, 30 or more scratch qubits cancel the 100 Toffolis saved (E034).
* Idle qubits cannot be recycled as clean ancillas: ours hold data needed by `del_lookup` and un-normalisation. Dirty-qubit adders cost about twice the Toffolis.
* The frontier's table is about 36 qubits against our 47 (plus separate address and flags, about 20 in all). Flip-probing table qubits showed the slope stored with about 16 fractional bits against our 18 (E035).
* Joint coefficient and angle search is a lattice problem: every bit removed from `c_1` or `c_2` costs half a bit of error, exactly. The frontier's 2^-24.4 at 16-bit slopes cannot come from coefficient rounding alone.
* Abandoned: decoding the table basis (the 39 table qubits are XOR-mixed bases, not the bits of `c0, c1, c2`).

## Decision

Nothing built. Levers in order: short-carry adder (about 2%), lookup synthesis (at most 7%, needs a SAT or annealing tool),
measured unwind. Ratio 14 needs levers 1 and 3 together or a co-designed table. E034 and E035 closed with ratio unchanged at 12.34.

## Reproduce

The note gives scripts from the scratchpad (not committed): dump with `km.Circuit.from_file(...).to_file(out, format='kmx')`; simulate in chunks of
50 instructions with `km.Simulator(n, seed=...)`, `write_across_shots`, `do`, `read_across_shots`; GF(2) spans of 256-address truth tables.

## Links

PRs 99, 107, 112, 117, 126; E034, E035; `docs/experiments/invsqrt-onepass.md`; corrects `2026-11-13-invsqrt-stage2`.
