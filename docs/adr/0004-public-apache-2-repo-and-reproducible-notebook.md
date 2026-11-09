# ADR-0004: Public Apache-2.0 repository and a public reproducibility notebook

- Status: Accepted
- Date: 2026-11-10
- Deciders: Jian (F6, F6 revised)

## Context

Prize eligibility (Milestone, Longest Leader, and the winning submission) requires public notebooks
and datasets plus reproducibility, licensing and documentation. Jian is fine publishing. kickmix
and the verifiers are Apache-2.0 (LICENSE.txt in the data), and the competition rules were not read
(Q11).

## Decision

Repo is public from the start under Apache-2.0. Competition data (`data/`) is gitignored, not
redistributed, and fetched by script. A Kaggle notebook rebuilds the best submission from the repo
and reruns the verifier. For the milestone it is published as soon as it produces a scored entry.
Rules are read in V1 and override this ADR if they forbid it.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Private until January | Forfeits the milestone and Longest Leader eligibility |

## Consequences

Competitors see the method as it improves; this is accepted. Do not commit `data/`, tokens or
`~/.kaggle/credentials`.
