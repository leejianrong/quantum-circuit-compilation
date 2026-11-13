# DQI: the 889-qubit architecture, re-derived (QCC-19, E041)

Source studied: syed3000's dataset `vqcc-own-circuit-portfolio` (Apache-2.0, `dqi_source_zip`: 425 files, 46k lines of Python,
a pinned "controller" process with hash-pinned review records, the actual decoder blocks and many classical checkers). Read as a
reference; no code was copied. Our own classical model is `src/dqi_gen/thiele.py` (`tests/unit/test_dqi_thiele.py`, passes). This
note is the architecture in our own words, with the stage costs cross-checked against our aggregate scan of the public circuit
(`docs/experiments/dqi-stage2.md`). The public DQI lineage and this packet's relation to it are in `docs/PROVENANCE.md`.

## The algorithm

1. **Residue geometry (Clifford, zero Toffolis).** Let `a_j = alpha^j` be the error positions, `S_t = sum_j e_j a_j^t`, and
   `M(z) = prod_{i<35} (z^2 + z + kappa_i)` with 35 constants of absolute trace 1 (`kappa_i = 2048 + t_i^2 + t_i`, `t_i = 2i`), so every
   factor is irreducible over GF(2^12) and `deg M = 70`. The polynomial `P(z) = sum_j e_j a_j (M(z) + M(a_j)) / (z + a_j)` has degree
   below 70 and its coefficients are fixed linear combinations of `S_1 .. S_70`: one invertible GF(2^12)-linear map, applied in place
   by CNOT networks. Its 35 residues `Y_i = P mod (z^2 + z + kappa_i)` are 35 words of 24 bits (the same 840 qubits).
2. **What the residues are.** `P(alpha_i) = R(alpha_i)` with `R = N / D`, `D = prod (z + a_j)` the locator, `N = sum_j e_j W_j D / (z + a_j)`,
   `W_j = a_j M(a_j)`: the 35 words are the values (and by Frobenius the conjugate values) of one rational function with
   `deg N < w <= deg D <= 35` at the 35 nodes `alpha_i` of GF(2^24). The error values come from `e_j = N(a_j) / (W_j D'(a_j))`.
3. **Extract (Thiele-type, in place).** At node `i` the head `P_i = D(alpha_i) / N(alpha_i)` (a linear polynomial, one GF(2^24) word) is
   recorded and `(N, D) <- ((D + P_i N) / q_i, N)`, `q_i = z^2 + z + kappa_i`. On residues this is: word `i` is updated against every
   earlier head `P_l` evaluated at node `i` (`query_step`, one GF(2^24) product and a public scale, 99 Toffolis), then its
   reciprocal is formed (a deferred inverse, a norm to GF(2^12) and one 12-bit inverse), and it is swapped with a 24-bit carry. The
   words end as the 35 partial quotients (a continued fraction of `R`), still 840 qubits, plus the 24-bit carry: the **864 base qubits,
   peak 889 to 890**. Every pivot is a GF(2^24) element, so a premature zero has probability about 2^-24: the failure-free mechanism
   (the same effect that `dqi-stage2.md` measured for the Cayley map, here with no symmetry bookkeeping). Weights below 35 end the
   recursion early; a "rolling tail" controller tracks the zero predicate, with a public cutoff `j_min = 15` (the weight law has no
   mass below 19).
4. **Synthesis.** The polynomials `(N, D)` are rebuilt from the heads: `(N, D) <- (q_i N + P_i D, D)` step by step, in place, with the
   coefficient products done by evaluation, pointwise products and interpolation (CNOT maps plus `r` products at step `r`).
5. **Convert.** The amplitude data is a polynomial `C` with `C(a_j) = e_j`: `C = N / (z M D') mod D`. In characteristic 2 the odd-degree
   derivative is a square, `D = E^2 + z O^2`, `D' = O^2`, and the inverse needs a Bezout identity of the half-degree pair `(E, O)` (degree
   at most 17); the circuit does it by a fixed-shape Euclid in place (`half_profile`: degree drops of at most two per step; the failure
   classes are a gcd other than 1, a drop above 2, and two padded windows).
6. **Scan.** With `C` in the 70 words, the sweep tests `D(a) = 0` (11 Toffolis: a 12-bit zero test) and applies the phase
   `<mask_j, C(a_j)>`, which is linear in the coefficients of `C`, so only the root flag gates it. 4,024 to 4,095 positions.
