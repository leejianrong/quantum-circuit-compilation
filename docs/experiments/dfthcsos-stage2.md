# dfthcsos stage 2: public ideas, our own seed (QCC-16, QCC-15)

ADR-0009 amendment of 2026-11-13 allows study of public work and online research. Research summary and
ranked ideas: [docs/research/dfthcsos.md](../research/dfthcsos.md). Everything implemented is ours.

## Finding that matters

The public notebook text (marculera) says the frontier tables come from a seed built from the target alone
(pivoted Cholesky leaves, balanced k-means into groups, simultaneous OMP, least-squares weights) and a very
long fit (60k-iteration L-BFGS rounds, then 33-stage progressive rounding, Adam), reaching 12 mHa at the
scoring shape. Our random-start fit stalls at 28.8 mHa, so the seed and the fit length are the gap, not the
rounding schedule (consistent with dfthcsos-eight-bit.md). Other ideas (coded bit 0, row dealing, Newton refit of
W and H2) are logged but not built.

## Experiment: our compact seed, from the description (negative so far)

`src/dfthcsos_gen/seed.py`, `scripts/run_fit.py --init compact`. Shape (8,143,44), laptop, 4 threads,
about 0.5 s per L-BFGS iteration. Own `tsym` from the FCIDUMP (not committed).

| iteration | compact seed `error_2` | random start (E003, same shape) |
|---:|---:|---:|
| 0 | 2.12 | |
| 100 | 0.617 | 0.446 |
| 200 | 0.349 | 0.219 |
| 400 | 0.229 | 0.122 |
| 700 | 0.176 | 0.083 |

Our seed is worse than a random start at equal iterations. The 2.12 start error shows the OMP step is weak:
the 44 leaf matrices per group are nearly full rank (76), and with 12 candidate eigenvectors per leaf and
B = 143 shared vectors the group cannot represent them. Not yet tried: all 76 eigenvectors as candidates, more
leaves than R*C (they used 414 for 360 slots and let the fit drop some), the best of 500 k-means starts by
orbitals per group, weighted least squares, and a fit of tens of thousands of iterations (their advantage
showed over 60k iterations, not 700). The run was stopped at 700 iterations. No verifier run is justified;
the ledger is unchanged.

## Status

Best verified fully-own result is unchanged: 1,697,674,805 (ratio 1.98, 3/3 salts, 11-bit words). The two
Kaggle fits (`qcc-dfthcsos-fit`, `-fit-b`) were not touched. Next lever: finish the seed (items above) and run it
for 10+ h on a Kaggle kernel; then progressive rounding at 8 bits on a base below about 14 mHa.

## Kaggle fits and QAT (round 2)

Fits fetched to `~/qcc-fits/kaggle/` (sha256 prefixes of `v.npy`/`w.npy`): `qcc-dfthcsos-fit` (8,176,56, 9,000
iterations) 3f21839106e3a8aa / 57f1b3f6a67bf6a2, continuous `error_2` 0.01682 (re-scored with `eval_fit.py`);
`qcc-dfthcsos-fit-b` (8,143,44, 30,000 iterations) 45b6786636d39a67 / 17890abf47d72505, 0.02274, does not
pass even continuously, so the small shape is closed for our fits.

QAT (`dfthcsos_qat.py`, 6 stages x 80 iterations) on the 0.01682 table, `error_2` after fixing each share:

| bits | 0.4 | 0.65 | 0.8 | 0.9 | 0.96 | 1.0 (all rounded) |
|---:|---:|---:|---:|---:|---:|---:|
| 11 | 0.01817 | 0.02049 | 0.02057 | 0.02102 | 0.02142 | 0.02259 |
| 10 | 0.02205 | 0.02935 | 0.02854 | 0.02903 | 0.03059 | 0.03422 |

Both fail the 0.02 gate, so no verifier run. The earlier 0.0138 table gave 0.0179 at 11 bits; this one loses
about 0.019 to rounding, so the 11-bit gate needs a continuous fit near 0.014 or lower. A 45,000-iteration
continuation runs as `leejianrong/qcc-dfthcsos-fit-c` (`notebooks/dfthcsos_fit_c`, chained on `-fit`, about 11 h);
the last 100 iterations of the first run still gained 4e-5.

## Public loader architecture by dynamic analysis (own words)

