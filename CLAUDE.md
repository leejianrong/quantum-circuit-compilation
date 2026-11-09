# Verifiable Quantum Circuit Compilation

Kaggle competition (deadline 2027-01-20): shrink three kickmix circuits (`invsqrt`, `dqi`,
`dfthcsos`). Score = geometric mean of `baseline_cost / cost`; any verifier failure rejects the whole
submission. Start with `docs/COMPETITION.md` (what it is, scoring, benchmarks, prizes) and
`docs/COMPETITION_RULES.md` (legal rules). Plan: `docs/PLAN.md`. Slices: `docs/SLICES.md`. Decisions: `docs/adr/`.
Board: Pandan `QCC` (use the `pandan` skill). Trust the code over the docs; the plan is ahead of the repo.

## Status
`bench verify <invsqrt|dqi|dfthcsos> CIRCUIT --salts N` (src/bench/) logs to `ledger/results.jsonl`. kickmix has not been run
locally yet (QCC-3).

## Commands
- `make install` / `make check` (lint + mypy + fast tests) / `make hooks` (pre-push, run once)
- `make fetch-data` downloads competition data to `data/` (gitignored, about 1.1 GB, never commit it)
- Tests marked `integration` need kickmix and the data; they are skipped by default.

## Rules
- Never submit anything not in `best/` and promoted by `bench promote` (ADR-0001, ADR-0003).
- The official verifier is the oracle. Reduced-shot runs are for inner loops only and must be flagged.
- A bug becomes a test first. Keep tests deterministic.
- Branch per story off fresh `main`, PR-only, CI green before merge. Name branches `qcc-<n>-<slug>`.
- Never commit `data/`, `.mcp.json`, Kaggle credentials or tokens. Don't print tokens.
- Heavy DQI runs go to Kaggle or RunPod (ADR-0002), not this 7 GB laptop.