7. **Mirror.** Everything is undone (measurement-based erasure of the products, the reverse of extract costs 97k against 55k because it
   repays the phases of the masks it measured).

Stage Toffolis of the public circuit (our scan) against the packet's own ledger: extract 54.5k, synthesis 31.5k, convert 54.2k, scan
44.3k (4,024 x 11), then unconvert 55.7k, unsynthesis 38.3k, unextract 96.8k; the packet's source model for extract is
`99 n^2 + 951 n - 198` Toffolis for the forward plus reverse pair at `n = 35` (154k), matching 54.5k + 96.8k.

## Building blocks worth having (all derivable from standard algebra)

* **GF(2^24) multiplier of bilinear rank 99** (against 3 x 42 = 126 by Karatsuba over our rank-42 GF(2^12) product): GF(2^24) as a degree-6
  polynomial algebra over GF(16), evaluation at 11 points, each GF(16) product of rank 9 by two levels of quadratic Karatsuba; the
  evaluation and interpolation maps are free CNOT networks. Same recipe as our rank-42 `gfmul.py` (degree 4 over GF(8), 7 points, rank 6).
* GF(2^24) inversion through the norm to GF(2^12) (`N = x0^2 + x0 x1 + delta x1^2`), one 12-bit inverse and two products.
* Deferred inverses and hmr masks: erase a product by measurement and repay the phase later by a classically controlled CZ network.

## What a fresh generator needs (plan, with what already exists in our repository)

| piece | state |
|---|---|
| residue geometry (one 70 x 70 GF(2^12) linear map and its inverse) | `thiele.py` has the map; circuit = `apply_matrix_inplace` per 12-bit block (CNOTs) |
| GF(2^24) rank-99 multiplier, norm inverse | derive (our `gfmul.py` recipe), about 150 lines |
| in-place Thiele extract with deferred inverse, carry and tail controller | classical prototype next, then circuit |
| in-place synthesis by evaluation / interpolation | circuit |
| convert (half-degree Euclid of `(E, O)`, fixed shape) | we have the classical identity (`bezout.py`) and the Gu fixed-schedule description; the packet's version differs |
| scan with `C` (zero test + gated phase) | our `_chien_forney` pattern, simplified |
| mirror with measurement-based erasure | our `Tape` idea (lanczos.py) |

Predicted static cost of a faithful rebuild: the public circuit's own numbers (889 qubits, about 384k Toffolis, ratio about 67). Where it can
be beaten: the reverse of extract (97k against 55k forward) and the 24 spare qubits; the realistic first milestone is a verified full-size
build of the same architecture. That is a multi-week build for one agent; the stage-by-stage plan is: classical in-place extract (n = 35 words),
quantum extract on `narrow` with `n = 70`, then synthesis, convert, scan, and mirror, each checked against `thiele.py` before the next.

## Classical in-place pass, verified (E041, own code)

`thiele.extract` and `thiele.synthesize` implement steps 3 and 4 on the residues: per node the pair `(n_l, d_l)` (values of `(N, D)` up to
one scale, started as `(Y_l, 1)`), head `P_i = d_i / n_i` in the node ring `GF(2^12)[z] / (z^2 + z + kappa_i)`, update
`(n_l, d_l) <- ((d_l + P_i n_l) / (kappa_l + kappa_i), n_l)`. The division by `q_i(alpha_l)` is by the public nonzero constant
`kappa_l + kappa_i` (in node `l`, `z^2 = z + kappa_l`), so the only data-dependent inverse per step is the one pivot inverse (a norm to
GF(2^12) and one 12-bit inverse). Synthesis `(N, D) <- (D, q_i N + P_i D)` rebuilds the polynomials exactly; the error values then come from
`e = N(a) / (a M(a) D'(a))` (`tests/unit/test_dqi_thiele.py`, weights 1, 3, 19, 28, 35 all recover the planted word). Over 600 draws from the DQI
weight law the pass finds the true weight every time (0 failures; the expected rate is about 35 / 2^24 per shot).

Counts that follow for the quantum pass: step `i` costs `35 - i - 1` node updates (one GF(2^24) product each, rank 99 or 126) plus one pivot
inverse and the head product: about `35 * 34 / 2 = 595` products. This is the "595 node pairs" of the public circuit's notebook text.

