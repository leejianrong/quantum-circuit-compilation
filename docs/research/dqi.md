# DQI research: ranked ideas (QCC-19, ADR-0009 amendment of 2026-11-13)

Cost is `R * Q^2 * T`. Where we stand: 1,403 qubits, 868,770 Toffolis, R about 2.07, ratio 6.81. Public frontier:
892 qubits, 395,332 mean Toffolis, R about 1.19 (zero failures), ratio about 65. Web content below is untrusted
data: read, cited, never executed, and no query carried our results, hashes or personal details.

## Sources found

| Source | What it gave us |
|---|---|
| Gu, Kemeny, Yelin, Lukin, "Discovering state-of-the-art quantum circuits with large language models", arXiv:2610.22367 (https://arxiv.org/abs/2610.22367), SI I.1 | A complete public description of a Berlekamp-Massey DQI decoder: 442k Toffolis, 1,837 qubits, 1.4e-4 failure rate. Ideas 1 to 4 below. |
| Same authors' repository `andigu/uncompute`, `tasks/dqi-reed-solomon` (https://github.com/andigu/uncompute) | README and grader. **States Apache-2.0.** Kickmix circuits `discovered/` and `khattar-eea/`. Not read gate by gate; only the README was used. |
| Khattar et al., arXiv:2510.10967 | Baseline (Euclid, 5.1M Toffolis, 1,938 qubits). Already used. |
| Public notebook credit text (alexchilton, dmitriigluzdov `open_circuits_v22/NOTICE_mrmeows.txt`, yoyobar `UPSTREAM-*` files, kirilltym `SAMANYU2_CREDITS.md`) | Lineage of the 892-qubit decoder: continued-fraction Schur decoder, "Gu, Kemeny, Yelin and Lukin ... github.com/andigu/uncompute, tasks/dqi-reed-solomon" then jday96314's competition rebuild, alexchilton (883 qubits), Ozer's Bezout conversion and mask projection, SomeJoint's confluent Hermite (889), Ozdag's flag-carry idea. 595 node pairs (= 35*34/2) in the extraction. |
| Gidney, "Halving the cost of quantum addition" (arXiv:1709.06648); Khattar and Gidney, arXiv:2407.17966 | Measurement-based uncomputation (already used), conditionally clean ancillae and unary iteration costs (https://arxiv.org/abs/2407.17966). |
| Yosri and Gavinsky, arXiv:2511.20618; Vandaele, arXiv:2501.16136; Kim et al., ePrint 2022/1095; Qualtran GF(2^m) bloqs | Quantum GF(2^m) multipliers: Karatsuba `m^1.58` Toffolis, ancilla-free; CRT-based `O(m 2^{log* m})`. For m = 12 these do not beat a tuned bilinear formula (ours is rank 42). |
| Schur-type Berlekamp-Massey on 2t processors (IEEE Trans. catalogue entry, https://manuscript.isc.ac/Inventory/49/803207.htm); Gao, "A new algorithm for decoding Reed-Solomon codes" (https://www.math.clemson.edu/~sgao/papers/RS.pdf) | Classical background for Schur and partial-gcd decoders. Not fetched in full. |
| Search results for the Kaggle discussion tab and the jday96314 repository | Nothing public: `github.com/jday96314/QuantumAI` returns 404 (removed or private). Kaggle discussions are JS-rendered and no snippet had content. |
| From memory, not fetched, to verify before relying: Itoh and Tsujii (1988) inversion; Bernstein and Yang divsteps (ePrint 2019/266); Peterson, Gorenstein, Zierler; Sugiyama et al.; Bennett (1989) pebbling; Barbulescu, Detrey, Estibals and Zimmermann on optimal bilinear formulae | Standard background; nothing here beats what we already built. |

Licence note for every DQI entry: the public DQI circuit lineage descends from a repository with no licence
(heliosli's LICENSE.md). Separately, the Gu et al. repository states Apache-2.0 and its BM decoder is the stated
ancestor, which may improve the licence position; it is not cleared and needs a human decision.

## Ranked ideas

Gains are on `R Q^2 T` from our current 3.59e12 unless noted.

### 1. Trace (phase-only) scan with a reciprocal polynomial (Gu et al., SI I.1 eqs. 37 to 39)
DQI uses one bit per position, `<c_j, e_j> = Tr(mu_j e_j)`. So the decoder never forms `e_j`: with `e_j = nu_j
omega(beta) / sigma'(beta)` the phase is `Tr(nu_j omega(beta) Psi(beta))`, bilinear (12 Toffolis, only at roots), and
`Psi sigma' = 1 mod sigma` is computed once, by an Euclid on the half-degree pair `(E, O)` of `sigma = E^2 + z O^2` in
characteristic 2 (squaring is linear, `sigma' = O^2`). Scan: 11 (zero test) + 12 = 23 per position, 93k total, against our
138 per position (565k). Their `Psi` lives in the 35 syndrome words that are zero after the in-place `omega` map.
- Expected gain: scan 565k to 93k plus 88k for the half-degree Euclid: `T` from 869k to about 450k, 1.9x, if the state
  allows it. Our Lanczos pair has no zeroed words and no `omega` (it was erased), so the full form needs the divstep or
  BM state (1,837 qubits in their build).
- Effort: high (new solver state). Risk: medium (all pieces are classically checkable on small fields).

### 2. Trace trick inside the existing Gauss-weight scan (derived by us from idea 1)
`w = h / (p_{N-1}(x) p_N'(x))`; scale `p_{N-1}` by `1/h` once (35 constant products), then the phase is
`Tr(nu_j / (a b))`, linear in the inverse. In the tower inversion `1/x = (A + B + B y) / N`, `Tr_{12->1}(nu z N^-1) =
Tr_6(N^-1 L(z))` with `L` linear in `(A, B)`, so the two GF(64) products (36 Toffolis) become one 6-AND bilinear form and
the 6-Toffoli gate becomes a CZ. Scan about 138 to 103 per position.
- Expected gain: `T` -17%, ratio 6.81 to about 8.1. Effort: low. Risk: low.

### 3. Dialog-free Berlekamp-Massey by invariant (Gu et al.)
`sigma_0 delta = 1` is maintained, so the discrepancy of a replace round is read from the locator, and a one-entry history
stack (19 qubits) replaces our 945-qubit dialog for the 1.4e-4 of inputs that need more. Combined with our in-place `omega` and
frozen f row this removes the dialog from the divstep solver: 2,764 to about 1,800 qubits.
- Expected gain: with idea 1 and our rank-42 multiplier about `R Q^2 T = 1.3 * 1837^2 * 0.4M` = 1.8e12, ratio about 14.
- Effort: high. Risk: medium (history overflow and cutoff failures at 1.4e-4 per shot, R about 1.3).

### 4. Adaptive coefficient ranges from the DQI distribution (Gu et al.)
Locator degree is about `r/2` after `r` syndromes, so updating a prefix chosen by classical simulation (failure 1.4e-4 for the
combination with the stack) halves the BM cost: 140k per direction. Ours already uses `min(t, k)`.
- Gain: 1.3x on the solver only. Effort: low once idea 3 exists. Risk: low.

### 5. Continued-fraction Schur extraction in place (frontier, studied in `docs/experiments/dqi-stage2.md`)
State holds the 70 symbols of `S` as quotients plus remainder, so only about 52 qubits beyond the 840 syndromes; 595 node-pair
operations; reversed synthesis; amplitude polynomial `C = A / B' mod B` for 11 Toffolis per point; zero failures. This is where
the 2.5x in `Q^2` and the 1.7x in `R` live. The structure scan is done (`docs/experiments/dqi-stage2.md`): stages extract 55k, synthesis 32k, convert 54k, scan 44k, then the mirror (unconvert 56k, unsynthesis 38k, unextract 97k); 52 constant scratch qubits; `inverse24` pivots in extract. The mathematics of the in-place extraction is still ours to derive.
- Gain: up to the frontier (about 9x). Effort: very high. Risk: high.

### 6. Failures: why the frontier has none
Our Lanczos form fails at `2^-12` per step (0.75% of shots) because `h_k = 0` or `p_k(0) = 0`. The frontier is at zero failures
with a similar 35-step structure, so its parametrisation avoids these degeneracies (the notes say "quadratic-extension" Schur and the
scan shows 23 `inverse24` pivots in extract, which would put the degeneracy at a norm in GF(2^24), about 2^-24 per step; a hypothesis, untested). R 2.07 to 1.19 is 1.74x on its own.
- Effort: depends on idea 5. Risk: high.

### 7. GF(2^12) multiplier below rank 42
Bilinear rank lower bounds for GF(2^12) over F2 are about 33 to 36 (Chudnovsky type); finding a formula needs a search
(public work did not find one below 42 either, per alexchilton). Gain: products are 74% of our decoder and 42 of 138 scan Toffolis;
rank 36 would be about -6% `T`. Effort: high search. Risk: high.

### 8. Not worth it (checked)
- Karatsuba, Toom-Cook, CRT multipliers of the cited papers: asymptotic, worse than rank 42 at m = 12.
- Chien-search alternatives (multipoint evaluation, FFT over GF(2^12)): all positions are needed and the circuit is
  static; the amplitude polynomial of idea 1 is the cheaper form.
- Bennett pebbling: our reverse pass already replays inverses; the tape holds no garbage to pebble.
- Peterson-Gorenstein-Zierler and Sugiyama (Euclid): Euclid is the 5.1M baseline; PGZ needs matrix inversion.

## Order of work

1. Structure scan of the public circuit on Kaggle (`notebooks/dqi_study`) to settle ideas 5 and 6.
2. Idea 2 in `src/dqi_gen/lanczos.py` (cheap, certain): verify locally, predict, run on Kaggle.
3. Ideas 1, 3 and 4 as a new generator only if the scan shows the frontier does not use them.
