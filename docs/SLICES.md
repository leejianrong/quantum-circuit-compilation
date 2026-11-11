# Verifiable Quantum Circuit Compilation: Slices

Two epics, run in parallel. **Epic A (Compile)** is V1-V6; **Epic B (Learn)** is L1-L4. Within Epic A
each slice ends in a demonstrable leaderboard or ledger result. V1 confronts the riskiest unknowns
(local kickmix, DQI memory/time, the submission path) and hits the 2026-11-20 milestone.

# Epic A: Compile

## V1: Pipeline proven on the baseline (by 2026-11-14)

**Delivers:** R0 (baseline 1.0), R1, R2, R4 (partial), R6 (measurement), R7

**Build plan**

1. Read the competition rules (sharing, submission format, daily cap, notebook requirement for the
   milestone). Record answers in QUESTIONS.md (Q11-Q13).
2. Create the public repo: Apache-2.0, `.gitignore` for `data/`, `uv` project, `CLAUDE.md`. Add a
   `scripts/fetch_data.sh` that pulls the competition files with the Kaggle CLI.
3. Resolve kickmix locality (Q10): try `uv pip install qualtran` (kickmix source), else load
   `kickmix.so` locally (needs Jian's OK to execute the downloaded binary; sandbox it), else
   fall back to Kaggle notebooks for all verification.
4. `bench verify invsqrt` on the sample circuit; then `dfthcsos`. Record cost, shots and seeds.
5. Run baseline DQI verification on Kaggle; record peak RSS and wall time (settles ADR-0002).
6. `bench pack` the sample submission into an archive; upload to Kaggle; confirm a score of about 1.0.
7. Publish a Kaggle notebook that unpacks and verifies the baseline, with datasets public, for
   milestone eligibility (only if rules require it).

**Demo:** the Kaggle leaderboard shows our team with a score near 1.0; `bench ledger show` lists baseline
costs for all three benchmarks.

**Rests on assumptions:** Q10, Q11, Q12, Q13 (see PLAN). Q12 wrong, meaning submission is by notebook,
changes step 6 only.

### Test plan

#### End-to-end

- Uploading the packed archive yields a non-zero public score between 0.95 and 1.05 on Kaggle.
- `bench verify` baseline costs per benchmark match the metric's `baseline_cost` within verifier noise.
- Peak RSS and wall time for baseline DQI verification are recorded in the ledger.

#### Integration

- `bench pack` output unpacked by the metric's `find_one` rules finds exactly one of each required file.
- A deliberately corrupted circuit makes `bench verify` fail with a ledger row marked FAIL, not a crash.

#### Unit

- Ledger append and parse round-trip; circuit sha256 stable across runs.
- Packager refuses to assemble when any `best/<bench>` is missing.

## V1b: Public-circuit portfolio on the board (target: about 25 before 2026-11-20)

**Delivers:** R0, R1, R2, R8, R9 (ADR-0007)

**Build plan**

1. Fetch the public circuits the notebooks point to (Kaggle datasets and notebook outputs) with
   `scripts/fetch_public.sh`; hash them; write `docs/PROVENANCE.md` (author, source, stated licence, cost).
2. Verify every candidate per benchmark with `bench verify` at several salts; log failures (DQI
   hidden-seed risk).
3. Assemble the best verified candidate per benchmark into `best/`, and pack.
4. Submit; confirm the board score is near the notebook-reported value; publish the notebook with
   attribution and a forum link.

**Demo:** the leaderboard shows a score near 25 and `docs/PROVENANCE.md` lists every circuit used.

**Rests on assumptions:** Q19, Q20 (see PLAN). If the public scores are not reproducible, the slice reports
the real number and the plan re-centres on that.

### Test plan

#### End-to-end

- Board score is within 2% of the score the portfolio gets from our own full-shot verification.
- Every file in the submitted archive has a provenance row.

#### Integration

- The same circuit verified at 5 distinct salts yields 0 failures or is excluded from `best/`.

#### Unit

- Provenance check script fails if any `best/` file lacks a row.

## V2: invsqrt (fusion): audit and squeeze the public design

Expect small gains. Public work claims 62 qubits and about 1.5% per remaining qubit, so this slice is
about verifying that claim and testing whether anyone has missed a structural change.

**Delivers:** R0, R1, R3, R8

**Build plan**

1. Model the cost (qubits x (Toffolis + T/4)) and break the public circuit down by stage.
2. Write our own parameterised generator for the table plus quadratic (Horner) design, reproducing
   the public cost at the public parameters.
3. Probe unexplored directions: different segment counts or polynomial degrees, tolerance use
   (the best circuit is reported at about 0.945 of the error tolerance), alternative normalisation,
   and shared carry/borrow tricks. Search with reduced-shot verify; promote with the full gate.

**Demo:** ledger shows an invsqrt cost at or below the public best, from our own generator, with 0
failures across 10 salts.

### Test plan

#### End-to-end

- Packed submission with our own invsqrt scores at least as well on Kaggle as the public circuit.
- Official verifier passes at 10 distinct salts.

#### Integration

- Generator output verifies identically as `.kmx` and `.kmb`.

#### Unit

- Fixed-point model matches the ideal 1/sqrt(x) within 2^-24 over the whole domain (n_p = 10).

## V3: dfthcsos (chemistry): attack the 7-bit cliff and the factorization

Highest expected gain per effort: the lowest ratio so far (about 11x) and an open lever.

**Delivers:** R0, R1, R3, R8

**Build plan**

1. Model `lambda_eff * T_total * Q_total` and the gates (`Lambda > 49.0`, `E_gap > 3.914898`, error2 gate)
   from the verifier; reproduce the public cost.
2. Attack the cost-model cliff at `brot` <= 7 (temporary qubits roughly halve; reported 7-bit
   quantization-aware training plateaus near error2 0.11 against a 0.02 gate).
3. Search factorization shapes (R, B, C) beyond the public 8 x 143 x 44 and the loader count.
4. Hypotheses (ours, unverified): mixed bit-widths per factor or per angle word; error-aware
   rounding that targets the energy gate rather than angle error.
5. Promote only with measured gate margins.

**Demo:** ledger shows a lower dfthcsos cost with gate margins recorded, from our own pipeline.

### Test plan

#### End-to-end

- Packed submission with the new dfthcsos scores higher on Kaggle; official verify passes at 10 salts.

#### Integration

- Loaded angle words decode on the submitted `tree_edges` to unit vectors within tolerance.

#### Unit

- Our cost model reproduces the verifier's `resource_costs` for the public circuit.

## V4: DQI: cut qubits and the Forney/BM stages, and quantify hidden-seed risk

Largest circuit and most levers. Public circuits use a Berlekamp-Massey / Schur decoder; reported
breakdown: BM forward pass about 25% of Toffolis, Forney sweep about 56%, one 42-AND GF(2^12)
multiplier throughout. Qubits count twice in the cost.

**Delivers:** R0, R1, R3, R6, R8

**Build plan**

1. Reproduce the public breakdown; build small-field instances for fast iteration.
2. Quantify hidden-seed failure risk of each candidate: failures per salt, and behaviour at the known
   hard error weights; choose the safest circuit, not just the cheapest.
3. Look for new levers: qubit reuse and borrowing, restructuring the Forney sweep, cheaper
   multiplier or constant-multiplier structure, approximations priced into the repetition factor.
4. Full-size verification on the chosen executor (ADR-0002) before promotion.

**Demo:** ledger shows a lower DQI cost, a measured failure rate per salt, and a risk table of
candidates.

**Rests on assumptions:** Q16, ADR-0002 memory measurement.

### Test plan

#### End-to-end

- Full-size DQI verification passes at 10 salts; Kaggle score rises on submission.

#### Integration

- Small-field instance runs through the same verifier code path as the full instance.

#### Unit

- GF(2^12) arithmetic helpers match a reference implementation on random inputs.

## V5: Deep optimisation to task-prize level

**Delivers:** R0 (stretch), the three $10k single-task goals

**Build plan**

1. Per benchmark, run iterated improvement cycles (generate -> verify -> ledger) with Claude Code
   sessions in parallel worktrees, tracking the leaderboard-implied cost.
2. Approximation tuning against accuracy bounds per ADR-0001.
3. Weekly: read new public notebooks, adopt ideas (licence permitting), resubmit.

**Demo:** per-benchmark cost trend charts from the ledger; leaderboard position.

### Test plan

#### End-to-end

- Each promoted candidate passes the 10-salt full-shot check; no Kaggle submission is rejected.

#### Integration

- `bench promote` blocks a candidate with a single failure or insufficient margin.

#### Unit

- Margin calculation yields the expected result on synthetic ledger rows.

## V6: Final: reproducibility and handover (before 2027-01-04, final by 2027-01-20)

**Delivers:** R4, R7, Longest Leader eligibility

**Build plan**

1. `notebooks/reproduce.ipynb` rebuilds `best/` from the repo and verifies it on Kaggle.
2. Make notebook and datasets public by 2027-01-04; keep public to the deadline.
3. Write a technical write-up; choose the final submissions.

**Demo:** a fresh Kaggle session runs the notebook end to end and prints the same costs as the ledger.

### Test plan

#### End-to-end

- A clean-room run of the notebook reproduces the final archive hash (or equivalent costs under a fresh
  salt).

#### Integration

- Repo checkout with no `data/` can regenerate it through `scripts/fetch_data.sh`.

#### Unit

- n/a

# Epic B: Learn (independent of Epic A; runs in parallel)

Audience: Python-literate, undergrad engineering maths, no quantum background. Each page ends with a
runnable example and 2-3 exercises. Content lives in `docs/learn/`.

## L1: Quantum computing in the abstract that matters here

**Delivers:** R5 (partial)

**Build plan**

1. Pages: bits vs qubits, amplitudes and complex numbers, superposition, gates as unitary matrices,
   interference, measurement. Numpy snippets simulate 1-3 qubits.
2. Pages: reversible logic, NOT/CNOT/Toffoli, ancillas and uncomputation, phase gates and phase kickback.
3. Docs scaffold: Zensical site builds locally with `uv run zensical build`; CI runs the snippets.

**Demo:** the site serves locally and all page snippets pass in CI.

### Test plan

#### End-to-end

- A reader who has never studied quantum mechanics can follow L1 from page 1 to the exercises; Jian
  reviews and flags every unexplained term.

#### Integration

- CI builds the site and executes every code block.

#### Unit

- Snippet helpers (tiny state-vector simulator) pass reference cases (Bell state, Toffoli truth table).

## L2: Costs and kickmix

**Delivers:** R5 (partial)

**Build plan**

1. Pages: why Toffoli count and logical qubits are the cost; MBUC explained with a worked AND-gate
   example; why classical simulation verifies kickmix circuits (linearity, phase tracking, the 2*sqrt(eps)
   bound; Fiat-Shamir seeding).
2. Pages: kickmix instruction set, `.kmx` format and the Python builder; build and verify a tiny
   adder, then a tiny circuit with MBUC.
3. A glossary page.

**Demo:** the reader builds a 4-bit adder in kickmix and sees the verifier pass, then breaks it and
sees the verifier fail.

**Rests on:** V1 step 3 (kickmix runnable); until then L2's code samples are marked pending.

### Test plan

#### End-to-end

- Following the page, a new reader builds and verifies the tiny circuit in under 30 minutes.

#### Integration

- The tiny-circuit examples run under the repo's pinned kickmix.

#### Unit

- Glossary: every term used in L1-L2 appears.

## L3: The three benchmark primers

**Delivers:** R5

**Build plan**

1. invsqrt: fixed-point arithmetic, Newton-Raphson, the Quake trick, error budgets, phasing, why n_p = 10.
2. DQI: finite fields GF(2^m), Reed-Solomon codes, syndromes, decoding failure vs repetition overhead,
   OPI problem.
3. dfthcsos: Hamiltonians in one paragraph, tensor factorization (SVD intuition), Givens rotations,
   QROM, block-encoding cost model, the score formula.
4. For each: a "what the reference circuit does and where its cost goes" walkthrough with real numbers
   from the ledger.

**Demo:** for each benchmark, the reader can state the cost drivers and name two candidate
optimisation levers.

### Test plan

#### End-to-end

- Jian can explain each benchmark's cost drivers unaided after reading its primer (self-check
  questions in each page).

