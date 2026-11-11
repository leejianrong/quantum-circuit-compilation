# ADR-0008: Ledger v2, worst-salt ranking, and an in-repo indah dashboard

- Status: Accepted
- Date: 2026-11-12
- Deciders: Jian (D1 to D4)

## Context

Ledger schema 1 has no timestamp, experiment link or circuit structure, so it cannot draw progress
over time or show where cost goes. We also want to show the optimisation process, not only results.

## Decision

1. Extend the ledger by appending schema 2 rows; schema 1 rows stay valid (D1).
2. Build the dashboard in this repo under `dashboard/`, with indah from PyPI as an optional extra (D2).
3. Run it locally first; commit static plots to the README and site; no public hosting until we have
   our own results, since the lineage view shows third-party circuits (D3).
4. Rank and promote on the worst-salt ratio, not the mean (D4).

## Alternatives considered

| Option | Why not |
|---|---|
| New ledger file or database | Breaks the append-only, diffable ledger (ADR-0001) for no gain |
| Dashboard inside the indah repo | Couples competition code to a framework repo |
| Rank on the mean over salts | Hides the salt that would reject a submission |

## Consequences

Plots and the dashboard depend on kickmix statistics, so tests use small fixture circuits. See
`docs/MEASUREMENT.md`.
