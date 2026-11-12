# DQI: look-ahead analysis and Lanczos trims (QCC-19, E021)

Cost is `R Q^2 T`. Start: 1,457 qubits, 905,338 Toffolis, R about 2.07 (0.75% failing shots), ratio 6.08.
Local checks use `narrow` (full `n` and field, 71 positions); the full-size static prediction is
`narrow + 4,024 x 138` Toffolis (the scan is exactly 138 per position) at the same qubit count.

## Why the exact look-ahead is not built

`R(rate)` from the verifier formula (102,400 shots, Clopper-Pearson at 2^-128) is close to linear in the failing-shot rate:

| failing shots | 0.75% | 0.50% | 0.30% | 0.10% | 0.01% | 0 |
|---|---:|---:|---:|---:|---:|---:|
| R | 2.07 | 1.83 | 1.62 | 1.39 | 1.23 | 1.19 |

A perfect fix is worth at most 1.74x before paying for it. A partial fix on a fraction `f` of the steps removes only
`f` of the premature zeros (they are uniform in `k`): `f = 1/3` gives R 1.83 for about +10% Toffolis, a wash.

The full block step is harder than the earlier estimate (+80% decoder) because of alignment. After a degenerate step
the pair is `(p_{k+2}, p_k)`: its degree runs one ahead of the loop index for the rest of the run. Everything in a step is
a function of that index (array lengths `k + 1`, which raw syndrome `S_{k-1}` is erased, which window `S_{k..2k+1}`
the heads read, the termination count, the degree the scan sees). With a data-dependent offset (0, 1, or more after
further events) each of these becomes a controlled shift of a 35-register array (a cswap per qubit) or a doubled head
dot product, not a few extra products. The estimate +30% `T` for R 2.0 to 1.25 is therefore a lower bound and the net
is below 1.2x. Not built.

Ideas that keep the `2^-12` per-step floor and were dropped on paper: a fake node of known weight at a chosen
position (`h_k(eps)` is affine in `eps`: one bad `eps` per error word); detecting a premature zero as
`h_k = 0 and s_k != 0` (free, but the retry cannot be conditional in a static circuit); the window shift `g(z) = z`
(needs `2w <= n - 1`, fails for 2.8% of shots at the top weight).

## The amplitude polynomial (scan near 11 Toffolis per point) is not reachable from the pair

The Gauss weight `w = h / (p_{N-1}(x) p_N'(x))` needs `1 / p_{N-1}` and `1 / p_N'` at a root. The Wronskian makes
`1 / p_{N-1}(x) = q_N(x) / const` a polynomial, but `q_N` (the numerator, the old Omega) needs the low raw moments that
are already erased, and `1 / p_N'(x)` is polynomial only as the Bezout cofactor of `(p_N, p_N')`, which is another solver.
Interpolating the weights needs the moments of `w_j / p_N'(x_j)`, not `S`; the residue form needs the LFSR extension
of `S` to 4,095 moments (about 143k products). The polynomial `p_{N-1} p_N' mod p_N` is about 2,450 products (100k
Toffolis against 172k saved) but needs 35 more registers (420 qubits), which loses at `Q^2`. Christoffel-Darboux gives
`p_{N-1}(x) p_N'(x) = h_{N-1} (sum_k p_k(x) / sqrt(h_k))^2` at a root, which would drop the 42-Toffoli product, but
the sum runs over every `p_k`, so it needs one more polynomial array.

## Trims built (each verified on `narrow`: PASS, 3 salts at 25,600 shots, 0 phase errors, 0.67 to 0.83% failing shots)

| change | qubits | Toffolis (narrow) |
|---|---:|---:|
| baseline (QCC-19 tower inversions) | 1,457 | 350,026 |
| fresh products are cleared by measurement in the reverse pass (`initmul` is the inverse of `delmul`; the tape had made the inverse of every fresh product a second full product), `S_{k-1}` erased by measurement, `h_{k-1}` cleared as `lam * h` then `lam` by one inverse clear instead of a division | 1,457 | 313,458 |
| `A + B` formed in place inside the tower inversion (no 6 + 3 qubit copy), scan accumulators `sg, od, am` released while the tower runs and rebuilt after (zero Toffolis), second head after the inversion, `a_eff` after the row scale | 1,439 to 1,412 | 313,458 |
| idle zero registers of ours are freed around every tape operation, so tower scratch and the integer-add ancillas sit in room that is already counted | | |
| carried scalars cleared before the capacity registers are taken | 1,403 | 313,458 |

## Full-size result (Kaggle, official verifier, 102,400 shots per salt, 5 salts, kernel `qcc-dqi-gen`)

| version | qubits | Toffolis | worst-salt cost | ratio vs 2.4439e13 | salts |
|---|---:|---:|---:|---:|---|
| before (QCC-19 tower inversions) | 1,457 | 905,338 | 4.017e12 | 6.08 | 5/5 PASS |
| PR 79, circuit sha256 `3b456a35568d...` | 1,412 | 868,770 | 3.6576e12 | 6.68 | 5/5 PASS |
| PR 80, circuit sha256 `64951ff397ca...` | 1,403 | 868,770 | 3.5895e12 | 6.81 | 5/5 PASS |

The static prediction (`narrow + 4,024 x 138`, same qubits) matched to the Toffoli. R stays at about 2.07 (the circuit is
unchanged logically). Per-salt costs of the last run: 3.563e12, 3.482e12, 3.556e12, 3.504e12, 3.590e12.
Not promoted: `best/` needs 10 full-strength salts through `bench promote`, and 6.81 is far below the public circuit (about 65).
Where the qubits stand: the decoder peaks at 1,400 to 1,403 (six temporaries at the in-place row scale on top of the
pair, raw tail and carried scalars), the scan at 1,400 (1,328 live plus 74 scratch). Both would have to fall together.

## Where the Toffolis are now (narrow, decoder only 304k of 313k)

heads (two dot products per step) 78k, erase 25k forward and 25k back, row update 4 products per coefficient over both
passes (100k, at the floor of a three-term recurrence), z0 shift and swap cswaps 46k, controlled adds 17.6k, inversions 10k.
Scan: 138 per position = product 42, norm 18, subfield inversion 25, gate 6, two products 36, zero test 11.