#### Integration

- Numbers quoted in the primers equal current ledger rows (a check script).

#### Unit

- GF(2^12) and fixed-point demo code matches reference implementations.

## L4: Publish the site

**Delivers:** R5, R7

**Build plan**

1. Zensical config, navigation, and a "start here" page with the reading order.
2. GitHub Pages deployment from CI; link from the README.
3. Refresh with insights from Epic A (what actually worked and why).

**Demo:** public URL serves the learning site; README links to it.

### Test plan

#### End-to-end

- The deployed site is reachable and every internal link resolves.

#### Integration

- CI fails if a code block or link breaks.

#### Unit

- n/a

# Epic C: Measure and showcase

Plan: `docs/MEASUREMENT.md`; decisions: ADR-0008. Cards QCC-39 to QCC-48.

| Slice | Card | Demo |
|---|---|---|
| C1 Ledger v2 with circuit statistics | QCC-39 | `bench verify` writes a schema 2 row with Toffolis and qubits |
| C2 Experiment log | QCC-40 | open, verify against and close an experiment |
| C3 Backfill and leaderboard rows | QCC-41 | ledger holds the 2026-11-11 portfolio, public references and Kaggle score |
| C4/C5 Plots | QCC-42, QCC-43 | `bench plots` writes six PNGs |
| C6 Dashboard scaffold | QCC-44 | `make dashboard` shows real ledger rows |
| C7 Cost explorer | QCC-45 | sliders reproduce 299.6M and show the 7-bit cliff |
| C8 Anatomy and verifier theatre | QCC-46 | flame chart and salt ticks for a ledger entry |
| C9 Lineage graph | QCC-47 | baseline to public to ours, licence risk visible |
| C10 Docs and README | QCC-48 | site page and README plots |
