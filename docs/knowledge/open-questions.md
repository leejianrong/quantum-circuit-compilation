# Open questions

What we do not yet know. Owner decisions are marked; the rest are experiments waiting for someone to run them.
When one is answered, write a log entry and move it to the [claims register](claims.md).

## Owner decisions

* (invsqrt: answered 2026-11-19, one sandboxed container build approved and done, see the [log](../log/entries/2026-11-19-invsqrt-reference-build.md); dfthcsos still open.) May the Apache-2.0 builders of syed3000 be run to regenerate their circuits? [HANDOFF](../HANDOFF.md) lists this as
  open because the permission classifier blocks it. The DQI builder has since been reproduced byte for byte inside a
  sandboxed container ([stage ledgers](../log/entries/2026-11-15-dqi-stage-ledgers.md)); confirm the policy for the
  invsqrt and dfthcsos builders.
* Is a GPU run of the dfthcsos fit with a `Lambda` penalty from the start worth the quota?
* (v17 invsqrt container build: approved and done 2026-11-21, see the [log](../log/entries/2026-11-21-invsqrt-v17-reference-build.md). The v17 `dqi_generator` is read ([log](../log/entries/2026-11-22-dqi-v17-generator-reading.md)); building its `paired-plain` profile (0.085% better, 13 minutes, 5.5 GB) needs the owner's approval; the `dfthcsos_generator` is unread and a build needs its own approval.)
* Which licensed portfolio is submitted? Nothing is promoted or submitted without the owner
  ([PROVENANCE](../PROVENANCE.md), licence column).

## Experiments not yet run

| Question | Why it matters | Source |
|---|---|---|
| What rounding gets the penalised words to 8 bits inside the `error_2` gate (QAT gives 0.099), and what loader structure does the public table use to reach 4,040 Toffolis per loader pass? | the remaining 3.5x of the dfthcsos gap is `T_total * Q_total`, not `lambda_eff` | [S4 stage 3](../log/entries/2026-11-19-spike-s4-stage3-own-3x.md) |
| Does the consuming multiplier work as the builder source suggests (ten signed-digit rows into a 16-wire word)? We have not re-checked or built it | the invsqrt 46-qubit lead | [invsqrt syed decode](../log/entries/2026-11-15-invsqrt-syed-decode.md) |
| Which single module of his extractor bundle (nested-norm arithmetic, retained-norm return) gives the -114 T per node? The bundle is shown to; modules are not isolated | 62% of the DQI gap | [stage ledgers](../log/entries/2026-11-15-dqi-stage-ledgers.md) |
| (closed 2026-11-19, obsolete) Does an in-place Euclid history exist for the reciprocal scan? The frontier scans at 11 T per position, the reciprocal scan needs 23 | none | [S6](../experiments/spike-s6-euclid-history.md) |
| Which algorithm needs no data-dependent word swap in the DQI outer (the public 70.04x circuit has no `CSWAP`; its conditioning is otherwise the same as ours, so the 12,384 unconditioned `CSWAP`s are 79% of the gap)? | closes the DQI gap to the public frontier (about 4%); a design question, not a port | [70x study](../experiments/dqi-70x-study.md) |

## Data to reconcile

* The invsqrt frontier's rotation count differs across the notes (43, 42 and 45); the
  [generator entry](../log/entries/2026-11-12-invsqrt-generator.md) flags it.
* Some notes label experiments with ids that do not match `ledger/experiments.jsonl` (for example E002 to E008 in
  the dfthcsos notes are dqi and invsqrt experiments there, and E041 is not in the ledger at all). The entries list
  only ids that match; the notes themselves are left as written.
* E040 is still open in the ledger although its result is recorded.
