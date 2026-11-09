# The competition: what it is and how it's judged

Read this first if you are new to the project (human or agent). The legal rules are in
[COMPETITION_RULES.md](COMPETITION_RULES.md); our plan is in [PLAN.md](PLAN.md). Where this file
and the Kaggle page disagree, Kaggle wins.

- **Name:** Google Quantum AI, Verifiable Quantum Circuit Compilation
- **Page:** https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation
- **Slug (for the CLI):** `google-verifiable-quantum-circuit-compilation`
- **Category / prize pool:** Featured, $150,000
- **Deadline:** 2027-01-20 23:59 UTC. Launched 2026-10-21; about 2,700 teams by 2026-11-10.
- **Companion paper:** Khattar et al., arXiv:2610.23832 (kickmix, verification guarantees, the three
  benchmarks). Also `data/verifiable_circuit_compilation.pdf` after `make fetch-data`.

## The idea in plain terms

Large quantum algorithms will run on error-corrected quantum computers, where every gate is
expensive. The expensive ones are **Toffoli gates** (they set the runtime) and the **logical qubit
count** (it sets the machine size). Shrinking a circuit therefore shrinks the hardware needed.

Experts have shrunk such circuits by hand. This competition crowdsources it. Three costly
subroutines are written as **kickmix circuits**: made only of reversible classical logic (NOT,
CNOT, Toffoli), phase gates, and measurement-based uncomputation. A classical computer can run these
one input at a time, tracking one bit per qubit plus a phase, so each circuit can be checked
automatically on many random inputs. That check is the reward signal for AI coding agents, classical
optimisation and search. No quantum hardware or physics background is needed.

We optimise **quantum circuit designs** (files on disk), using **classical computers** to build and
verify them. Nothing runs on a quantum machine. Some inputs are classical maths that changes the
quantum cost (for example the tensor factorization in `dfthcsos`).

## The score

For each benchmark the verifier returns a **cost** (lower is better). The leaderboard score is the
**geometric mean over the three benchmarks of `baseline_cost / cost`**. The host's reference
submissions score 1.0; halving every cost scores 2.0.

- All three benchmarks must be present in every submission.
- Each verifier simulates the circuit on many tests. **Any failed test rejects the whole
  submission.**
- Tests are seeded from a hash of the circuit file merged with a secret per-split salt, so we cannot
  reproduce the hidden tests. Every edit to a file gives fresh random draws.
- Approximations are allowed inside each benchmark's accuracy bounds. Doing slightly less work is
  part of the game.
- The metric code is the notebook `metric/google-quantum-ai-metric`
  (`kaggle kernels pull metric/google-quantum-ai-metric`). It lists the allowed instructions, the
  file checks (`.kmx` text or `.kmb` binary, qubit/bit ids below 2^30/1536, named registers, only
  regular files) and runs each verifier once per leaderboard split.

## The three benchmarks

| | invsqrt (fusion) | dqi (combinatorial optimisation) | dfthcsos (chemistry) |
|---|---|---|---|
| Science goal | Stopping power of alpha particles in warm dense plasma (inertial confinement fusion) | Decoded Quantum Interferometry on Optimal Polynomial Intersection (verifiable quantum advantage candidate) | FeMoCo, the nitrogenase cluster that fixes nitrogen |
| Algorithm | Trotter simulation of electrons on a grid | DQI | Quantum phase estimation on a block-encoded Hamiltonian |
| Subroutine to shrink | Phase by 1/sqrt(x) for every electron pair (n_p = 10, relative error 2^-24) | Reversible Reed-Solomon syndrome decoder, RS(4095, 4025) over GF(2^12) | Angle-loading QROM circuits, the classical factorization, and the Givens tree |
| What we submit | `invsqrt.kmb` | `dqi.kmb` (baseline is 886 MB) | `dfthcsos/angle_k_0..k_n-1.kmb` plus `submission.npz` (factorization and tree edges) |
| Cost | Toffolis and qubits (see the verifier) | Toffoli x qubit terms, with decoder failures priced into repetition overhead | `lambda_eff * T_total * Q_total`; accuracy gates `Lambda > 49.0` and `E_gap > 3.914898` Ha |
| Baseline reference | `verifiers/invsqrt/nr_reference_circuit.py` (Newton-Raphson) | `verifiers/dqi/dqi_reference_circuit.py` | `verifiers/dfthcsos/` and `example_submission/` |
| Verifier | `verify_submission_invsqrt.py` | `verify_submission_dqi.py`: 102,400 shots (400 batches of 256), up to 4 worker processes | `verify.py`: reads a 128 MB FCIDUMP, about 10 s load |

