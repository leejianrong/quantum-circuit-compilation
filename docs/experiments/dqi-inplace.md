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

## Result: `src/dqi_gen/lanczos.py` (Kaggle, official verifier, 102,400 shots, 5/5 salts PASS)

Pair state `(p_k, p_{k-1})` plus carried `h`, raw syndromes erased in place (`S_{k-1}` from `p_k`, with a controlled shift
when `p_k(0) = 0`), update gated by an alive bit so the arrays freeze at `(p_w, p_{w-1})`, Gauss-weight scan, reverse
pass by replaying a tape of inverse operations. sha256 of the full circuit `caeb5e61...d79bc`.

| version | qubits | Toffolis | official cost | ratio vs 2.4439e13 | failures per 102,400 |
|---|---:|---:|---:|---:|---|
| divstep (QCC-19, PR 51) | 2,764 | 1,017,742 | 9.262e12 | 2.64 | 0 |
| Lanczos | 1,472 | 1,210,488 | 5.39e12 to 5.59e12 | 4.37 (worst salt) to 4.53 | 755 to 834 (value errors, 0.75 to 0.81%) |

`R` is 2.0 to 2.1 because of the failures; with none the same circuit would cost about 2.6e12 (ratio 9.4). Static prediction
before running was 5.5e12 (qubits 1,400 predicted, 1,472 built). Qubits fall 47% (S 840, 38 extra poly registers, scan scratch
144, rest scalars), Toffolis rise 19% (scan 171 per position, about 0.70M; decoder both passes about 0.5M).

## What did not work or was not built

* **Exact look-ahead for `h_k = 0`** (0.75% of shots, the whole remaining penalty): the block step is
  `p_{k+2} = (z^2 + c z + d) p_k + e p_{k-1}`, `e = s_k/h_{k-1}`, and the pair `(p_{k+2}, p_k)` still determines `(c, d, e, p_{k-1})`,
  so it also needs no dialog. In a static circuit it needs three more heads per step, a three-product update, two more inversions
  and a skip iteration so the degree stays aligned (about +80% decoder, +22% `T`) for `R` 2.0 to 1.25: net only about 20%. Not built.
* **Retry with a shifted node set** for failing shots: needs a second pass, `Q` and `T` both up; worse.
* **Floor of this family**: the pair is 69 slots but only `k` syndromes are erased at step `k`, so about 35 slots (420 qubits)
  beyond the 840 remain; erasing the high raw moments needs the Jacobi-to-moments map (the reverse pass itself).
* A faster GF(2^12) multiplier (public work reports rank 42, ours 63) or an amplitude polynomial (scan 11 Toffolis per point)
  are the next Toffoli levers; the scan is 58% of `T`.

## Next lever

Qubits: 1,472 against 892. Toffolis: the scan (0.70M against the frontier's 0.535M in total). Failures: `h_k = 0`.
Local check: `QCC_DATA=data uv run python -m dqi_gen.instances --gen lanczos --instance narrow --shots 8192` (seconds).
