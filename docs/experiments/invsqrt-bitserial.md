# invsqrt: split phase, serial phasing and a centered remainder (QCC-13)

Goal: close the gap to the public 62-qubit circuit (cost 94,599.6, ratio 21.95) from our 136-qubit generator
(296,738.6, ratio 7.00) using the two structural observations logged in `docs/PROVENANCE.md` ("Ideas learned",
ADR-0009 stage 2): phase the value one bit at a time through a single working qubit, and phase a coarse word
and a fine word separately. Both are implemented fresh in `src/invsqrt_gen/split.py`; no gate list, table or
constant comes from a public circuit.

**Result: 121 qubits, cost 247,262.49, ratio 8.40, 5 of 5 salts pass with the identical cost (E016). The frontier
(ratio 21.95, 3.1x better than the 7.00 we started from, 2.6x better than this build) is not reached.** The two
observations do not pay by themselves in our architecture (a measured wash and a measured loss); what pays is a
different change they led to, the centered remainder, plus tuning the register widths to the accuracy boundary. The
numbers below say why, and where the rest of the gap must come from. Nothing here touches `best/`; promotion is the
owner's step through the gate.

| Build (experiment) | Qubits | Toffolis | Rotations | Predicted cost | Verifier |
|---|---:|---:|---:|---:|---|
| Baseline generator, 30,20,11 g4 (E007) | 136 | 1,949 | 33 | 297,058 | 296,738.6, 5 salts |
| Complement split, 30,20,11 g4 (E012) | 129 | 1,986 | 44 | 297,442 | screen 296,058 |
| Centered, serial coarse phase, 29,19,10 g3, unpolished (E013) | 123 | 1,785 | 45 | 259,552 | screen 259,212 |
| Centered, barrel, 29,19,10 g3, polished (E014) | 123 | 1,752 | 45 | 254,380 | screen 254,380 |
| Centered, barrel, 28,19,10 g2, polished (E015) | 122 | 1,716 | 45 | 250,038 | 250,037.98, 2 salts |
| Centered, barrel, 28,19,9 g2, polished (E016) | 121 | 1,710 | 45 | 247,262 | 247,262.49, 5 salts |

The columns are `--a 7 --frac f0,f1,f2 --guard g` (and `--centered --polish` from the third row on). Screens run 1/20
of the shots, one salt: they confirm correctness and never gate promotion. The cost is deterministic: the screens
and the full runs of the same circuit agree to the last digit.

## Predicting the cost

`src/invsqrt_gen/predict.py` computes the verifier's cost without running it: `Q` from the circuit, Toffolis from
the static count (no Toffoli sits under a measurement condition, so static = executed), and the rotation T cost from
the model error. The margin `min f(x) (2^-24 - rel(x))` over the inputs `x <= 3,133,452` fixes
`eps = pi margin / n_rot` and each rotation costs `0.56 log2(1/eps) + 5.3` T. Counting only the inputs the verifier
runs (2,350,089 of the 4,194,304 normalised ones) made the prediction exact: it reproduces 247,262.4885,
250,037.98 and 254,379.6 to every printed digit (before that fix it was 0.6% high). The accuracy gate is the same
set: `rel(x) < 2^-24` for every reachable `x`.

## Design 1: split phase (observation 2)

`V_0 = c_0 - P` held `c_hi` (the top `a = 7` bits, a table output of the address alone) and a borrow qubit for
the whole Horner stage. Phases add, so split `V_0` into a coarse word and a fine word:

* Complement form (`build_split`, `Params(ceil=True)`): the table stores `n = 2^K - c_lo` (`K = f_0 - a`), the Horner
  register ADDS the product, `T = n + P < 2^(K+1)`, and `V_0 = (c_hi + 1) 2^K - T` exactly. The coarse word
  `c_hi + 1` is loaded in the same unary-iteration pass, phased with positive angles, and cleared at once by a
  measurement-based lookup (about 25 Toffolis); the fine word `T >> guard` is phased with negative angles. The model
  phases `ceil(V_0 / 2^guard)`.
* The Horner stage then has no high part, no borrow qubit and no controlled decrement.

