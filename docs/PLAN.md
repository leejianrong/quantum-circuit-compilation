# Verifiable Quantum Circuit Compilation: Plan

Status: agreed (round 1 closed) · Milestone: full competition, deadline 2027-01-20 23:59 UTC

## Problem

Google Quantum AI's Kaggle competition asks for cheaper compilations of three fault-tolerant
subroutines written as *kickmix* circuits (reversible classical logic, phase gates, measurement-based
uncomputation): `invsqrt` (fusion, 1/sqrt(x) phasing), `dqi` (Reed-Solomon syndrome decoder for
Decoded Quantum Interferometry) and `dfthcsos` (FeMoCo Hamiltonian block encoding: factorization,
Givens tree, QROM angle-loading circuits). Each benchmark's verifier fuzz-tests the circuit and
returns a cost. The leaderboard score is the geometric mean of `baseline_cost / cost` over the three,
so every benchmark must be present and valid in every submission, and a single failed hidden-seed test
rejects the whole submission.

The owner (Jian) is a Python engineer with undergraduate engineering maths and no quantum background.
The second problem is therefore knowledge: nobody on this project can currently read a kickmix
circuit and say why it is expensive.

## Solution

Two tracks that share a repo.

- **Track A, Compile:** a local/Kaggle verification harness (`bench`) that builds a candidate
  submission, verifies it with the official verifiers plus our own stricter multi-seed fuzz, and logs
  cost and safety margin to a ledger. On top of it, one optimisation workstream per benchmark, driven
  by Claude Code sessions as the coding agent, climbing the leaderboard through ratcheted,
  always-valid submissions.
- **Track B, Learn:** a Zensical docs site (plus plain markdown that renders on GitHub) that takes a
  Python-literate newcomer to the knowledge needed to work on this competition, with runnable examples.

Starting point (ADR-0007): a verified portfolio of the best public circuits (about 25x), then our own
improvements where others have not looked. Prize targets: top-6 leaderboard (overall), the three $10k single-task prizes (invsqrt, dqi,
dfthcsos each), Longest Leader, and, on a "get on the board" basis only, the 2026-11-20 milestone.

## Users and actors

1. Jian (human, owner): reads results, decides what to submit, reads the learning material.
2. Claude Code sessions (agent): write circuit generators and optimisers, run the harness. When
   they disagree with the ledger, the ledger (official verifier output) wins.
3. The Kaggle verifier (external judge) always wins over local checks.
4. Future newcomers reading the public repo and docs site (secondary).

## Scope

**In.**
- Valid submission of all three benchmarks, resubmitted at every improvement.
- Harness, ledger, submission packager, reproducibility notebook.
- Deep optimisation for all three benchmarks, including accuracy-bounded approximations.
- Learning track: markdown curriculum and a Zensical site, published via GitHub Pages.
- Public Apache-2.0 GitHub repo and a public Kaggle notebook that reproduces the best submission.

**Out.**
- Real quantum hardware or non-kickmix circuits (not scoreable).
- Training ML models on data (no dataset exists; "agents" means coding agents).
- A custom multi-agent orchestration layer (ADR-0005 explains why).
- Guaranteeing the 11/20 milestone prize; we aim for about 25 (R9) but the board is crowded.

## Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| R0 | Maximise the Kaggle score: geometric mean of baseline/cost over the three benchmarks | Core goal |
| R1 | Every submission passes the official verifier; margin on approximations is measured, not guessed | Must-have |
| R2 | A scored (non-zero) entry exists on the leaderboard before 2026-11-20 23:59 UTC | Must-have (R9 raises the target) |
| R3 | Each benchmark has an independent improvement workstream and its own cost history | Must-have |
| R4 | The best submission is reproducible from the public repo/notebook (prize eligibility) | Must-have |
| R5 | A newcomer with Python plus undergrad maths can follow the learning track to the point of reading a kickmix circuit and the three benchmark specs | Must-have |
| R6 | DQI full-size verification is runnable within the memory budget in ADR-0002 | Must-have |
| R7 | Repo is public, Apache-2.0, contains no competition-restricted data (see Open risks) | Must-have |
| R8 | Every circuit we submit has a provenance row (author, source, licence, hash, cost); verbatim third-party files are replaced or licence-cleared before Final Submissions | Must-have |
| R9 | A scored entry near the public frontier (about 25) exists before 2026-11-20 | Must-have |

## Shape