Method: the public frontier's `angle_k_0.kmb` was simulated in kickmix on all 1,220 addresses (zero phase
flips) to read the word registers, and its gate text was read for aggregate structure. Nothing was copied.

- Registers: `selection` of 11 qubits, `word_0..4` of 8 qubits (J = 5), 77 work qubits, 128 in all; 296 CCX,
  about 16,600 CX, 80 HMR/CZ pairs (measure-and-fix uncompute of the ANDs).
- Address split: low 4 bits `l`, high 7 bits `h = a >> 4` (77 values). The circuit first builds, one temporary
  AND each, the monomials of `h` (75 products of the high bits: the algebraic-normal-form basis, in which every
  function of `h` is a CX-only linear combination) and of `l` (7 products of the low bits).
- Output bits are then `F(h) + G(l) + sum_t v_t[o] alpha_t(h) beta_t(l)`. `F` and `G` cost only CX. Each product
  is one CCX of a pivot wire holding `beta_t` and a pivot wire holding `alpha_t` (each a CX-combination of
  monomials) targeted at a word bit; CX fan-out of that bit into other word bits before and after the CCX shares
  one product between several output bits. About 220 CCX serve 40 output bits (5.5 per bit; one plane at
  `lb = 4` needs up to 8): a GF(2) tensor rank near 220 for a 40 x 76 x 15 tensor.
- The table looks random in every simple view: each bit plane has full centered rank 15 at `lb = 4` (31 at
  `lb = 5`, 19 at `lb = 6`), the three flattenings are full rank (40, 76, 15), the 15 slices sum to rank 534, and
  no bit-0 block of 16 is affine in the low address bits (circuit 0 holds no coded bit; circuits with a coded
  bit were not examined). So the low joint rank comes from how the words were chosen: rounded into a low
  tensor-rank set, not visible per plane. Such a table has to be chosen jointly with the rounding: pick
  `alpha_t, beta_t`, solve for `v_t, F, G`, round the angles into that affine set (a code-constrained rounding;
  E004 showed that imposing rank after rounding is hopeless).
- Our `bilinear.py` has the geometry; it lacks the sharing across output bits and the free `F(h) + G(l)` part.
  That generalisation is not built.

Cost model: at J = 5, 8 bits, 15 circuits x (about 86 ANDs + 220 products) is about 4,600 Toffolis per pass
against 4,151 in the public circuits, in line with the 8,302-Toffoli frontier. It is unusable until the table can
be rounded into the rank-220 code, which first needs a continuous fit at or below about 0.014.

No milestone (fully-own ratio 3 or 6.85) reached; best fully-own verified remains ratio 1.98.

## GF(2) decomposition search (built, little gain) and the qubit finding

`src/dfthcsos_gen/gf2tensor.py`: flip-graph random walk (Kauers and Moosbauer, arXiv 2212.01175; plus
transitions after Arai et al., arXiv 2312.08793; both ideas, our code) on the centered tensor, from two starts
(slice-by-slice, rank 534-600; per-plane, unit `v`), with a pair-aware annealer whose cost is `sum_v ceil(m_v / 2)`
(two rank-one terms with the same output vector share one Toffoli). Journal-based undo, exactness tested.
Results on an 8-bit table made from our 11-bit QAT words (40 outputs, `lb = 4`, 88 x 16):

| method | terms | Toffolis with pairing |
|---|---:|---:|
| slice start, flips only, 2M steps | 476 | about 470 (pairs rarely form) |
| per-plane start (`bilinear.py` equivalent) | 479 | 255 |
| per-plane start, annealed 4M steps (temp 0.08) | 479 | 253 |

The shared search gains under 1% over per-plane planning: the flip walk stalls, and rank is the wrong objective
once pairing is available (the per-plane start has rank 479 yet costs 255). The planted-rank test (rank 120 in
a 40 x 80 x 16 tensor) is not recovered (stays 600): this heuristic does not find hidden structure. Not tried: SAT/ILP on
small blocks, a pair-aware move set, a start that exploits smooth high bits (high bit planes have lower
centered rank than low ones: 255 here against 320 for a random table).

