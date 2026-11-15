---
id: 2026-11-13-invsqrt-sqrt-division
date: 2026-11-13
title: "invsqrt by square root and division: a 46-qubit design re-derived, our own builds reach 90 qubits (281,802 at 1/20 shots), consuming multiplier not closed"
type: experiment
benchmark: invsqrt
methods: [sqrt-division, source-decode, qubit-reduction]
status: done
outcome: inconclusive
prs: [140, 145, 147, 152, 154, 157, 161, 162, 184]
rows: [321aff83]
studies: [docs/experiments/invsqrt-sqrt-division.md]
backfilled: true
licence_touched: true
---

## Question

The public 46-qubit invsqrt (verified by us at 80,162.7 on 10 salts) uses almost no table. Can we re-derive its
square-root and division design in our own words and build it, and where do its 46 qubits come from?

## Setup

This entry was backfilled from the study note and git history on 2026-11-15. Source studied read-only: the public Apache-2.0 circuit of the `syed3000/vqcc-own-circuit-portfolio` dataset (v12, sha256 prefix `321aff83`), its builder
sources and a public walkthrough. Measured numbers come from running the circuit in the kickmix simulator on 1,440 to 1,500
inputs and classifying qubits at snapshots. Our model is `src/invsqrt_gen/sqrtdiv.py`; stages in `sqrtdiv_stages.py`,
`sqrtdiv_circuit.py`, `rec.py` and `defadd.py`. Our builds were screened at 1/20 of the shots on one salt. Commit, machine: not recorded.

## Results

### Quantitative

| Build | Qubits | Executed Toffolis | Screen cost |
|---|---:|---:|---:|
| V0 (own code, full) | 134 | 2,618 static | 397,977.6 (ratio 5.2) |
| V1 (table released, numerator in place) | 105 | 2,904 static | 341,878.1 (ratio 6.07) |
| V2 (signed-digit product, deferred adders) | 90 | 2,780 | 281,802 (ratio 7.37) |

All three PASS the official verifier at 1/20 of the shots, one salt (screening only). E023 is 168,237 and the reference 80,163. Error budget: integer model
2^-24.99 (V0), 2^-24.94 (V2); first-order truncation 2^-25.42, 2^-26.42 centred [M]. The reference's live width: 26 after
the root, 42 to 44 around the table and product, 31 after the coefficient is measured away, peak runs of 46 scattered over 391 runs [M].

### Qualitative

* The idea: root in place (12-bit root `v` plus signed residual `h` in the 22 input wires), a one-coefficient correction, a small table, non-restoring
  division whose quotient digits go straight to the rotations. The saving is algorithm and lifecycle, not layout.
* A plain build is worse than E023 (about 86 qubits, 193k): the saving lies in the in-place lifecycle of product and divider [M].
* Decoded dynamically: quotient bits appear one per row in wires freed by the shrinking remainder; the divider's adder keeps only two alternating carry wires and
  pays their phase debts in the mirror. Our gadget `fd_add`/`md_add` reproduces this on 49 parameter sets. Alone it does not shrink E023: the peak (93) sits in two other stages.
* Signed-digit product rows (V2) came from the decode: each row is one plain add, no AND temporaries.
* Dead end as recorded: the consuming multiplier. Repaying dropped low columns by recomputation in the mirror does not close, since both values of a dropped bit give an in-range predecessor in
  100% of steps (`tests/unit/test_invsqrt_lowcols.py`). The note concluded that a 14-wire saving by this route is a dead end, with about 215k at best from what remained.
* CORRECTION (added 2026-11-15 in the note, from `2026-11-15-invsqrt-syed-decode`): reading the builder source shows the consuming product is ten signed-digit rows into a 16-wire word and the table is loaded twice because the inverse needs the coefficient; the "dead end" assumed a dropped-column problem the real design does not have. Not yet re-checked by us.

## Decision

Treat the consuming product as a lead, not a result. Do not build stages after the root until the lifecycle is
understood (it was, next entry). Nothing touches `best/`.

## Reproduce

The note gives no single command; the model is `src/invsqrt_gen/sqrtdiv.py` with tests `tests/unit/test_invsqrt_sqrtdiv.py`,
`test_invsqrt_defadd.py`, `test_invsqrt_lowcols.py`. Screen runs use `bench verify` with `--shots-divisor`.

## Links

PRs 140, 145, 147, 152, 154, 157, 161, 162, 184; row `321aff83`; `docs/experiments/invsqrt-sqrt-division.md`; corrected by `2026-11-15-invsqrt-syed-decode`.

> Corrected in part by [2026-11-15-invsqrt-syed-decode](2026-11-15-invsqrt-syed-decode.md): the consuming multiplier is not a dead end according to the builder source; our own re-check is still pending.
