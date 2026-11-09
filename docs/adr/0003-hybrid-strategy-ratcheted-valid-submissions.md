# ADR-0003: Hybrid strategy: cheapest ratio gains first, per-task prizes, and a never-partial best-known-good store

- Status: Accepted
- Date: 2026-11-10
- Deciders: Jian (F3, F5: "as optimistic and ambitious as possible")

## Context

Score is the geometric mean of three ratios, so a 2x on any benchmark is worth the same. Three $10k
prizes pay for the best score on a single task; the overall prizes need all three. Each submission
must contain all three benchmarks.

## Decision

- Order: V1 baseline entry -> invsqrt (smallest, fastest verifier, probable single-task prize) ->
  dfthcsos and DQI in parallel workstreams, each aiming at a single-task prize.
- Submissions are assembled only from `best/`, where every bench is a verified candidate, so an
  experiment in one benchmark can never produce a partial or invalid archive.
- Deep optimisation, including approximations, is in scope for all three from the start.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Strictly balanced effort | Ignores that single-task prizes need only one strong benchmark |
| One benchmark only | Overall score and 3 of 3 prizes need all |

## Consequences

Promotion discipline (ADR-0001) carries the safety burden. Parallel workstreams mean three
independent ledgers per benchmark.
