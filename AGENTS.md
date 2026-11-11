# Verifiable Quantum Circuit Compilation

## What
Kaggle competition (deadline 2027-01-20 23:59 UTC): shrink three kickmix circuits (`invsqrt`, `dqi`,
`dfthcsos`). Score = geometric mean of `baseline_cost / cost`; any verifier failure rejects the whole
submission. Python 3.12 with uv. Code is in `src/bench/` (harness) and `src/dfthcsos_model/` (cost model, may be
absent until merged). Learning site sources are `docs/learn/`.

Read first: `docs/COMPETITION.md` (scoring, benchmarks, prizes), `docs/COMPETITION_RULES.md`, `docs/PLAN.md`,
`docs/MEASUREMENT.md` (ledger, plots, dashboard), `docs/PROVENANCE.md` (every public circuit we use), `docs/adr/`.
Board: Pandan `QCC`, id 46 (use the `pandan` skill; `pandan board use 46`). Trust the code over the docs.

## How
- `make install` / `make check` (ruff + mypy + fast tests; also the pre-push hook and CI) / `make hooks` (once)
- `make docs` builds the site; every ```python block in `docs/learn/` is executed by tests (` ```python no-run ` skips)
- `make fetch-data` -> `data/` (about 1 GB, gitignored); `bash scripts/fetch_public.sh` -> `public/` (gitignored)
- `QCC_DATA=$PWD/data uv run bench verify <bench> <circuit-or-dfthcsos-dir> --salts N` appends a row to
  `ledger/results.jsonl`. Also `bench pack`, `bench exp`, `bench lb`, and `bench plots` (PNGs in `out/plots/`; needs `uv sync --extra plots`).
- Branch per story off fresh `main`, named `qcc-<n>-<slug>`; PR-only; merge when CI is green (owner's standing
  instruction). Never stack branches. No attribution lines in commits or PRs.

## Rules that are easy to get wrong
- The official verifier is the oracle. Reduced-shot runs (`--shots-divisor`) are screening only and never gate promotion.
- Submit only what is in `best/`, verified at several salts with zero failures. A salt-dependent failure rejects everything.
- `Circuit.to_file(path)` writes text unless `format='kmb'`; a text file named `.kmb` is rejected silently.
- The ledger is append-only: never rewrite old lines. `toffolis` there is a static count, not the official cost.
- Never commit `data/`, `public/`, `best/` (third-party circuits, licences unresolved), `.mcp.json` or tokens.
  Never reformat or edit fetched files; they stay byte-identical.
- Resources (7 GB RAM, 16 cores): `bench verify invsqrt` takes about 5 min per salt on all cores, so run one heavy
  verify at a time. DQI needs 5-9 GB: run it on Kaggle (`notebooks/dqi_verify/`), never here (ADR-0002).
- A bug becomes a test first; tests are deterministic. Tests marked `integration` need kickmix and `data/`.
