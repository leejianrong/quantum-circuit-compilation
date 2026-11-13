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