Parts of each algorithm that are not kickmix circuits (arbitrary state preparation, Givens rotation
gates) are priced by analytical formulas, so they count in the score without us submitting circuits
for them.

## What the hosts gave us

All in the competition data (download with `make fetch-data`; see `scripts/fetch_data.sh`):

- `kickmix/kickmix.so` (simulator, compiled for Kaggle's image; Apache-2.0)
- `verifiers/` for the three benchmarks, plus `dfthcsos/SCORING_README.md`
- `sample_submission/` (the baseline, which scores about 1.0)
- the FeMoCo `.fcidump` and fixed shifts for chemistry
- the companion paper PDF

The files are Apache-2.0 per their LICENSE.txt. Do not commit `data/`.

## Submission format

One archive containing exactly one each of: `invsqrt.kmx|kmb`, `dqi.kmx|kmb`, and a `dfthcsos/`
directory with `angle_k_0 ... angle_k_<n-1>` (each `.kmx` or `.kmb`) and `submission.npz`.

**Pitfall:** `Circuit.to_file(path)` writes the text format unless you pass `format='kmb'`. A text file
named `.kmb` is rejected with no useful message. See the file-format rules in the metric notebook.

## Key rules (full text: [COMPETITION_RULES.md](COMPETITION_RULES.md))

- 5 submissions per day; up to 2 Final Submissions; ranked on the Private Leaderboard only.
- Teams of up to 5. The team merger cap counts total submissions made.
- No private code sharing outside a Team; sharing is fine if available to all Participants (forums).
- Never redistribute the Competition Data. Winners license their submission and its source code under
  Apache 2.0. AI/LLM tools and external data are allowed if public and free for all (or reasonable).
- Timeline dates, the milestone and Longest Leader notebook rules, and the submission format details are on
  the Kaggle Overview tab, not in the Rules.

## Prizes

| Prize | Amount | Condition |
|---|---|---|
| Leaderboard 1st to 6th | $50k / $25k / $10k / $5k / $5k / $5k | Final private leaderboard |
| Mid-Competition Milestone | $10k | Highest public leaderboard score at 2026-11-20 23:59 UTC; needs a public notebook (and its datasets) kept public until the final deadline |
| Longest Leader | $10k | Notebook holds the top spot longest from the start to 2027-01-04; notebooks and datasets public by 2027-01-04 23:59 UTC and kept public |
| Single-task (x3) | $10k each | Best selected score on invsqrt, dqi or dfthcsos individually |

Every additional prize carries the same licensing, reproducibility and documentation requirements as
the winning submission. Exact terms: [COMPETITION_RULES.md](COMPETITION_RULES.md).

## Where the field stands (as of 2026-11-09, from public notebooks; not verified by us)

Public notebooks report about 25x on the leaderboard (a geometric-mean score near 25.15). A top
notebook lists per-benchmark ratios of roughly 22x for invsqrt, 65x for dqi and 11x for dfthcsos.
The gains came from replacing Newton-Raphson with a table plus quadratic (Horner) evaluation, a
Berlekamp-Massey style decoder for DQI, and smaller, refit factorizations for chemistry. Many authors
build on one another's public work under mixed licences. Treat these numbers as leads to check, not
facts; the baseline entry still scores about 1.0.

## Glossary

| Term | Meaning |
|---|---|
| Kickmix circuit | Circuit of reversible classical gates, phase gates and measurement-based uncomputation; cheap to verify classically |
| Toffoli | Controlled-controlled-NOT; the main expensive gate |
| Ancilla | Scratch qubit that must be returned to 0 |
| MBUC | Measurement-based uncomputation: measure a scratch qubit and cancel the sign cheaply instead of reversing the computation |
| QROM | Quantum lookup table over a superposition of addresses |
| Syndrome | Compact fingerprint of errors in a codeword |
| Fiat-Shamir seeding | Test inputs seeded by a hash of the submission (plus secret salt), so there is no fixed hidden test set |
| Salt | Secret per-leaderboard-split string merged into the seed; we use our own salts when self-verifying |

## Further reading

- Khattar et al., arXiv:2610.23832 (companion paper); Babbush et al., arXiv:2603.28846 (kickmix
  circuits); Khattar et al., arXiv:2510.10967 (DQI resource estimate).
- Rubin et al., PNAS 2024 (fusion); Jordan et al., Nature 2025 (DQI); Reiher et al., PNAS 2017 and
  Low et al., PRX 2025 (FeMoCo).
- kickmix documentation in Google's Qualtran library.
- Our learning track (Epic B on the Pandan board) will turn these into a newcomer curriculum.
