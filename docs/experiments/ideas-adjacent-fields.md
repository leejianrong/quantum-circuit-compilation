# Ideas from adjacent fields (broad pass, 2026-11-22)

Purpose: before choosing the next lever, list methods that other fields built for the same *kind* of problem and say how each would
touch our three scores. Everything below is written from memory, **not checked against the papers**; names and years are pointers for
the verification pass, not citations. Tags: **[used]** the public lineage already uses a version of it (seen in the v17 sources),
**[new]** we have not seen it used here, **[tool]** a ready tool exists.

## What kind of problem this is

Clifford gates (CX, X, CZ, swaps) are free; only Toffoli/AND count, rotations and the peak qubit count are priced
(invsqrt: cost = qubits x Toffoli-equivalents; DQI: R Q^2 T; dfthcsos: lambda_eff T Q). So each task is
**minimise the multiplicative complexity of a function under a width cap, with a check that is exact and cheap** (full-domain
proof, 12 s on invsqrt; exact expectation; official verifier at the end). That is the shared structure of: cryptographic circuit
minimisation (AND gates), logic synthesis, register allocation with rematerialisation, and approximate computing.

## 1. Cryptography and secure computation (AND-gate minimisation)

Garbled-circuit and MPC protocols make XOR free and charge per AND, the same cost shape as ours.

* Multiplicative-complexity heuristics and exact SAT synthesis for small functions (Boyar-Peralta style AES S-box circuits; SAT-based
  S-box optimisation) **[new, tool]**. Targets: the 128x16 invsqrt table loaders (56 and 70 ANDs on the 46-qubit line), coefficient rows,
  the dfthcsos loaders, any 5 to 8 input block that recurs. First test: take the loader truth table, run an exact or heuristic
  AND-minimiser, compare with the 56/70 the owner reached.
* Tower-field and normal-basis arithmetic (Canright-style inversion; Itoh-Tsujii inversion with addition chains; squarings free in a
  normal basis) **[partly used]**: the DQI inverse and the Forney/BM stage. Check what the D70 field chart already does before
  spending time.
* Bilinear complexity and Karatsuba-type formulas for GF(2^k) multiplication, tensor-rank searches over GF(2) **[used]**: D70's rank-23
  tensor for the 2x2 GF(8) outer product is this. Flip-graph and RL-guided tensor decomposition searches (AlphaTensor, flip graphs)
  **[tool]** can look for lower ranks for the specific multipliers (GF(8), GF(64), GF(4096) pieces).

## 2. Logic synthesis and electronic design automation

* XOR-AND graph (XAG) optimisation and DAG-aware rewriting (ABC, mockturtle) **[tool]**: quantum compilers already map XAGs to
  reversible networks. A pass that converts a stage's classical part to a XAG, minimises ANDs, and maps back, with the exact proof as the gate.
* Satisfiability and observability don't-cares: the invsqrt domain is 3,133,452 of 2^22 inputs (25% unused) and our check is a full
  simulation, so every stage has a don't-care set we can *measure* **[used in part: audit_affine and audit_pairs do a version]**.
  Exact synthesis with those don't-cares is the generalisation.
* Approximate logic synthesis (error-rate or max-error bounded) **[new]**: matches the tolerance slack idea, but invsqrt has only 0.3%
  slack left, so this is a small lever there.
* Register allocation and rematerialisation (compilers): qubit count is register pressure; the choice between holding a value and
  recomputing it is rematerialisation; optimal allocation is polynomial on chordal interference graphs. Our width profile
  (`docs/log/entries/2026-11-22-invsqrt-v17-width-profile.md`) is the liveness analysis; the missing piece is an optimiser over it.

## 3. Reversible computing and pebbling

* Reversible pebbling games with SAT solvers (space-time tradeoff for uncomputation) **[new, tool]** and spooky pebbling
  (measurement-based uncomputation, which is what HMR does) **[used by hand]**. A SAT/ILP scheduler for which intermediate values to
  keep, recompute or uncompute-by-measurement is the principled version of the hold and retire patches.
* Lookup-table networks that trade Toffolis for dirty qubits (select-swap, QROAM-style) **[probably used]**: the loaders; check the
  loader certificates in the v17 trees.
* ESOP minimisation (EXORCISM) for reversible functions **[tool]**: alternative loader synthesis.

## 4. Computer arithmetic (hardware)

* Function evaluation with certified error budgets: multipartite and bipartite tables, minimax polynomials with Sollya, Gappa error proofs, FloPoCo-style
  bit-width allocation as an ILP **[new]**. invsqrt is the classic reciprocal-square-root unit; the fits here use a table plus polynomial, but the
  error budget is allocated by search, not by a certified ILP. A principled re-allocation could free bits, but only inside the 0.3%.
