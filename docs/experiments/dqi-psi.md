# DQI: the reciprocal-polynomial scan, design and classical prototype (QCC-19, E037)

Goal: replace the Forney scan of our dialog-free BM decoder (96 Toffolis per position, 386k of 741k, ratio 7.76) by a scan of about
23 per position, after the published idea of Gu, Kemeny, Yelin, Lukin (arXiv:2610.22367 SI I.1; Apache-2.0 repository, nothing copied;
the public DQI lineage has no licence). Code: `src/dqi_gen/bezout.py`, `tests/unit/test_dqi_bezout.py` (classical only).

## What is verified (classical)

* `sigma = E^2 + z O^2` in characteristic 2 (`E`, `O` have 18 coefficients, `E_0 = 1` after normalisation), `sigma' = O^2`.
* Constant-time Bernstein-Yang divsteps on the **reversed** pair `(E*, O*)` (`delta = 1`, swap when `delta > 0` and `g(0) != 0`, 36 steps),
  tracking the first row `(u, v)` of the transition matrix, give `u E* + v O* = c z^36` exactly. The monomial index is 36 in all 200 random
  trials (weights 1 to 35), so no data-dependent shift is needed. `u` has its nonzero coefficients in `[2, 18]` and `v` in `[2, 19]`:
  **35 words, the number of zero syndrome words that the in-place Omega leaves** (`S_35 .. S_69`).
* At a root `beta = 1/x` of `sigma`: `1 / sigma'(beta) = (x^-1 u(x)^2 + v(x)^2) x^-38 / c^2`
  (`tests/unit/test_dqi_bezout.py`, weights 1, 2, 9, 20, 34, 35). With `u~ = x^-19 u`, `v~ = x^-19 v` this is `(v~ + x^(-1/2) u~)^2 / c^2`:
  two polynomial evaluations by CNOT networks with Chien constants, a linear squaring, and `c` removed once by scaling the 35 words by `1/c`.
* Scan per position: the zero test of `sigma(beta)` (11 Toffolis) plus gating `Psi` by the root flag (12 ANDs), then the phase against
  `omega(beta)` by `gf2_phase_by_product` with the classical mask, which costs no Toffolis: **23 per position**, 4,024 x 23 = 93k against
  our 386k.

## Predicted cost if the in-place version exists

Euclid divsteps forward about 40k and reverse about 35k (36 steps over words of at most 18, products at rank 42, one inversion per step),
synthesis of `(u, v)` forward and back about 50k, scan 93k: about 218k replacing 386k, so `T` about 570k, `Q` about 1,870 to 1,910,
`R` 1.19 to 1.3: cost about 2.4e12, **ratio about 10** (7.76 now).

## The open problem: where the Euclid keeps its history

The 36 words of `E*`, `O*` are the locator registers themselves (in place by the square-root maps) and the 35 zero words must end up
holding `(u, v)`. A divstep drops one coefficient of `g` per step and needs its quotient `c` and its swap bit later (the reverse pass, and
the synthesis of `(u, v)` from the quotients). Counting words is fine (`f` plus `g` plus quotients stay at 36), but:

1. **Parking slots are data dependent.** After a swap the shorter array moves into `f` and the other shrinks, so the freed top word that
   would hold the quotient belongs to a different array than the one whose top is free after a non-swap step (a 17-word `g` no longer fits
   in the array whose top two words hold earlier quotients). The published design avoids this with polynomial (top-degree) Euclid and
   fixed blocks; we have only found the constant-time divstep form so far.
2. **No invariant like `g[0] b = 1` is known** that would let the swap bit and quotient be recomputed from the after-state, as in our BM decoder.
3. **Quotient erasure during synthesis.** Building `(x, y) -> (z x + c y, y)` consumes `c`, but `c = x'(0) / y(0)` is recoverable only when
   `y(0) != 0`.
4. Storing the history out of place (36 quotients plus 36 swap bits, 468 qubits) would raise `Q` by 25% and wipe out the gain (`Q^2` +56%
   against `T` -23%): checked, a loss. A second BM run on the series `O*/E*` needs about +430 qubits: also a loss.

## Next steps

* Find the fixed-slot formulation (top-degree Euclid with padding, or divsteps with the freed word chosen by the swap flag and a controlled
  relabelling) and prototype it classically, counting the words written at every step and proving the reverse recovers `c` and the swap.
* Only then the quantum generator: Euclid in place, synthesis into `S_35 .. S_69`, scan, and the undoing; small instances first.