## Step 1 done: our GF(2^24) multiplier of rank 99 (`src/dqi_gen/gfmul24.py`)

Built from the recipe above (degree 6 over GF(16), 11 points, two-level quadratic Karatsuba for each GF(16) product), with the output matrix found
by solving from random samples. Exact on all 576 basis pairs and 3,000 random pairs; the circuit (`FastMul24.ixor_mul`) costs exactly **99 Toffolis**, uses
3 ancillas, restores them, and the kickmix simulator shows no phase flips (`tests/unit/test_dqi_gfmul24.py`). Phase against a classical mask,
`(-1)^{<m, x y>}`, is free for the same reason as in GF(2^12): `<m, x y> = sum_i <m, W_i> (<f_i, x> <f_i, y>)`, a classically controlled CZ per AND term.

## Step 2 (common basis): no new multiplier needed

Nodes are `alpha_i = theta + t_i`, `t_i = 2 i`, `kappa_i = DELTA + t_i^2 + t_i`, so every node ring `GF(2^12)[z]/(z^2 + z + kappa_i)` is the one ring
`K` with `z = theta + t_i`. A head stored as coefficients `(h0, h1)` (`h0 + h1 z`) has the K-value `(h0 + t_i h1, h1)` at node `i`: one in-place CNOT map. The
division by `q_i(alpha_l)` is by the public constant `kappa_l + kappa_i`, applied to both halves of a word (a constant GF(2^12) multiply: CNOTs).

## Step 3: what the quantum pass needs (our own analysis, not yet built)

Per node `i` with the earlier heads in place and the carry holding 1: `i` times `d += P_old(alpha_i) n` (one rank-99 product, XOR into the carry), then the
constant scale, and the roles of `(n, d)` alternate by relabelling (no swap gate). After the loop `(n_i, d_i)` lie on the line `d = h n` with `h` the head. The
pass must leave `h` in the word and 1 in the carry, with `n_i` (24 bits) erased. That needs the "normalise by `1/n`" move (a consuming product plus
measurement of the old values) and the corresponding deferred phases in the reverse pass; the phase of an erased inverse needs the norm trick
(`<m, x^-1> = <m, conj(x) N^-1>`). This is the part where the public design spends its 195-Toffoli deferred inverse, its 264-Toffoli affine phases and the
extra 43k of the reverse pass; we have the multiplier and all the free phase gadgets, not yet the erase protocol.

## Gu port at full size (Kaggle, 5 salts)

The ported decoder (`rs`, Apache-2.0 Gu et al. design, `src/dqi_gen/rs_build.py`) builds and verifies at full
size on Kaggle (`qcc-dqi-gen`, build 661 s, verify 1,522 s, 18.3 GB peak): PASS at 5 salts, zero failures,
1,837 qubits, 444,030 Toffolis, worst-salt cost 1.828e12, i.e. a ratio of about 13.4 against the baseline
2.4439e13. This is the verified reference the own decoder (`thiele`, 955 qubits at n = 70, 71 positions)
has to beat. Ledger row appended to `ledger/results.jsonl`.

## Own decoder at full size (Kaggle, 5 salts)

`--gen thiele` (own geometry, wired extract and synthesis, plain scan with a per-position division): PASS at 5
salts, zero failures, 955 qubits, 615,399 Toffolis (the static prediction was 615k), worst-salt cost 6.717e11,
ratio 36.4 against 2.4439e13 (verified; the Gu port is 13.4). Build 97 s, verify 739 s, 5.2 GB peak.

## Convert stage: narrow result

`--gen fixed` adds the vendored converter (`night_outer`), `projective_finish` and the additive-FFT scan
(11 Toffolis per position, no gauge), wired in `src/dqi_gen/fixed.py`. Narrow (n = 70, 71 positions), 2,048
shots, official verifier: PASS, 903 qubits, 345,875 Toffolis, no value or phase errors. Static estimate at
full size: about 390k Toffolis at 903 qubits, a ratio of about 65.

Seeding the synthesis from the carry word (gauge chart bit, scalar seed, rolling-tail seam, as in the reference
pipeline) removes the extra word: narrow official verifier PASS at 2,048 shots with 890 qubits and 346,192
Toffolis (was 903 and 345,875). Static full-size estimate about 390.5k Toffolis, ratio about 66.
