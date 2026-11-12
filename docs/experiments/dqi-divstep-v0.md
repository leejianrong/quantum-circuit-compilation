# DQI: our own divstep decoder, first version (QCC-19)

`src/dqi_gen/decoder.py` (stage 1 of ADR-0009: paper, host reference builder, standard algorithms; no public
circuit file was read). It replaces the reference's synchronized Euclid by constant-time division-free
steps ("divsteps", Bernstein-Yang; the paper's "Dialog" idea, arXiv:2510.10967 section II B 3) and replaces
the per-position Itoh-Tsujii inversion by a GF(2^6) tower. Everything is checked with the official verifier.

## Design

**Key equation.** Run `n = 2t` divsteps on `(f, g) = (1, S(z))`, `S(z) = sum s_i z^i`, `delta0 = 1`. Step:
if `delta > 0` and `g(0) != 0` swap `f, g` and set `delta = -delta`; then `g <- (g - (g(0)/f(0)) f) / z`,
`delta += 1`. Classical check (3,000 random syndromes per size, weights 0..t): after `n` steps the Bezout row of
`g` is `(Omega, sigma)` up to one nonzero scalar, so `sigma S = Omega mod z^n` with the right degrees.

**Rows, not polynomials.** We never store `f` and `g`. With `z^k g_k = u_g + v_g S` (same for `f`), the only
quantities a step needs are `g_k(0) = [z^k](u_g + v_g S)` and `f_k(0)`. Measured: `deg u_g < k` always, so
`g_k(0) = [z^k](v_g S)` (a convolution against the read-only syndromes) and `f_k(0)` is one 12-qubit register
`b` that changes only on a swap. Registers: `v_g` (t + 1), `v_f` (relabelled up by `z` each step, static),
`b`, a small signed `delta`, and per step the quotient `c = d/b` and the swap bit (the dialog, 70 x 13 qubits).
`Omega = sigma S mod z^t` is computed once (t(t+1)/2 products) and cleared by measurement, so the u rows
(half of the first version's registers and Toffolis) are gone.

**Reversible control.** `delta` is stored with an offset; the swap is a controlled swap of the rows and of
`(d, b)` followed by `c = d/b` in either case (after the swap `d/b` is `b_old/d`), so there is no branch.
`D = c b` holds in both cases, so `d` clears by measurement. The reverse pass recomputes `D = c b` (one
product), undoes the row update, clears `c` by measured uncomputation, and clears the discrepancy register by
X-basis measurement with a phase fix `sum <m, v_i s_{k-i}>` through `gf2_phase_by_product`: no Toffolis, so the
reverse pass is about 35% cheaper than the forward pass.

**Chien + Forney.** Per position the coefficients are scaled in place by constants (CNOTs), `sigma(z)`,
`sigma'(z)` and `Omega(z)` are CNOT sums, a 12-bit ladder flags `sigma(z) = 0` (12 Toffolis, uncomputed by
measurement), and the phase is `<M_j, Omega / sigma'>`. Division uses `GF(2^12) = GF(2^6)[y]/(y^2 + y + b)`
(`tower.py`): `1/a = conj(a) / N` with `conj` linear and `N = A^2 + AB + bB^2` in GF(2^6). The basis change
is a fixed 12x12 F2 matrix applied in place by CNOTs. Per position: one norm product, one GF(2^6) inversion,
two products with the (flag-gated) inverse, and a free `gf2_phase_by_product`: 21 + 63 + 42 + 6 + 11 =
143 Toffolis, against 351 for Itoh-Tsujii in GF(2^12).

## Results (official verifier, 3,072 shots, zero failures everywhere)

| instance | reference Q, T | Q2T ref | our Q, T | our Q2T | ratio |
|---|---|---:|---|---:|---:|
| tiny 15,4,4 | 115, 22,090 | 2.92e8 | 129, 1,122 | 1.87e7 | 15.6x better |
| small 63,10,6 | 229, 93,542 | 4.91e9 | 360, 9,246 | 1.20e9 | 4.1x |
| medium 255,20,8 | 462, 326,559 | 6.97e10 | 846, 43,010 | 3.08e10 | 2.3x |
| large 1023,40,10 | 972, 1,558,907 | 1.47e12 | 1,976, 271,447 | 1.06e12 | 1.4x |
| narrow 71,70,12 | not run | | 4,013, 609,015 | 9.81e12 | |

`narrow` is the benchmark's `n` and field with only 71 positions (about 6.7M ops, fits this laptop): it
also passes 25,600 shots, with mean error weight 29.3 and P(weight 35) = 1%, so the full t = 35 decoding
path over GF(2^12) is exercised. Odd degrees (the 511,30,9 check) use the Itoh-Tsujii fallback and pass too.

Full-size static costs (the verifier averages executed gates, equal within 0.1% here):

| stage | Toffolis |
|---|---:|
| forward divsteps | 339,150 |
| Omega | 39,690 |
| Chien + Forney (4095 x 143, before the second tower level) | 585,585 |
| reverse divsteps | 220,010 |
| total | about 1.18M (reference 5.73M) |

Qubits 4,013 (reference 1,893): syndromes 840, `v_g` 432, `v_f` 1,272, dialog 910, Omega 420 (only during
Forney), the rest `b`, `delta`, Forney scratch. Static `Q^2 T` is about 1.9e13 against the reference's
2.05e13, so this first version is only about 8% better than the baseline by itself: Toffolis are 4.8x
fewer, but qubits are 2.1x more and they are squared.

A second tower level for the norm inversion (GF(2^3) over GF(2^6); 28 Toffolis instead of 63) was added
afterwards: 108 per position, so the Chien + Forney stage is 442k and the total about 1.04M Toffolis;
static `Q^2 T` about 1.68e13, 18% below the reference's 2.05e13 (the `narrow` row above is this version:
606,530 Toffolis, 4,013 qubits).

## Full-size verification (Kaggle, official verifier, RS(4095, 4025) over GF(2^12))

Kernel `notebooks/dqi_gen/run.py` builds the circuit and runs `verify` at 102,400 shots per salt. The version
before the second tower level (static 1,184,435 Toffolis, 4,013 qubits, 44M operations) **passed under three
salts with zero failures** (script exit 0 means every `verify` returned PASS; the verifier raises on any
`eps_plus >= 1/16`), 417 s wall for build plus three salts, 4.5 GB peak child RSS, so a four-worker Kaggle
verify of our circuit needs about half the memory of the baseline. That run did not record the per-salt cost
lines (stdout was not captured); the runner now keeps them. A rerun on the final version with five salts was
queued on Kaggle and had not started when this was written, so the final-version full-size cost is not yet in
the ledger. Expected from the static count with `R = 1.19`: about `1.19 x 4013^2 x 1.04M = 2.0e13`, i.e. a
ratio near 1.2 against the baseline's 2.44e13 (not an official number).

## What did not work or was not tried

- A first version tracking the `u` rows too verified (5,275 qubits, 2.37M Toffolis) but was 3.2x worse than the
  baseline on `Q^2 T`; dropping them cut qubits by 24% and Toffolis by half.
- Per-position division cannot use data-dependent skipping (`sigma = 0` is a quantum condition).
- Evaluating the phase through power sums and the linear recurrence of the extended syndromes (no per-position
  inversion) needs about 35 products per position (about 2,200 Toffolis): worse than 143.

## Next levers

1. **Qubits (squared).** The 4,013 are 840 read-only syndromes plus about 3,170 of state. The public frontier
   at about 892 qubits implies the key-equation state lives in or beside the syndrome registers, since
   `S <-> (sigma, Omega)` is a bijection on decodable syndromes. Our `v_f` relabelling garbage
   (data shifted past index t, 1,272 qubits) and the dialog (910) are the largest pieces.
2. Forney: 143 per position. A second tower level for the norm inversion (GF(2^3) over GF(2^6)) saves about
   35 more (about 0.14M Toffolis); the 11-Toffoli flag and the 21-Toffoli norm product are next.
3. Divsteps: row update is 57% of the key-equation Toffolis (about 36 products per step).

Reproduce: `QCC_DATA=data uv run python -m dqi_gen.instances --gen divstep --instance narrow`
(seconds), `... --instance full` on Kaggle (`notebooks/dqi_gen/run.py`).
