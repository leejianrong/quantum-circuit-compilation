---
id: 2026-11-15-invsqrt-syed-decode
date: 2026-11-15
title: "invsqrt: the 46-qubit builder's product is ten signed-digit rows into a 16-wire word, Q48 to Q46 is worth 4.2% of its cost"
type: reading
benchmark: invsqrt
methods: [source-decode, sqrt-division, qubit-reduction]
status: done
outcome: correction
prs: [184]
studies: [docs/experiments/invsqrt-syed-decode.md]
corrects: [2026-11-13-invsqrt-sqrt-division]
backfilled: true
licence_touched: true
---

## Question

What does the builder source of the public 46-qubit invsqrt (cost 80,162.76) actually do stage by stage, what
does our `src/invsqrt_gen` lack, and which ideas could beat it?

## Setup

This entry was backfilled from the study note and git history on 2026-11-15. Read-only study of the Apache-2.0 builder archive in `public/syed3000__vqcc-own-circuit-portfolio/files/invsqrt_source_zip`
(`docs/PROVENANCE.md` S14). Unpacked into the scratchpad and read only: nothing imported, built or run. Claims cite paths inside
the archive. Tags [V] verified from source text, [I] inferred by us. Target: 46 qubits, 1,511.5703125 Toffolis, 1 T, 33 rotations.
Commit, machine: not recorded.

## Results

### Quantitative

| Quantity | Value |
|---|---|
| Q48 candidate10 | 1,548.75 Toffolis, 85,468.7 [V] |
| Q46 final | 1,511.5703125 Toffolis, 80,162.76 [V] |
| 46/48 of 85,468.7 | 81,909 [V arithmetic] |
| Toffoli change about -1,710, 4 T to 1 T about -35 | lands on 80,163 [V arithmetic] |
| First / second loader | 61 to 56, and 79 to 70 Toffolis [V] |
| One qubit at the final point | 37.9 Toffoli-equivalents = 2.17%; one Toffoli 0.057% [I] |

### Qualitative

* CORRECTION of the "consuming multiplier dead end" in `2026-11-13-invsqrt-sqrt-division`: the product is ten signed-digit rows into a 16-wire word where row `i` is
  controlled by `h_i` and that wire then becomes the next top wire of the accumulator. Nothing is dropped and no low column is measured; the
  cost is that the inverse needs the coefficient again, so the table is loaded twice. We had assumed a dropped-column problem that does not exist.
* Also: there is no one-wire endpoint. The quotient signs plus a known-one wire form a 26-position ring rotated in place by cyclic CSWAPs
  with flag-affine controls, with 33 `Z_POW` on word wires [V].
* Much of the last Toffoli saving is spare-wire trading (held CSWAP pairs, rebuilt root bits, a mechanical post-pass over all 3,133,452 inputs), not new arithmetic [V].
* The table was co-designed once but not to the end: the fit maximises accuracy margin (about 2.7% of tolerance left) and makes one slope bit implicit; the loader search often hit `TIME_LIMIT`.
* Q45 is not a single trick: at Q46 every stage binds at once. His closed routes (conditional normalisation, compact endpoints at Q44 to Q50) and open ones (fused normalise and root, Q47 gate) are listed in the note.
* We already have the deferred adder, the recorder and signed-digit rows; the loader synthesis, ring endpoint, consuming layouts and width patches are missing.

## Decision

Ordered build list of ten steps; first milestone is about 1,549 Toffolis at 48 qubits (about 85.5k, ratio 24.3). Ideas ranked: Q45 (net -0.8 to -1.5%),
loader co-design (-0.6 to -1.2%), mechanical passes on E023-class circuits (-1% to -3%, low risk, can start now). Code is to be written fresh;
only ideas enter our tree (Apache-2.0 plus NOTICE). Nothing was built in this study.

## Reproduce

The note gives no commands; it is a static read of the archive.

## Links

PR 184; `docs/experiments/invsqrt-syed-decode.md`; corrects `2026-11-13-invsqrt-sqrt-division`; `docs/PROVENANCE.md` S14.