The qubit finding is the real obstacle: one-hot lines (`H + L = 104` qubits at `lb = 4`) leave room for J = 1
word at 8 bits (11 + 8 J + 104 <= 128). The public loader gets J = 5 with about 77 work qubits because its lines
are ANF monomials of the selection bits, not one-hot lines: the selection bits themselves are the degree-1
lines and only the `H - 1 - 7` and `L - 1 - 4` products of degree >= 2 take a qubit (one AND each). A line basis
`{x^S : S < H}` works (the matrix `[S subset of h]` is triangular), a form `alpha(h)` converts by a Moebius transform
(`c_S = sum over h subset of S of alpha(h)`), and the constant line is an X on the pivot. The generator needs that
line basis before any 8-bit candidate fits in 128 qubits; not yet built. Per-plane cost at lb = 5 would be 58 work
qubits (J = 7) but plane rank 31, so 16 Toffolis per plane.

## ANF line-basis loader (built, exact, cost-modelled)

`src/dfthcsos_gen/anf.py` keeps the per-plane planner but swaps one-hot lines for monomial lines of the selection
bits: `m_S`, `S < H` on the high bits and `T < L` on the low bits; the selection qubits are the degree-1 lines, a constant
qubit is line 0, and each `S` with at least two bits takes one work qubit and one AND (`m_S = m_(S minus top bit) AND
x_top`), uncomputed by measurement. One-hot forms convert to monomial sets by the Moebius transform. Tests:
`tests/unit/test_dfthcsos_anf.py` (transform inverse, form values, kickmix load of three table shapes: exact on all
addresses, selection restored, work clean, no phase flip, static count = kickmix count). At scale (our 8-bit table from the
failing 11-bit QAT words, 1,408 addresses, `lb = 6`, J = 5) the family of 15 circuits builds in 1 s, uses 125 qubits and
7,257 Toffolis per pass, and circuits 0, 7 and 14 load exactly on all addresses and shots.

Angle cost per pass by split (same table; `work` includes the constant line):

| bits | lb | work | J | K | Toffolis per pass |
|---:|---:|---:|---:|---:|---:|
| 8 | 4 | 92 | 3 | 25 | 6,765 |
| 8 | 5 | 64 | 6 | 13 | 9,910 |
| 8 | 6 | 74 | 5 | 15 | 7,257 |
| 11 | 4 | 92 | 2 | 38 | 9,701 |
| 11 | 5 | 64 | 4 | 19 | 13,679 |
| 11 | 6 | 74 | 3 | 25 | 10,473 |

(Unary iteration at 11 bits: about 13,300 per pass with J = 9.) Cost-model predictions for (8,176,56) with our
`lambda_eff` 62.6 (`dfthcsos_model.score`; `lambda_eff` 46.9 in brackets): 8 bits, `lb = 6`, J = 5: T 23,541,
Q 430, ratio 5.3 (7.1); the same on a (8,143,44) shape: 5.9 (7.9); 11 bits, `lb = 4`, J = 2: T 26,945, Q 715,
ratio 2.78 (3.71) against 1.98 for unary at 11 bits. So the loader alone lifts an 11-bit table from 1.98 to about 2.8
and an 8-bit table to about 5.3 to 5.9, which makes the fit quality (an 11-bit table passing the gates, and 8-bit
below 0.012 continuous) the only gate to ratio 3 and beyond. These are predictions: no verifier run yet, since no own
table passes the accuracy gates (QAT of the 0.0168 fit gives 0.0226 at 11 bits).

## Shared-product loader (built) and a correction to the reading above

`src/dfthcsos_gen/shared.py` builds a circuit for any table of the form `F(h) + G(l) + sum_t v_t alpha_t(h) beta_t(l)`
(one Toffoli per term however many output bits it feeds: CX fan-out `p -> o` before and after the CCX). Test
`tests/unit/test_dfthcsos_shared.py`: a random plan on 100 addresses loads exactly on all addresses and shots, clean
work register, no phase flip, and the static Toffoli count equals kickmix's.

Capacity argument (why I no longer think the public table is rounded into a low-rank code). A code of 214 terms
(without the two-products-per-Toffoli trick of `bilinear.py`) has about 32,000 free bits against 49,000 table bits,
so about a third of all bits would be constrained, which would force rounding errors of several LSB at 8 bits (our
naive 8-bit rounding is already 14x over the gate). The public rounding noise is far smaller, so the more likely
reading is that the table is an essentially arbitrary 8-bit table and the loader is a good GF(2) tensor
decomposition of it: a random 40 x 76 x 15 GF(2) tensor has rank about 350, and with two rank-one terms per
Toffoli about 175 to 215 Toffolis serve 40 output bits, matching the observed 214 products. That makes the loader
cost a decomposition-search problem on any table, with no rank constraint on the fit, and the 8-bit gate a pure
fit-quality problem (the continuous error must be near 0.012 before 8-bit rounding can pass). Not verified by
decomposing a table.

