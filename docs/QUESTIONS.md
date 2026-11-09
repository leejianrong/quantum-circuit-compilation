# Questions

Statuses: `DECIDED` (user answered) · `ASSUMED` (default taken, correct it if wrong) · `FORK`
(waiting on the user) · `DEFERRED` (not needed this milestone).

## Open forks

None. Round 1 closed.

## Register

| ID | Question | Status | Answer or default | Landed |
|----|----------|--------|-------------------|--------|
| Q1 | Where do heavy DQI runs happen? | DECIDED | Kaggle notebook first, RunPod fallback; RAM measured in V1 | ADR-0002 |
| Q2 | Margin on approximations? | DECIDED | Official verifier, 10 salts at full shots, measured margins | ADR-0001 |
| Q3 | Order of attack / task prizes? | DECIDED | Hybrid, invsqrt first, per-task prizes, ratcheted | ADR-0003 |
| Q4 | Agent harness? | DECIDED | Harness (`bench`) only, no orchestrator | ADR-0005 |
| Q5 | Time budget? | DECIDED | Ignore; be ambitious; DQI and dfthcsos deep slices in | PLAN §Scope |
| Q6 | Public repo? | DECIDED | Public, Apache-2.0 | ADR-0004 |
| Q7 | 11/20 milestone? | DECIDED | Only a working, non-zero entry | SLICES V1 |
| Q8 | Learning material? | DECIDED | Epic B, markdown plus Zensical site | ADR-0006 |
| Q9 | Which benchmarks must be in every submission? | ASSUMED | All three (metric requires it) | ADR-0003 |
| Q10 | Can kickmix run locally? | ASSUMED | Yes via Qualtran or the `.so`; unchecked: execution of the downloaded `.so` was blocked, needs Jian's OK | PLAN, V1 |
| Q11 | Do the rules allow a public repo and notebook? | ASSUMED | Yes; rules unread | V1 step 1 |
| Q12 | Submission is a file upload? | ASSUMED | Yes, per metric docstring | V1 step 6 |
| Q13 | Is the daily cap non-binding? | ASSUMED | Yes at about 1 per day | PLAN |
| Q14 | Ledger format? | ASSUMED | JSONL | PLAN §Shape S2 |
| Q15 | LLM API spend? | ASSUMED | None | ADR-0005 |
| Q16 | Optimised DQI circuits are smaller than baseline? | ASSUMED | Yes | PLAN, V4 |
| Q17 | Python tooling? | ASSUMED | uv, Python 3.12/3.13, pytest, ruff | PLAN §Implementation |
| Q18 | Does Longest Leader matter? | DEFERRED | Decide after V2 shows the competitive position; public by 2027-01-04 | V6 |

## Coverage

| Category | Covered by |
|----------|-----------|
| Primary user and actors | PLAN §Users, Q4 |
| Scope boundary | PLAN §Scope, Q5, Q7 |
| Data model and identity | Ledger row (circuit sha256 + git sha), S2 |
| State and storage | Q14, S3 `best/` store |
| Concurrency and conflict | Parallel worktrees; `best/` promoted only through `bench promote` (ADR-0003) |
| Interfaces and contracts | PLAN §Affordances; verifier modules as the contract |
| Failure behaviour | ADR-0001; V1 corrupted-circuit test |
| External dependencies | Q10, Q11; kickmix and verifiers are Apache-2.0 (LICENSE.txt in the data); Kaggle CLI |
| Runtime and deployment | ADR-0002, Q1 |
| Measurable success | R2 (score > 0 before 11/20), per-slice demos, leaderboard score |
| Security and secrets | ADR-0004 (no `data/`, no Kaggle token in the repo); never log `credentials.json` |
| Versioning and migration | Ledger is append-only JSONL with a `schema` field; verifiers pinned by commit in the data |
