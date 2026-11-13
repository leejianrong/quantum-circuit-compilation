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
   the only explanation we see for the frontier's zero failures (R 1.19) with 35-node inputs. Not verified: it needs a classical
   prototype of block-2 steps over the extension (next step below).
4. **Scan is 11 Toffolis per position because the weights are in a polynomial** (the `convert` stage, 49 `inverse12`), kept in place.
   It is the zero test only: the phase of a polynomial evaluation against a classical mask is linear (CNOT) and the gate on the
   root flag is a CZ. Ours is 138 per position (the evaluation of two polynomials, a product, an inversion, two more products).
   This is 0.51M of our 0.87M.
5. **Reverse is dearer than forward** (`unextract` 97k against `extract` 55k): consistent with measurement-based clearing in the
   forward pass that must be repaid in the reverse.
6. **Extract has about the same work per step throughout** (about 3,000 Toffolis per 200,000 instructions across 19 windows), not a
   triangle shrinking in time: the 23 steps each touch a window of constant width.

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

1. Classical prototype over GF(2^24): take consecutive moment pairs `(S_{2i}, S_{2i+1})` as one extension element, run the Lanczos or
   Schur recursion on 35 of them with 2 x 2 block pivots, and measure the degeneracy rate on the DQI weight law (target: under 1e-5 per
   shot) and whether the pair state is 70 words in place. If it works, the failure factor R 2.07 to 1.19 is 1.74x by itself.
2. Amplitude polynomial `C` with `C(root) = weight`, held in the 70 words: find the in-place map from the pair `(p_N, p_{N-1})`
   (or from the final Jacobi parameters) to `(sigma, C)`; then the scan is 44k instead of 565k.
3. Only then rebuild the decoder as an in-place Schur or block-Lanczos extraction with a 52-qubit scratch budget.
