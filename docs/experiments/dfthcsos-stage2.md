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