Measured (a = 7, frac 30,20,11, guard 4): 129 qubits (-7), 1,986 Toffolis (+37), 44 rotations (+11). The rotations
rise because the two words occupy overlapping position ranges once shifted by `s` (the coarse word's positions
`17 .. 35` and the fine word's `0 .. 28`), so about 12 positions are rotated twice; this is the overlapping angle
range seen in the public circuit, and its cost is the point. Predicted 297,442, screen 296,058: **neutral**. The 7
qubits (about 110 Toffoli-equivalents) are paid back by 37 Toffolis and 11 rotations (about 80 Toffoli-equivalents)
plus the second shifter.

## Design 2: one working qubit (observation 1)

`serial_phase` phases the coarse word without a shifted register: a one-hot of `s` (about 18 Toffolis, cleared by
measurement), then for every angle position `k` one working qubit receives `XOR_s' [s = s'] c_{k-s'}` (one Toffoli
per term), takes the rotation, and is measured; the fix-up is a conditional CZ per term, which costs nothing.
No headroom qubits and no unshift. It costs +33 Toffolis over the barrel shifter (1,785 against 1,752 on the
centered build) because a nine-bit word has 9 x 11 terms against 42 controlled swaps. The headroom it saves is not
at the qubit peak (the Horner stage is). **Loss of 1.6%** (predicted 259,552 against 255,493). It would only pay if
the word being phased were produced bit by bit by an adder (never stored), which our architecture does not do.

## Design 3: the centered remainder (what paid)

Expand each segment about its middle: the Horner variable is `rho = r - 2^13`, a 14-bit two's complement number
(the top bit of `r` inverted by one `X`). Consequences, all measured:

* A radix-4 Booth recoding of a 14-bit two's complement number has 7 digits, not 8 (the 8th digit only recoded the
  top bit of the unsigned `r`, and was the widest row). Step 0 has 7 rows and step 1 has 5 (was 7).
* Every product is one bit smaller (`|rho| < 2^-8`), and the quantised coefficient errors enter as `rho^j` instead
  of `r^j`, so `V_1` and `V_2` lose one and two bits at the same accuracy: the model error at (30, 20, 11) is
  2^-24.53 against 2^-24.17.
* `V_0` needs no borrow: with `|P| < 2^21` the table stores `W = (c_0 mod 2^22) + 2^21` in a 23-bit window and the
  coarse word `CW = (c_0 >> 22) 2^22 - 2^21` absorbs the offset, so `V_0 = CW + W - P` exactly, the window is the
  register, and `CW >> guard` is a nine-bit table word (`2 (c_0 >> 22) - 1`).
* The middle levels hold `c_j mod 2^K` in `lo`, `(c_j >> K) - 1` in `hi`, and a one in the first of two extra window
  qubits (the signed product moves the window to `lo + 2^K - Q`, which stays inside `[0, 2^(K+2))`); one small
  `iadd(ext, hi)` finishes the high part.

Per-stage Toffolis of the 123-qubit build (forward + back): normalise 105 + 105, lookup 254 + 50 (clears), coarse
84, Horner step 1 134 + 134 + 16, step 0 353 + 353, fine 164. Against the baseline's 421 + 421 for step 0, the
centered step is 16% cheaper. At the baseline widths (30, 20, 11, guard 4) the centered build is 128 qubits and
1,860 Toffolis (278,393); the narrower widths it allows take it to 123 qubits and 1,752 Toffolis.

## Error analysis (the 2^-24 gate)

The verifier requires `|theta - target| <= 2^-24 / sqrt(x)` turns for every `x`, and spends what is left on the
rotations. The generated circuit equals its bit-exact model (`tests/unit/test_invsqrt_split.py` checks the phase of
simulated shots against `model_y` exactly), so the exhaustive error over all normalised inputs is known before
any run: `rel = max |Y_model - Y| / Y`. Where it comes from, at (a, frac, guard) = (7, (28, 19, 9), 2):

* The unquantised degree-2 polynomial on a segment of width 2^-7 has relative error 2^-27.7, 3.7 bits below the
  budget. The slack cannot be spent on a smaller table: `a = 6` multiplies it by 8 (2^-24.7, which alone is 61% of the
  tolerance) and needs a ninth Booth row.
* The budget goes on the rounding of the coefficients `c_1, c_2` (entering as `rho`, `rho^2`), one floor per Booth
  digit (7 + 5 floors, which is why the guard bits exist), the final floor to `wy = 26` bits, and the fit.
* `fit_tables` does coordinate descent, then (`--polish`) an exhaustive joint `+-1` search on `c_1, c_2` per segment
  with `c_0` recentred; polishing is worth 0.1 to 0.3 bits and is what puts the narrow widths inside the gate.
  `--reachable` fits only the inputs `x <= 3,133,452` produce (another 0.04 to 0.12 bits; it does not move the
  best configuration).

