# ADR-0004: Public Apache-2.0 repository and a public reproducibility notebook

- Status: Accepted
- Date: 2026-11-10
- Deciders: Jian (F6, F6 revised)

## Context

Prize eligibility (Milestone, Longest Leader, and the winning submission) requires public notebooks
and datasets plus reproducibility, licensing and documentation. Jian is fine publishing. kickmix
and the verifiers are Apache-2.0 (LICENSE.txt in the data), and the rules (now read, see Decision)
(Q11).

## Decision

Repo is public from the start under Apache-2.0. Competition data (`data/`) is gitignored, not
redistributed, and fetched by script. A Kaggle notebook rebuilds the best submission from the repo
and reruns the verifier. For the milestone it is published as soon as it produces a scored entry.
Rules were read (docs/COMPETITION_RULES.md) and do not forbid this. Constraints they add:
- Share publicly with all Participants: post a link on the competition forums alongside the repo and
  notebook (C.5.d). No private sharing outside our Team.
- Never commit or redistribute Competition Data (B.4.b), including the baseline circuits and the FCIDUMP.
- Anything reused from other competitors must be Apache-2.0-compatible, and our own work original
  (C.14.a, B.7.b). Winners license the submission and its generating source code under Apache 2.0 (B.5.a).

## Alternatives considered

| Option | Why not |
|--------|---------|
| Private until January | Forfeits the milestone and Longest Leader eligibility |

## Consequences

Competitors see the method as it improves; this is accepted. Do not commit `data/`, tokens or
`~/.kaggle/credentials`.
