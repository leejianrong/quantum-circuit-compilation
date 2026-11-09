# Verifiable Quantum Circuit Compilation: Slices

Two epics, run in parallel. **Epic A (Compile)** is V1-V6; **Epic B (Learn)** is L1-L4. Within Epic A
each slice ends in a demonstrable leaderboard or ledger result. V1 confronts the riskiest unknowns
(local kickmix, DQI memory/time, the submission path) and hits the 2026-11-20 milestone.

# Epic A: Compile

## V1: Baseline on the board (by 2026-11-17, scored entry before 11-20)

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

## V2: invsqrt (fusion) beats baseline

**Delivers:** R0, R1, R3

**Build plan**

1. Study the reference (`nr_reference_circuit.py`): Newton-Raphson initial guess, iteration count,
   fixed-point widths, error bound 2^-24.
2. Write a parameterised generator `src/invsqrt/` (initial-guess table or polynomial, bit widths, number of
   iterations, uncomputation by MBUC).
3. Search the parameter space with an unattended script, using reduced-shot verify, then full-shot
   verify under 10 salts for promotion.
4. `bench promote`, pack, submit.

**Demo:** ledger shows invsqrt cost reduced by x% with margin >= policy; leaderboard score rises.

**Rests on assumptions:** Q10. If local kickmix fails, inner loop moves to Kaggle.

### Test plan

#### End-to-end

- Packed submission with the new invsqrt scores > the previous submission on Kaggle.
- Official verifier passes at 10 distinct salts with 0 failures.

#### Integration

- Generator output verifies identically as `.kmx` and `.kmb`.

#### Unit

- Fixed-point reference model matches the ideal 1/sqrt(x) within 2^-24 on the whole domain
  (n_p = 10, exhaustively).

## V3: dfthcsos (chemistry) first improvement

**Delivers:** R0, R1, R3

**Build plan**

1. Read `SCORING_README.md` and `verify.py`; model the cost `lambda_eff * T_total * Q_total` and gates
   (`Lambda > 49.0`, `E_gap > 3.914898`).
2. Start with the cheap levers: QROM batching/ADDRESS layout and angle bit-width `brot`, tree shape
   (path vs log-depth), reusing the baseline factorization.
3. Then the deep lever: re-factorize (R, B, C) trading accuracy against QROM data size; accept only
   with margin on the accuracy gates.
4. Promote and submit.

**Demo:** ledger shows a lower dfthcsos score with gate margins recorded.

### Test plan

#### End-to-end

- Packed submission with new dfthcsos scores higher on Kaggle; official verify passes at 10 salts.

#### Integration

- Circuits' loaded angle words decode on the submitted `tree_edges` to unit vectors within tolerance.

#### Unit

- Our cost model reproduces the verifier's `resource_costs` for the baseline.

## V4: DQI first improvement

**Delivers:** R0, R1, R3, R6

**Build plan**

1. Read `dqi_reference_circuit.py` and the DQI verifier; understand the syndrome decoder
   (extended Euclid or equivalent, MBUC).
2. Identify the dominant Toffoli consumers and the allowed approximation (decoding failure rate in
   the score).
3. Build smaller-scale instances (small field) for fast iteration; then full RS(4095,4025).
4. Promote after full-scale verification on Kaggle/RunPod (ADR-0002).

**Demo:** ledger shows a DQI cost reduction with a measured failure rate within the score model.

**Rests on assumptions:** Q16 (circuit sizes drop), ADR-0002 memory measurement.

### Test plan

#### End-to-end

- Full-size DQI verification on the chosen executor passes; Kaggle score rises on submission.

#### Integration

- Small-field instance passes the same verifier code path as the full instance.

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
