# ADR-0001: Every candidate is scored by the official verifier and promoted only with a multi-seed margin

- Status: Accepted
- Date: 2026-11-10
- Deciders: Jian (F2)

## Context

The Kaggle metric runs each verifier under secret per-split salts. The verifiers seed their random
tests from hash(circuit, salt). Any failed test rejects the whole submission, and submissions are
rate-limited. Approximations within accuracy bounds are where most of the score headroom lies, and
also where a hidden-seed failure is most likely.

## Decision

- The harness calls the competition's own verifier modules and logs their `score` as cost.
- Final candidates are verified at full official shot counts under at least 10 distinct salts.
  Zero failures are required across all of them, and accuracy-gated quantities (e.g. dfthcsos
  `Lambda > 49.0`, `E_gap > 3.914898`, DQI failure probability) must clear their bound with a
  recorded margin.
- Reduced-shot verification is allowed for the inner optimisation loop only and is flagged in the
  ledger; it never gates promotion.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Verify once with the official shots, submit | One unlucky hidden-seed failure wastes a slot and gives zero information |
| Re-implement our own checker | Drift from the official one; the official one is already open |
| Maximise approximation to the exact bound | Gains a few percent, risks rejection |

## Consequences

Slower promotion (10x verifier time, notably for DQI); fewer surprises. The margin policy is a
tunable number, recorded per ledger row.
