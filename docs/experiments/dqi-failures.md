# DQI: Lanczos decoder failures and Toffoli cuts (QCC-19)

Cost is `R Q^2 T`; `R(eps) = ln 2 / -ln(1/2 + 2 sqrt(eps))` with `eps` the Clopper-Pearson bound on the failing-shot
rate, so 0.75% failures cost R about 2.0 against 1.19 with none.

## Which inputs fail (classical enumeration, `jacobi.solve`, GF(2^12), n = 70, DQI weight law, 75,000 shots)

| event | shots | rate |
|---|---:|---:|
| premature `h_k = 0` at a step `k < w` (Hankel minor of the moments vanishes) | 516 | 0.69% |
| `p_k(0) = 0` at an erasing step (handled by the controlled shift) | 563 | 0.75% |

The premature events are spread evenly over `k` (about `2^-12` per step, `w` is 28 to 34 for 80% of shots, so about `w/4096`),
and they follow the weight law (none below `w = 23`). The circuit's observed 0.72 to 0.81% on the narrow instance
and at full size agrees. The set depends only on the error word (a property of the weighted Vandermonde minors), not on the
circuit, so no local fix inside this algorithm lowers it: the probability per step is that of a random field element being 0.

## Ruled out for removing the failures

* **Rescaling nodes** (`S_i -> c^i S_i`): `H_k` only picks up a power of `c`, same zeros. **Shift of the origin** (`z -> z + a`):
  the Gram matrix changes by a unitriangular change of basis, same determinant.
* **Shifted moment window** (`S_{s+i}`, same nodes, weights times `x^s`): different zero set, but it needs `2w <= n - s`;
  the weight law has 2.8% at `w = 35` (needs all 70 moments) and only 97% / 88% / 73% of shots allow `s = 1 / 3 / 5`.
  The circuit cannot know `w` in advance, and a retry doubles `Q` or `T`.
* **Multiplier `g(z)` on the functional** (`T_i = sum g_m S_{i+m}`): same moment budget problem, and a degree-1 `g` kills a node.
* **Randomised Hankel preconditioning**: already at the `2^-12` per step floor of a 12-bit field; the bound
  `n^2 / |F|` of Toeplitz preconditioners is worse.
* **Exact look-ahead** (block step `p_{k+2} = (z^2 + c z + d) p_k + e p_{k-1}`, three more heads, three-product update,
  two inversions, a skipped iteration): the only exact fix. After the cuts below the decoder is 0.34M of 0.90M Toffolis, so
  +80% decoder is about +30% `T` for R 2.0 to 1.25 (1.6x): net about 1.2x, with extra qubits. Not built; it is the remaining
  lever for failures.

## Toffoli cuts built (each verified on mid12 and narrow, then at full size on Kaggle)

| step | qubits | Toffolis (full) | official cost, worst salt | ratio vs 2.4439e13 |
|---|---:|---:|---:|---:|
| Lanczos (PR 64) | 1,472 | 1,210,488 | 5.59e12 | 4.37 |
| rank-42 multiplier `gfmul.py` (PR 66) | 1,472 | 950,487 | 4.347e12 (5/5 PASS, circuit sha256 `aa309296f5af...`) | 5.62 |
| tower inversions and divisions (PR 67) | 1,457 | 905,338 (static) | see below | |

* **Multiplier.** GF(2^12) as a degree-4 extension of GF(8): `a = sum a_i theta^i`, the product polynomial over GF(8) is
  evaluated at 7 points of the projective line (0, 1, infinity and four more), each GF(8) product is 6 ANDs
  (0, 1, infinity and GF(4) residues). All linear parts are CNOTs; `W` is found by solving from samples and checked
  against the field (`tests/unit/test_dqi_gfmul.py`). 42 Toffolis per product against 63, 18 against 21 in GF(2^6),
  6 against 7 in GF(8); 3 extra qubits. Scan 171 to 138 per position, decoder products all cheaper.
* **Tower inversion.** `1/x = (A + B + B y) / N`, `N = A^2 + A B + b B^2` in GF(2^6): about 82 Toffolis to compute and 46
  to clear (the inverse scaffold is undone for free) against 315 each; division is inverse plus product. Saves 45k
  Toffolis and 15 qubits (the old 48-qubit builtin scaffold is gone).
* Decoder floor now (narrow profile): products 74%, controlled swaps 14% (zero-constant-term shift and dead-array swap),
  controlled adds 5%. The scan is 4,095 x 138 = 0.565M and is near the floor of this formula (product 42, norm 18,
  inversion 25, two products 36, gate 6, zero test 11).
* Peak qubits are in the scan (1,457; the tape alone peaks at 1,412): scan scratch is 129 qubits, a reduction below
  about 100 would need re-computing the zero-test ladder (about +10 Toffolis per position).
