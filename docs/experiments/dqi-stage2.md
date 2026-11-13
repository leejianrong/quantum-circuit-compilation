# DQI stage 2: what the 892-qubit circuit's structure says (QCC-19, ADR-0009 amendment 2026-11-13)

Question: where does the public frontier (e9f54be3: 892 qubits, 395,332 Toffolis, ratio about 65) get its 2.5x in `Q^2`,
its 2.2x in `T` and its 1.7x in `R` over our Lanczos decoder (1,403 qubits, 868,770 Toffolis, R about 2.07, ratio 6.81)?

Method: `dqi_gen.study` streams the text dump of the circuit on Kaggle (kernel `qcc-dqi-study`, 2.5 minutes, 0.5 GB) and
keeps only counts: instruction mix, Toffolis per window, per qubit block first and last use, and Toffolis, entries and
distinct qubits per `INFO_TAG` path (the circuit names its own stages). No gate list, constant or instruction sequence was
read or kept. The public DQI lineage has no licence; the stated upstream decoder repository (andigu/uncompute) is Apache-2.0
(see `docs/research/dqi.md`). Everything below is a count or a stage name.

## Result: stage table (static counts; CCX 382,190 + CCZ 1,384 + CSWAP 12,012 = 395,586)

| stage (tag) | Toffolis | share | qubits touched | what the tags say |
|---|---:|---:|---:|---|
| `mask_projection` | 0 | 0 | 840 | 2.39M Clifford instructions: the linear part of the phase is applied once, in the syndrome registers |
| `initial` | 0 | 0 | 840 | 0.26M Clifford instructions |
| `extract` | 54,549 | 14% | 892 | 23 entries of `inverse24` (norm 42 Toffolis each, products 70), 6 of `multiply v`, 2 of `inverse12` |
| `synthesis` | 31,519 | 8% | 892 | 2 entries of `inverse12` only |
| `convert` | 54,197 | 14% | 891 | 49 `inverse12`, 26 `aligned_route`, 3 `full_head_product` |
| `scan` | 44,275 | 11% | 851 | 4,024 positions at 11 Toffolis (the zero test); 8,050 `gf_iadd` constant steps are all Clifford |
| `unconvert` | 55,654 | 14% | 891 | mirror of `convert`, plus `head_phase`, `head_pivot` |
| `unsynthesis` | 38,341 | 10% | 892 | |
| `unextract` | 96,765 | 24% | 892 | mirror of `extract` with more work (about 1.8x) |

The circuit is 58.3M instructions, 52.1M of them CX: most of the "cost" is linear maps, none of it counted. Executed Toffolis equal
the static count here (the 4,091 `PUSH_CONDITION` blocks are the per-position conditions).

## What this tells us (derived from the counts; hypotheses marked)

1. **The 892 is 840 plus 52, constant from `extract` to `uninitial`.** Qubit ids 840 to 891 (52 qubits: four 12-qubit
   registers plus four flags) are first used at the start of `extract` and last used in `uninitial`; there is no growth phase. So
   the whole decoder state lives in the 70 syndrome words and is transformed in place. Ours holds 840 plus a pair of
   polynomials that grows to 35 more registers plus carried scalars plus 74 to 129 scan scratch.
2. **There is no separate solver peak.** The number of distinct qubits touched per 200,000 instructions swings between 325 and 892
   in the middle stages, i.e. the stages work on windows of the 70 words, not on fresh registers.
3. **`inverse24` in `extract` (hypothesis: block pivots over the quadratic extension GF(2^24)).** Each extraction step inverts an
   element of GF(2^24) through its norm to GF(2^12) (norm 42 Toffolis = one GF(2^12) product, then an `inverse12`, then products).
   Our scheme pivots on one GF(2^12) element and fails when it is zero (2^-12 per step, 0.75% of shots). A pivot that is a
   GF(2^24) element, i.e. a 2 x 2 block treated as one field element, is zero with probability about 2^-24 per step. That is
   the only explanation we see for the frontier's zero failures (R 1.19) with 35-node inputs. Tested below.
4. **Scan is 11 Toffolis per position because the weights are in a polynomial** (the `convert` stage, 49 `inverse12`), kept in place.
   It is the zero test only: the phase of a polynomial evaluation against a classical mask is linear (CNOT) and the gate on the
   root flag is a CZ. Ours is 138 per position (the evaluation of two polynomials, a product, an inversion, two more products).
   This is 0.51M of our 0.87M.
5. **Reverse is dearer than forward** (`unextract` 97k against `extract` 55k): consistent with measurement-based clearing in the
   forward pass that must be repaid in the reverse.