* Digit recurrence (SRT) division with redundant quotient digits **[used]**, online (MSB-first) arithmetic **[new]**, CORDIC **[new]**,
  Goldschmidt iteration **[new]** (needs multipliers, so probably worse), residue number systems **[new]**.

## 5. Coding theory and VLSI decoders (DQI)

* Reed-Solomon decoder architectures: inversionless Berlekamp-Massey (iBM, RiBM), Euclid/half-GCD, syndrome-free decoding, Chien search with
  shared constant multipliers, Montgomery's batch-inversion trick **[partly used]**. Our S6 study killed the Euclid-history route; the BM variants were
  studied in `dqi-bm.md`. The VLSI literature optimises area x time, a close cousin of Q^2 T.

## 6. Signal processing and machine learning (rounding, tables, search)

* Quantisation as a closest-vector problem under a quadratic form: GPTQ/OBQ (Hessian-aware sequential rounding with error
  compensation), AdaRound, QuIP-style incoherence processing and lattice codebooks, sigma-delta noise shaping, trellis-coded quantisation
  **[partly tried]**: the public team tried compensation vectors, LLL and multi-pass and still needed parity codes and a weight refit. The
  untried angle is **incoherence**: our free rotation gauge (S4) is the analogue of a random orthogonal pre-rotation that flattens the
  Hessian before rounding. Parked with QCC-16, but the idea carries to any rounding problem.
* Dictionary learning / sparse coding and vector quantisation for tables **[used in part]**: the "sign96 dictionary" and coded batches are this.
* Program synthesis with LLM-guided evolution (FunSearch, AlphaEvolve) and learned superoptimisation (AlphaDev, STOKE-style MCMC) **[new, tool]**:
  our generators are Python programs with an exact, cheap, automatic score (modelled cost in seconds, proof in 12 s), which is the
  setting those systems need. Mutation targets: the stage scripts, patch parameters, window rewrites. The public team already runs
  "evolve_cuts" and window searches; what is new would be a continuous harness we own.
* Quality-diversity search (MAP-Elites) and replica exchange (parallel tempering) from evolutionary biology and statistical physics **[new]**: for the
  discrete word and cut searches where greedy descent stalls.

## 7. Quantum chemistry and tensor methods (dfthcsos)

* Symmetry shifts (BLISS) and orbital rotation to lower lambda; THC versus double factorisation; l1-regularised fits (our Lambda penalty is
  this) **[used]**; the public team derives a hard floor lambda_eff >= 46.786 for any accepted table, so lambda has at most 0.33% left.
  Remaining levers are T and Q (loaders, shape), where the public field is tied at parts per million.

## 8. Compiler technology for circuits

* Superoptimisers with automatically synthesised and verified rewrite rules (Quartz/QUESO style), ZX-calculus and phase-polynomial T-count
  optimisation (T-par, TODD = decoding Reed-Muller codes), equality saturation with e-graphs **[new]**. Our T count is already 1 to 4; the gains would be on Toffolis
  and width, where equality saturation with a width-aware cost is an open problem rather than an off-the-shelf tool.

## Candidate programme, ranked by (expected gain, cost to test)

| # | Idea | Targets | First test (cheap) | Honest expectation |
|---|---|---|---|---|
| 1 | Exact or heuristic AND-minimisation of recurring small blocks (loaders, coefficient rows, table lookups) with don't-cares measured from the full domain | invsqrt, dfthcsos | one loader truth table into an exact/heuristic multiplicative-complexity tool; compare with 56/70 | the owner hand-searched these ("SAT-minimal AND programs"); gain probably a few ANDs |
| 2 | Pebbling/rematerialisation optimiser over the width profile | invsqrt qubits | ILP/SAT on the four slack regions and on the 287 peak segments | one qubit is 39 Toffolis, so even a partial cut matters; hard, structural |
| 3 | AlphaEvolve-style harness over the owned generators with the exact oracle | all | evolve one stage script of the v17 invsqrt driver (cost in seconds, proof in 12 s) | unknown; the harness is reusable and the public team does a manual version |
| 4 | Tensor-rank and flip-graph search for the GF multipliers | DQI | decompose the GF(8) 2x2 outer product and check rank 23 can be beaten | D70 already beat the textbook bounds; a rank-22 would be news |
| 5 | Incoherence (gauge) pre-rotation before rounding | dfthcsos (parked), any rounding | measure the Hessian diagonal spread before and after a gauge rotation | explains whether 8-bit words are ever reachable without codes |
| 6 | Certified function-evaluation error budgets (ILP) | invsqrt | re-allocate the error budget across table, rows and rotations | bounded by 0.3% slack |

## Caveats

The public lineage has months of work by a team of agents on exactly these levers; several items above are already inside it. The
verification pass should (a) confirm each reference, (b) check the v17 sources for the items marked **[used]** or **[probably used]**, and (c) estimate each
first test before any is run.
