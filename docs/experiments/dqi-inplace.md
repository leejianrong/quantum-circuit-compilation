# DQI: a dialog-free key-equation solver (QCC-19)

Goal: get the decoder from 2,764 qubits toward the public frontier (about 892). Cost is `R Q^2 T`, so a qubit is worth
two Toffolis. Ideas here come from papers and standard numerical analysis (Chebyshev / Lanczos algorithm, Gauss
quadrature); the only public-text hint is that the 892-qubit decoder is a continued-fraction (Schur-type) design
whose scan costs about 11 Toffolis per point (logged under "Ideas learned" in `docs/PROVENANCE.md`). No circuit file was read.

## Why the dialog and the rows were there, and why they are not needed

`S -> (sigma, Omega)` is a bijection on decodable syndromes, but a divstep or Berlekamp-Massey step on the rows
`(v_g, v_f)` is not locally invertible: the quotient `c` of a non-swap step is not a function of the rows after the
step, so the previous design stored it (the dialog). The obstruction is a property of the *state*, not of the
information. Take the state to be the **pair of consecutive monic orthogonal polynomials** of the moment functional
`L(z^i) = S_i` (here `S_i = sum_j w_j x_j^i`, nodes `x_j = alpha^j`, `w_j = e_j x_j`):

    p_{k+1} = (z + a_k) p_k + b_k p_{k-1},    h_k = L(p_k z^k),   a_k = s_k/h_k + p_{k,k-1},   b_k = h_k/h_{k-1},

with `h_k` and `s_k = L(p_k z^{k+1})` two dot products of `p_k` with a window of raw syndromes (`S_{k..2k+1}`).

1. **Recoverability.** `p_{k+1}` has `k+1` free coefficients, `p_{k-1}` has `k-1`: the update consumes `(a_k, b_k)`
   into exactly two new coefficients. `a_k = p_{k+1,k} + p_{k,k-1}` and `b_k = p_{k+1,k-1} + p_{k,k-2} + a_k p_{k,k-1}`
   (one product), and then `p_{k-1} = (p_{k+1} + (z + a_k) p_k) / b_k`. So the pair `(p_{k+1}, p_k)` determines the step:
   the step is a bijection and needs **no dialog** (`jacobi.peel`, tested). In divstep language a thin step and a swap step
   are fused so the pair absorbs both quotients. After `t` steps the pair holds `2t - 1 = 69` free coefficients plus `h`:
   exactly the 70 symbols of information in `S`.
2. **Raw syndromes can be erased as the pair grows.** `L(p_k z^l) = 0` for `l < k`, so with `p_k(0) != 0`
   `S_{k-1} = sum_{i>=1} p_{k,i} S_{k-1+i} / p_{k,0}`. Later heads only read `S_{k'..2k'+1}` with `k' >= k`, so `S_{k-1}` is
   not needed again: erase it with `k` products and reuse its 12 qubits for the polynomials (reverse pass undoes it).
   Live set at step `k`: `n - k` raw syndromes + `2k` pair slots, i.e. `n + k` slots, at most 105 slots (1,260 qubits)
   instead of `S + rows + dialog` (2,769 slots).
3. **Forney without Omega.** Gauss quadrature: `w_j = h_{N-1} / (p_{N-1}(x_j) p_N'(x_j))` at the `N` roots of `p_N`, so the scan
   needs only the pair and `h`. It costs one product more per position than the Omega form (about 150 against 108 Toffolis).
   (`p_N'` is the odd part of `p_N` in characteristic 2.)
4. **Termination.** For weight `w < t` the recurrence ends at `k = w` (`h_w = 0`) with `p_w` the locator. The circuit keeps an
   alive bit (`alive_{k+1} = alive_k and h_k != 0`) and gates the update so the arrays freeze at `(p_w, p_{w-1})`.

## Classical check (`src/dqi_gen/jacobi.py`, `tests/unit/test_dqi_jacobi.py`)

GF(2^12), DQI weight distribution, 4,000 shots: roots of `p_w` are exactly the error positions and the Gauss weights equal
the errors (300 of 300 generic shots). Failure events of the scheme, per shot:

| event | rate |
|---|---:|
| premature `h_k = 0` (the Hankel minor of the moments vanishes before `k = w`) | 0.9% |
| `p_k(0) = 0` at an erasing step | 0.5% |

Both are about `2^-12` per step and are not handled by the first circuit, so the verifier sees about 1.4% failures:
`eps_plus` about 0.019 and `R` about 2.7 instead of 1.19 (a 2.25x penalty). That is why the exact divstep solver stays the
reference; the Jacobi solver only wins when `Q^2` falls by more than that.

## Cost prediction (full size, before building)

Products are 63 Toffolis (GF(2^12)), an inversion 315. Per step `k`: heads `2(k+1)` products, pair update `2k`, erase `k`;
reverse pass skips the heads (measurement clears). About 6,300 products over both passes (0.40M Toffolis), scan about
`4095 x 150 = 0.61M`, so `T` is about 1.05M and `Q` about 1,400. With `R = 2.7`: `R Q^2 T` is about 5.5e12, ratio about 4.4 (now
2.64). With the failures removed (a look-ahead step for `h_k = 0`, a shift for `p_k(0) = 0`) it would be about 10.

## What did not work (analysis only)

* **Two-row (Chebyshev table) form**, rows `sigma_{k,l} = L(p_k z^l)`: state is the pair plus two rows of length `n - 2k`, so
  `2n` slots at the start, and the top entries of the discarded row cannot be recomputed (they are the high moments):
  they stay as garbage. Raw syndromes with the head dot products (above) avoid both.
* **Series form of divsteps** (`G` in place of `S`): needs the second series `F`; its dropped coefficient each step is real
  data (garbage `n` slots), so about `2n` plus rows. Same floor as the paper's `len(poly) + len(dialog) = 2n`.
* **Single remainder plus quotients** (Euclid on `(z^n, S)`, state `(q_0..q_{i-1}, r_i)`, `n + i` slots): the previous
  remainder must be re-derived by a continuant division, `O(i)` products per coefficient, about 29k products per pass
  (1.2M Toffolis): no gain.
* **Series reciprocal in place** (the Schur step `f -> (f - g)/(z (1 - g f))`): triangular, but each coefficient of `1/F`
  needs all lower coefficients of both `F` and `1/F`; no in-place form with `O(1)` scratch.