6. **Extract has about the same work per step throughout** (about 3,000 Toffolis per 200,000 instructions across 19 windows), not a
   triangle shrinking in time: the 23 steps each touch a window of constant width.


## Classical prototype: the quadratic extension does remove the failures (`src/dqi_gen/cayley.py`, E028)

The Cayley map `u = (x + theta) / (x + thetabar)` sends the nodes `x` in F_q to the unit circle of F_{q^2}. The sequence
`T_i = sum_m [z^m]((z+theta)^i (z+thetabar)^(N-i)) S_m` is a linear image of the syndromes with `T_{N-i} = conj(T_i)` (so the same
bits as `S`: 35 independent F_{q^2} words for `n = 70`) and weights `w_j (x_j + thetabar)^N` that are generic elements of F_{q^2}.
Running the Jacobi recursion (`jacobi.solve`) on `T` over F_{q^2}, then `x = (theta + u thetabar) / (1 + u)` at the roots and the
Gauss weights divided by `(x + thetabar)^N`, decodes the original word. Failing events (premature `h_k = 0`, `p_k(0) = 0`)
per shot, measured with the official-style weight-`w` words:

| field q | n | w | plain Lanczos over F_q | Cayley over F_{q^2} | about `(w-1)/q` and `(w-1)/q^2` |
|---:|---:|---:|---:|---:|---|
| 16 | 8 | 4 | 0.334 | 0.013 | 0.19, 0.012 |
| 32 | 10 | 5 | 0.217 | 0.0073 | 0.13, 0.0039 |
| 64 | 10 | 5 | 0.116 | 0.0015 | 0.06, 0.0010 |

(Hankel of `T` with complex weights, q = 64, w = 12 and 35-step windows: 0.0033 against 0.156 for plain Hankel and 0.155 for the Hermitian Toeplitz
form of the same data, whose minors are F_q-valued and fail as often as the plain one.) At q = 4096 and 35 steps this is
about `34 / 4096^2 = 2e-6` per shot, i.e. R 1.19 with no look-ahead. **The hypothesis holds for the failure factor (1.74x).** It
is a classical result for decoding correctness and degeneracy only: the leftover wrong answers (at most 1% at q = 16) vanish with q.

## Cost of the naive quantum version: a loss

Lanczos over F_{q^2} with raw words `T_0 .. T_34` (840 qubits, the high half by conjugation for free) has a pair of
polynomials with 24-bit coefficients (about 912 qubits instead of 456), a GF(2^24) product is 3 x 42 = 126 Toffolis (3x ours),
and the scan evaluates over F_{q^2}. Estimate: about 1,900 qubits and 2.5M to 3M Toffolis, `R` 1.19: cost about 1.5e13, ratio 1.6, far
below 6.81. The frontier gets the failure-free property with 892 qubits and 395k Toffolis, so it must use an in-place
Schur-type extraction that exploits the conjugation symmetry (our hypothesis: Szego-like recursion where one polynomial and its
conjugate-reverse replace the pair, about half the work per step), plus the conversion to the F_q locator and the amplitude
polynomial (`convert`, `unconvert`). That algorithm is not derived yet. No quantum generator was built for it.

## Szego-type reduction from `T_{N-i} = conj(T_i)`: analysis, no saving found (derived, not measured)

With `sigma_L(f)(z) = z^N conj(f)(1/z)` the functional obeys `L(f) = conj(L(sigma f))`. For the Jacobi polynomial `p_k`
(`L(p_k z^l) = 0` for `l < k`) this gives `L(p_k^* z^m) = 0` for `N - 2k < m <= N - k`, where `p_k^* = z^k conj(p_k)(1/z)`: the
conjugate-reverse of `p_k` is orthogonal in a *high* window, not the low one, so `p_k^*` is not a multiple of `p_k` and no
single polynomial replaces the pair for `k < N/2 + 1`. Equivalently `det conj(H_k^{(0)}) = det H_k^{(N-2k+2)}`: the symmetry
relates Hankel minors of two different windows, which is why the Hermitian Toeplitz form (one window, F_q-valued minors) fails
as often as plain and the Hankel form (generic pivots) has no halving. The symmetry halves only the raw words (35 F_{q^2}
words, same 840 qubits) and makes the final locator self-conjugate-reversed (`p_N^* = c p_N`, 35 F_q parameters). So the
pair over F_{q^2} costs about 912 qubits and 3x the products; the estimate of about 1,900 qubits stands. The frontier's 892
qubits therefore needs an in-place algorithm that this symmetry alone does not give; it is not derived here.