Cost at the widths we can reach. Per-plane `bilinear.py` on a 1,484-address table (8,176,56) has lines
`H + L = 79` qubits, plane rank 31 and so 16 Toffolis per plane: about 25 circuits x (79 + 33 x 16) = 15,000 per pass
at 11 bits (3 words per circuit), against about 13,300 for the unary loader with 9 words. So at 11 bits a
loader change does not help; the gain is bound to 8 bits and to a shared decomposition (the 8-bit table is
the blocker). Next levers in order: the continuation fit, then a decomposition search over GF(2) for an 8-bit
table (kernel search), then 8-bit rounding.

## Study of andigu/uncompute `chemistry-fe2s2` and of more public loader write-ups

Studied the README and the discovered-circuit README at commit 64b5a13a (Apache-2.0, ADR-0009 Amendment 2). Nothing is
ported: that task is the alias-sampling PREPARE plus Pauli SELECT of a 40-qubit Fe2S2 Hamiltonian with 41,052 terms, a
different data-loading problem from our 1,220-row Givens-angle tables. What they do, and whether it transfers:

| technique (theirs) | transfers? |
|---|---|
| Repeated-span pruning: a split of the lookup tree is dropped when both children hold identical words in the graded range; free choices (alias schedule, out-of-range rows) are spent to create repeats, 41,050 to 10,271 Toffolis | Our unary loader already breaks early on equal subtrees, but angle words of distinct vectors never repeat; the analogue is the freedom in the rounding (gauge, row order), not exploitable now |
| Frame blocking: rows related by commuting Cliffords share one block root | No analogue in THC angles |
| Quadratic forms of GF(2)-rank 2r need r CCZs after a CNOT change of coordinates; Z-gauge search over the table | Same algebra as our two-products-per-Toffoli planes (`bilinear.py`, `anf.py`) |
| Measurement-based unlookup with a joint phase fix on a one-hot window | Not usable: the verifier runs each `ANGLE_k` as an XOR oracle forward and reversed, so the reverse cannot be a cheaper measured uncompute |
| Exact dynamic program over "hold" budgets per tree node (keep a conjunction alive vs recompute it) | Possible small gain for the unary tree at 11 bits; not tried |

From the Kaggle write-ups (lightningv08 "Bezout-Schur + 5-Word QROM", markdown only; ideas logged in PROVENANCE) the loader
structure matches what we reverse-engineered, with these extra details: (1) the word domain has bit `brot-1` equal to
bit `brot-2` (angles in the half circle: "pi-gauge"), so a word carries only 7 independent Boolean functions at 8 bits and the
top bit is one CNOT; (2) the lookup cache (monomial lines) takes 72 work qubits, so the circuit has
`11 + 8 J + 72` qubits, J = 5 fits at 123 and divides the 75 angle columns into 15 circuits; (3) per circuit the
coordinates are (output bit) x (low-address monomial) with a hi-address function each, paired two per Toffoli, and
"kernel relations" (linear dependencies among those hi-functions) remove products: 420 coordinates and 60 relations give
180 paired products for J = 4, 450 coordinates and 75 relations give 225 for J = 5 (297 Toffolis per circuit with the
72-Toffoli cache).

Implemented from that: `post.angles_of(half=True)` / `post.encode(half=True)` (half-circle angles via a signed
parent carry: a rotation by theta + pi negates both outputs, and the decoded vector may be -u, which `u u^T` ignores),
`anf.build_anf_loader(..., sign_ext=True)` (the top plane is never loaded; CNOT from bit brot-2 to brot-1 before and
after the planes, so the XOR chain of deltas stays consistent), `--half` and `--loader anf` in
`scripts/dfthcsos_post.py`, `--half` in `scripts/dfthcsos_qat.py`. Test: random reachable words (top bits equal) load
exactly. Not yet done: the kernel-relation search over the (output bit, low monomial) hi-functions.