Boundary probes (a = 7, centered, polished unless marked `u`; `model` is the error over all inputs, `reach` over
the reachable ones, and the build is feasible only when `reach < 2^-24` leaves a rotation margin):

| frac f0,f1,f2 | guard | model error | feasible | predicted cost |
|---|---:|---:|---|---:|
| 30,20,11 u | 4 | 2^-24.53 | yes | 278,393 |
| 30,19,9 u | 4 | 2^-24.06 | yes | 264,015 |
| 30,18,9 u | 4 | 2^-23.41 | no | |
| 29,19,10 | 3 | 2^-24.27 | yes | 254,380 |
| 29,19,9 | 3 | 2^-24.18 | yes | 252,504 (before the reachable fix) |
| 29,18,10 | 3 | 2^-23.72 | no | |
| 29,19,10 u | 4 (`wy` 25) | 2^-23.53 | no | |
| 28,20,10 | 2 | 2^-24.19 | yes | 258,426 (before the reachable fix) |
| 28,19,10 | 2 | 2^-24.01 | yes | 250,038 |
| **28,19,9** | **2** | **2^-24.01** | **yes** | **247,262** |
| 28,19,8 | 2 | 2^-23.72 (reach 2^-23.84 with `--reachable`) | no | |
| 28,18,9 | 2 | 2^-23.57 (reach 2^-23.62) | no | |
| 28,19,10 u | 3 (`wy` 25) | 2^-23.40 | no | |
| 27,19,10 | 1 | 2^-23.36 | no | |
| 27,19,9 | 1 | 2^-23.43 (reach 2^-23.49) | no | |

`wy = 26` is a hard floor (`wy = 25` fails at the widths tried, unpolished), the guard stops at 2, and (28, 19, 9) is the
narrowest set that passes. One more qubit costs about 0.8% and one more Toffoli 0.04%, so the remaining widths are
worth little: a perfect fit would gain about 1.5%.

## Why the gap is still 2.6x, and the next lever

The frontier has 62 qubits and 1,393 static Toffoli-like gates, including only 205 controlled swaps (aggregate
statistics from `docs/experiments/invsqrt-cost-drivers.md`). Our normalise and un-normalise alone are 210 controlled
swaps and tests; the two phase shifters add 248 more. So the public circuit applies the factor `2^s` without a
barrel shifter (the observation-1 route, a multiplexer into one working qubit, costs more Toffolis than our shifter,
so its saving must come from somewhere else: no stored phased word at all), and holds about 40 qubits above `x`
against our 99. Our qubit peak is the widest Booth row: `x` 22, flags 5, `V_0` 21, `V_1` 21, `V_2` 9, operand
register about 20 and carries about 21. The rotations are 16% of the cost (45 at about 30 T each, since the margin is
2^-39.6 turns), and the overlapping ranges of the two words account for 12 of them.

Levers costed on paper and not built (Toffoli-equivalents; one qubit is worth about 16 of them, because `Q C` moves
by 1/Q per qubit and 1/C per Toffoli):

| Idea | Effect | Verdict |
|---|---|---|
| Phase gradient register (add rows into a catalyst, no `V_0`, no mirror of step 0) | -430 Toffolis, but prep and unprep rotations of 36 qubits cost +520 and the shifts +70 | no gain |
| Operand-less rows (recompute the AND in the down-sweep) | -21 qubits, +340 Toffolis | wash |
| Split the carry chain in two | -11 qubits, +1 Toffoli per bit of the add | loss |
| Reload `V_2` for the mirror (clear by measurement during step 0) | -10 qubits, +279 Toffolis | loss |
| Deferred carries (add rows only over their operand window, sum the carry-outs once) | -70 Toffolis, but each signed row needs two pending qubits (+16 at the peak) | loss |
| Radix-8 | -17% of the products, +22 qubits for `3V` | loss |
| Degree 3 with `a = 6` | -127 lookup, +step 2 and a ninth row | loss |
| Rounding instead of flooring each Booth slice (carry-in from the dropped bit) | about half the floor error, so one guard bit, for +2 Toffolis per row | wash |

The next lever is therefore to remove the stored phased word and the barrel shifters together: a design where the
last accumulation is a phase adder (carries computed up, sum bits rotated while the carries are cleared, no
register written) and the factor `2^s` is applied by selecting which sum bit meets which rotation. That needs a
different Horner ending (the rows must land in a streaming adder) and a way to keep the Booth operand register
below 20 qubits; neither has a design yet.