Information count that any in-place design must meet: the Lanczos end state holds raw tail (36 words) plus pair (69) plus
`h`, 105 words for 70 words of information, so about 35 words are redundant (the tail is a function of the pair), and the
amplitude polynomial `C` (35 words) can only live there if the tail is erased by an in-place map from the pair to the moments, or
if `C` is computed in place of `p_{N-1}` (a bijection given `p_N` and `h`, but computing it needs a polynomial inversion
with garbage). Neither has a cheap known circuit.

## Where this leaves the work (decision needed)

* Frontier-class (892 qubits) needs the missing in-place Schur-type algorithm: open research.
* Gu et al.'s Berlekamp-Massey design is a build from a published description. By estimate, with our rank-42 multiplier,
  adaptive ranges and our in-place Omega: dialog-free BM with our Forney scan 1,860 qubits, about 0.7M Toffolis, R about 1.2:
  3.0e12, ratio about 8; with their half-degree-Euclid reciprocal polynomial scan about 0.5M Toffolis: ratio about 11. Both
  are multi-day builds (history stack, shared update, cutoff failures at 1.4e-4, parked-quotient Euclid in the zeroed syndrome words).

## Negative result: the "phase-only trace" trick does not help our scan

Gu et al. (SI I.1) get 23 Toffolis per position with `Tr(nu omega(beta) Psi(beta))`. In our scan the phase is already applied with
`gf2_phase_by_product` and a classical mask, which costs no Toffolis (classically controlled CZ), so the product `h * (1/u)` is free.
The remaining 138 are the evaluation product 42, norm 18, subfield inversion 25, two subfield products 36, gate 6, zero test 11.
A trilinear form (`h`, `conj(od)`, `N^-1`) needs one explicit product, so nothing is saved; scaling `p_{N-1}` by `1/h`
once moves the product, not removes it. The only way below about 100 is the amplitude polynomial (idea 1 and 5 in
`docs/research/dqi.md`), which needs 35 more words that the Lanczos pair does not have.

## Why this was not rebuilt in this pass

An in-place block-pivot extraction plus synthesis plus amplitude polynomial is a new decoder, not a variant of ours. The counts above
fix its budget (about 54k + 32k + 54k Toffolis forward, 44k scan, 52 qubits of scratch) but not its mathematics, and a
guess at the mathematics cannot be checked without a classical prototype. Gu et al.'s BM decoder (1,837 qubits, 442k Toffolis,
published and Apache-2.0) would be a second route, about ratio 14 to 17 with our multiplier by estimate (`docs/research/dqi.md`
idea 3), but its scan relies on the same in-place `Psi` computation (a half-degree Euclid with parked quotients), which we have
not built either. No new full-size circuit was verified in this pass; the best own DQI stays at ratio 6.81.

## Next steps (in order)

1. (Done, above.) Failure-free by the Cayley map. Open: a Szego-type recursion that uses `T_{N-i} = conj(T_i)` so the state is one
   F_{q^2} polynomial and the raw words are erased in place (classical prototype first, count words per step).
2. Amplitude polynomial `C` with `C(root) = weight`, held in the 70 words: find the in-place map from the pair `(p_N, p_{N-1})`
   (or from the final Jacobi parameters) to `(sigma, C)`; then the scan is 44k instead of 565k.
3. Only then rebuild the decoder as an in-place Schur or block-Lanczos extraction with a 52-qubit scratch budget.

## Extract overhead and mask gauge (E041 follow-up, 2026-11-14): no gap to close

Measured on small builders (extract and seeded synthesis only, 35 words of 24 bits plus carry; `num_toffoli_like`): `extract.forward`
73,919 Toffolis; plus the seeded synthesis forward 101,884; plus the seeded synthesis backward 139,437; plus the extractor closing
222,595. The public circuit's four stages for the same span (extract 54,549, synthesis 31,519, unsynthesis 38,341, unextract 96,765)
sum to 221,174, so the round trip is within 0.6% (+1.4k). The 73.9k against 54.5k is a stage-boundary difference (our `extract.forward`
runs part of what the public tags call synthesis, and our reverse is correspondingly cheaper), and the vendored extractor is the
public kernel verbatim anyway. The full circuit (391,326) is already 1% below the public 395,586.
The mask gauge (`syndrome_gauge_plan`, 70 selected points skipped by the scan, disabled in `fixed.py`) saves at most 70 x 11 = 770
Toffolis (0.2%) before the cost of its selected-interpolation, so it cannot move the ratio. Further DQI gains need a different
decoder design, not these two items.
