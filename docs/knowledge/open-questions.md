# Open questions

What we do not yet know. Owner decisions are marked; the rest are experiments waiting for someone to run them.
When one is answered, write a log entry and move it to the [claims register](claims.md).

## Owner decisions

* May the Apache-2.0 builders of syed3000 be run to regenerate their circuits? [HANDOFF](../HANDOFF.md) lists this as
  open because the permission classifier blocks it. The DQI builder has since been reproduced byte for byte inside a
  sandboxed container ([stage ledgers](../log/entries/2026-11-15-dqi-stage-ledgers.md)); confirm the policy for the
  invsqrt and dfthcsos builders.
* Is a GPU run of the dfthcsos fit with a `Lambda` penalty from the start worth the quota?
* Which licensed portfolio is submitted? Nothing is promoted or submitted without the owner
  ([PROVENANCE](../PROVENANCE.md), licence column).

## Experiments not yet run

| Question | Why it matters | Source |
|---|---|---|
| Do the penalised words (`Lambda` 283.6) survive 8 to 11-bit rounding inside the `error_2` gate, and with what `Lambda` after quantisation-aware training (which has no penalty)? | the other half of the dfthcsos gap (bits and planes) | [S4 stage 2](../log/entries/2026-11-19-spike-s4-penalised-fit.md) |
| Does the consuming multiplier work as the builder source suggests (ten signed-digit rows into a 16-wire word)? We have not re-checked or built it | the invsqrt 46-qubit lead | [invsqrt syed decode](../log/entries/2026-11-15-invsqrt-syed-decode.md) |
| Which single module of his extractor bundle (nested-norm arithmetic, retained-norm return) gives the -114 T per node? The bundle is shown to; modules are not isolated | 62% of the DQI gap | [stage ledgers](../log/entries/2026-11-15-dqi-stage-ledgers.md) |
| Does an in-place Euclid history exist that makes the reciprocal scan buildable? | the reciprocal scan is worth about ratio 10 only with it | [psi](../log/entries/2026-11-13-dqi-psi.md) |
| How does the public 70.04x DQI circuit avoid the 12,384 `CSWAP`s (79% of our 15,771 T gap) that our outer window routing needs? (Routing under a *measured* flag is not valid; see the correction.) Adaptive gauge scan is only 759 T of the rest | closes the DQI gap to the public frontier (about 4%) | [70x study](../experiments/dqi-70x-study.md) |

## Data to reconcile

* The invsqrt frontier's rotation count differs across the notes (43, 42 and 45); the
  [generator entry](../log/entries/2026-11-12-invsqrt-generator.md) flags it.
* Some notes label experiments with ids that do not match `ledger/experiments.jsonl` (for example E002 to E008 in
  the dfthcsos notes are dqi and invsqrt experiments there, and E041 is not in the ledger at all). The entries list
  only ids that match; the notes themselves are left as written.
* E040 is still open in the ledger although its result is recorded.