## Reverse engineering syed3000's chemistry set (Apache-2.0, studied; nothing ported yet)

Source: Kaggle dataset `syed3000/vqcc-own-circuit-portfolio` (licence apache-2.0, copyright 2026 Syed Asad Ali), file
`dfthcsos_source_zip`, read from `~/qcc-circuits/syed_src/` (outside the repo). Their record: 427 qubits, 14,810 Toffolis,
`lambda_eff` 46.907, ratio 11.31, 4,074 angle Toffolis per pass (263 to 293 per circuit, 15 circuits).

Loader (`compiler/emit_plan.py`, read and re-derived, our `anf.py` matches its architecture):
- 11 selection qubits, five 8-bit words, 69 hi monomial ANDs (`S < 77`), 15 low monomials (some low monomials are
  carried by the helper qubits), uncomputed by measurement (HMR plus CZ).
- Planes: 7 per word (35). The 8th bit is the "helper" `bit7 xor bit6`, a table that is almost always 0 and is loaded as
  a cheap pure monomial; CX bit6 to bit7 before and after (the same trick as our `sign_ext`).
- Each Toffoli computes `(l1 + h1)(l2 + h2)`, a PAIR of rank-one terms, and fans the result out to an output mask over
  the 35 planes (CX from the first output qubit to the others before and after). 212 products per circuit, every one
  paired, every out mask distinct, then a final CX layer for the `F(h) + G(l)` remainder.
- The product plan is chosen by a matroid-parity formulation: candidate pairs of outer products (low form x out mask), a
  required span dimension (525 minus "cuts"), and a randomized matching with an alternating-matrix witness over GF(2^8)
  that is verified separately for independence over GF(2). 424 independent columns give 212 products. Our per-plane
  planner needs about 280 products for 35 planes at 8 bits, so this is worth about 25% of the angle part (about 8% of
  `T_total`). Not rebuilt: it needs the cross tensor (target matrices per hi monomial) and the span-dimension
  bookkeeping, which is the next generator task.

Words and accuracy (`research/scripts`, 54 files, not rerunnable without their intermediate arrays):
- Word search keeps bits 0 to 2 of every word as codes (an affine code in the low address bits and "parity codes": the
  parity of bit 1, and a quadratic code for bit 2, over the five words of a batch must lie in
  `S = {A(h) + sum_i l_i B_i(h) + C(l)}`), decoded exactly by enumerating the 2^11 nonlinear parts `C` and choosing the
  best affine part per hi block (`parity_code.py`). Higher bits move in steps of 8, 16, 32 on the later columns, each move
  priced exactly with a fast metric model (`fastchem.py`, `flipcost.py`), applied one at a time, then the weights are
  refit by SQP / exact Hessian (`exact_refit2.py`, `sqp.py`) keeping only feasible states. This is the "polish after
  rounding" that takes a 12 mHa continuous fit to the 20 mHa gate at 8 bits.
- Their vectors are local: decoding their words gives a participation ratio of 4.4 orbitals per vector (1.1 to 20) and
  12.6 to 26.6 effective orbitals per group, against our dense random starts (76). A random SPARSE start (5 of a random 20
  orbitals per group) already reaches `error_2` 0.0782 after 600 iterations against 0.091 for the dense start at the same
  count (`scripts/run_fit.py --init-from`); the longer run is in progress.
- The continuous gap is mostly compute: the public notebook text fits on an A100 for hundreds of thousands of
  L-BFGS iterations; our 9,000 to 30,000 on four CPU cores are one to two orders fewer. `scripts/run_fit_gpu.py`
  (torch float64, autograd, parity-tested against the numpy objective) and two kernels
  (`notebooks/dfthcsos_fit_gpu_a`, `_b`, continuing fit-b and fit) are ready, but the weekly Kaggle GPU quota
  (30 h) is exhausted, so neither is pushed yet.

## The basin question: structure of a frontier solution, structured starts (QCC-16)