| Part | Mechanism | ADR |
|------|-----------|-----|
| S1 | `bench` CLI: `build <bench>` -> `verify <bench> --seeds N` -> `pack` -> `ledger add`. Wraps the official verifiers' Python entry points with salts of our choosing | 0001 |
| S2 | Ledger: append-only `ledger/results.jsonl`, one row per candidate (bench, git sha, circuit sha256, official cost, shots, seeds, failures, margin, wall time, host) | 0001 |
| S3 | Best-known-good store: `best/{invsqrt,dqi,dfthcsos}/` promoted only when verified; `bench pack` always assembles the archive from there, so a submission is never partial | 0003 |
| S4 | Heavy-run executor: Kaggle notebook as primary for DQI full verification, RunPod high-RAM pod as fallback; memory measured once and recorded | 0002 |
| S5 | Per-benchmark generators in `src/<bench>/` that emit `.kmx/.kmb` from parameters (so the search space is parameters, not hand-edited files) | 0003 |
| S6 | Public reproducibility notebook that rebuilds `best/` and reruns the verifier | 0004 |
| S8 | Provenance log `docs/PROVENANCE.md` and a public-circuit fetcher (`scripts/fetch_public.sh`) that downloads and hashes circuits from public datasets | 0007 |
| S7 | Docs: `docs/learn/*.md` with a Zensical site, deployed from CI | 0006 |

## Affordances

**Non-UI.**

| Affordance | Kind | Wires to |
|------------|------|----------|
| `bench build/verify/pack` | CLI | official `verifiers/`, `kickmix`, `best/` |
| `bench ledger show --bench X` | CLI | `ledger/results.jsonl` |
| `bench promote <candidate>` | CLI | gate: official PASS and margin check, then copy to `best/` |
| `notebooks/reproduce.ipynb` | Kaggle notebook | `best/`, verifiers |
| `docs/learn/` site | Zensical + GitHub Pages | CI |

## Implementation decisions

- Python 3.12 or 3.13 via `uv`; verifiers and `kickmix` from competition data are vendored under
  `data/` (gitignored, large and licence-governed), never committed. Local import of `kickmix.so` has
  not been tested: its build target is Kaggle's image. Slice V1 resolves this (try `pip install
  qualtran` first, then the `.so`, then Kaggle-only fallback).
- The harness imports each verifier module, not subprocesses, so it can pass our own salts and shot
  counts. `verification_shot_divisor`-style weakening is for fast inner-loop checks only; ledger rows
  record the shots used and `promote` requires full-strength runs.
- Fiat-Shamir seeding means seed = hash(circuit, salt). To measure margin we run K different salts
  (K >= 10 at full shots for final candidates). A candidate is promotable only with 0 failures across
  all salts and, for approximate designs, an empirical failure rate and accuracy-gate margin
  recorded in the ledger (ADR-0001).
- Generators build circuits with kickmix's `CircuitBuilder` (via Qualtran). Text `.kmx` is used
  for review and diffing, `.kmb` for large circuits.
- Learning material is written alongside the work; runnable snippets in it are executed in CI so the
  tutorial cannot rot.

## Testing approach

Seams: (1) the official verifier is the oracle, which is the highest seam and the acceptance test of
every slice; (2) the harness itself gets unit tests on packaging and ledger logic only (small
fixtures, not the real verifiers); (3) docs snippets are executed. We do not test circuit
internals, only behaviour under the verifier. Quality gates per `dev-playbook`.

## Assumed defaults

| ID | Assumed | Cost if wrong |
|----|---------|---------------|
| Q10 | `kickmix` can be made to import locally (via Qualtran or the `.so`) | All local work moves to Kaggle notebooks; slower iteration |
| Q11 | Competition rules permit a public Apache-2.0 repo of our own code and a public notebook | Repo goes private/partially redacted; rules must be read in V1 |
| Q12 | Submissions are file uploads of the archive (per metric docstring), not code-notebook submissions | The packaging path changes in V1; notebook becomes primary |
| Q13 | Daily submission cap is not binding at about 1/day cadence | Fewer, more carefully margin-checked submissions |
| Q14 | Ledger as JSONL (diffable, greppable), not a database | Trivial migration |
| Q15 | No LLM API spend; Claude Code sessions are the agent | n/a |
| Q19 | Public circuits are legitimately reusable as a starting point (rules C.5.d) and licences can be cleared or replaced before finals | A circuit must be rewritten or dropped late; the generators from ADR-0007 are the mitigation |
| Q20 | The notebook-reported scores (about 25) are real | Entry target is lower; the portfolio card (QCC-35) measures it |
| Q16 | DQI optimised circuits are smaller than the 886 MB baseline, so memory shrinks as we win | RAM estimate in ADR-0002 is worst case, so cost is low |

## Open risks

- `kickmix` locality (Q10): found in V1.
- Public repo vs rules/competitor advantage (Q11): rules read in V1; publication timing is Jian's call
  before 2027-01-04 for Longest Leader.
- Approximation margin: hidden-seed failure wastes a slot and invalidates the day. Mitigated by
  ADR-0001 but never eliminated.
- DQI iteration speed: baseline verification may take hours; first measurement in V1.
- Knowledge gap: optimisation ideas may stall without understanding. Track B is deliberately early.