Decoded vectors of the Apache-2.0 reference set (aggregate statistics only): the orbitals holding 50% of `u^2` number 1 for
the median vector (mean 1.6), holding 90% median 3 (mean 4.3), holding 99% median 11 (mean 12.8); the dominant orbital of the
143 vectors of a group takes 43 to 62 distinct values (spread over the orbitals, at most 13 repeats); 6 of 143 vectors per group
sit above 0.9 on one orbital; `W` has 18% zeros, per-copy L1 norms 0.5 to 4.1, top singular value of a group `W`
0.8 to 1.0 against 0.08 for the 44th. The tail matters: with `w` re-fitted, their vectors give `error_2` 0.0198, but keeping only
the top 1, 2, 3, 5, 8, 12 orbitals of each vector gives 1.93, 1.26, 1.00, 0.81, 0.71, 0.60, so locality is a property of the
optimum (a dominant orbital plus a dense small tail), not a sparsity pattern to impose.

Starts tried (shape 8,143,44, `rank 800`, equal settings, `error_2` after 600 to 700 L-BFGS iterations): dense random 0.0831;
random 5-of-20 orbital supports 0.0713; Cholesky-leaf eigenvectors with least-squares weights 0.74 (bad); orbital-centered
(`e_p + sigma g`, `p` cycling over the orbitals of each group, `seed.centered_seed`) 0.0713 at 600 iterations for
`sigma = 0.3` (about 0.065 at 700) and 0.081 at 600 for `sigma = 0.1`. At 200 iterations: dense 0.220, sparse 0.162,
centered 0.140 (`sigma = 0.1`) and 0.148 (`sigma = 0.3`). So a structured start is about 15 to 20% ahead of the dense one at equal
iterations (roughly 2x in iterations at this stage); whether the advantage persists to the asymptote is what the long kernel
(`leejianrong/qcc-dfthcsos-cen`, centered `sigma = 0.3`, rank 800, 150k iterations) will show. Not a basin change on its own.

## Matroid-parity pair planner (built; the cut search is the open problem)

`src/dfthcsos_gen/parity.py` (randomized alternating matrix over GF(2^8), perfect-pairing extraction by contraction;
our rewrite of the method read in syed3000's `extract_matching.py`, THIRD_PARTY_NOTICES.md) and
`src/dfthcsos_gen/matroid.py` (cross tensor `M_S` per hi monomial, candidate pairs `(l1, l2, out)` over blocks of three
low monomials, coordinates `h1, h2` of each `M_S` on the chosen rank-one columns, loader with `(l1 + h1)(l2 + h2)`
products fanned out to an output mask, CNOT-only `F, G` leftover, exactness checked by construction). Tests:
`test_dfthcsos_parity.py` (planted perfect matchings; rank certificate; no matching when all pairs share a vector) and
`test_dfthcsos_matroid.py` (a planned paired loader loads a table exactly in kickmix).

At scale (circuit 1 of an 8-bit half-circle table of ours, 1,408 addresses, 35 planes, `lb = 4`): the cross tensor has
rank 87; with no cuts the pairing has `ceil(525 / 2)` = 262 products against 280 for the per-plane planner (371 against
353 Toffolis per circuit with the 91 ANDs; 5%). The 212 products of the public plan need about 100 "cuts" (functionals
on blocks of three low monomials that vanish on every `M_S`; the span `W` of the rank-one columns is their kernel,
`dim W / 2` products). My random greedy cut search (120 tries, two cuts per try because `dim W` must stay even, 10 s per
rank test) accepted none: random annihilating functionals break the candidate structure. Their plan seems to start
from a feasible plan and take cuts as the annihilator of its columns, then refine; that bootstrap (and a candidate
set with all pairwise sums of `out` vectors, which I sampled) is the missing step. Expected gain if solved: about 25%
of the angle part, 8% of `T_total`.

A counting bound for the block structure (three low monomials per block, five blocks, 35 planes): the local target
space of a block has dimension `rank S` (= `H - 1`, 87 here, 75 for 1,220 addresses) inside the block's 105 dimensions, so
a cut family can remove at most `105 - (H - 1)` dimensions per block and `dim W >= 5 (H - 1)`, i.e. at least
`5 (H - 1) / 2` products: 218 for our 1,408-address table (against 262 without cuts), 188 for 1,220 addresses (the public
plan has 212). Whether a rank-one-spanned `W` that tight exists is a subspace-selection problem (for each of the seven
forms `l` of a block a subspace `V_l` of the 35 output dimensions with `S_block` inside `sum_l l (x) V_l`); a dimension
count says seven `V_l` of dimension 13 should suffice (about 1,200 conditions on about 2,000 parameters per block), which
points to an alternating least-squares style search over the `V_l` rather than random cuts. Not built.
