# invsqrt: split phase, serial phasing and a centered remainder (QCC-13)

Goal: close the gap to the public 62-qubit circuit (cost 94,599.6, ratio 21.95) from our 136-qubit generator
(296,738.6, ratio 7.00) using the two structural observations logged in `docs/PROVENANCE.md` ("Ideas learned",
ADR-0009 stage 2): phase the value one bit at a time through a single working qubit, and phase a coarse word
and a fine word separately. Both are implemented fresh in `src/invsqrt_gen/split.py`; no gate list, table or
constant comes from a public circuit.

**Result: predicted ratio 8.25 at 122 qubits (cost 251,644); the screens of the neighbouring builds passed with zero
failures and matched the prediction to 0.2%. The frontier (ratio 21.95) is not reached.** The two observations do not
pay by themselves in our architecture (a measured wash and a measured loss); what pays is a different change they
led to, the centered remainder. The numbers below say why, and where the rest of the gap must come from. The
full multi-salt run of the final build is in the ledger (experiment E011) and the owner's promotion gate decides
what happens next; nothing here touches `best/`.

| Build (experiment) | Qubits | Toffolis | Rotations | Predicted cost | Verifier |
|---|---:|---:|---:|---:|---|
| Baseline generator, 30,20,11 g4 (E007) | 136 | 1,949 | 33 | 297,058 | 296,738.6, 5 salts |
| Complement split, 30,20,11 g4 (E008) | 129 | 1,986 | 44 | not computed | screen 296,058 |
| Centered, serial coarse phase, 29,19,10 g3, unpolished (E009) | 123 | 1,785 | 45 | 259,552 | screen 259,212 |
| Centered, barrel, 29,19,10 g3, polished (E010) | 123 | 1,752 | 45 | 254,896 | screen 254,380 |
| Centered, barrel, 28,19,10 g2, polished (E011) | 122 | 1,716 | 45 | 251,644 | see ledger |

Screens run 1/20 of the shots, one salt: they confirm correctness and the prediction, and never gate promotion.

## Predicting the cost

`src/invsqrt_gen/predict.py` computes the verifier's cost without running it: `Q` from the circuit,
Toffolis from the static count (no Toffoli sits under a measurement condition, so static = executed), and the
rotation T cost from the model error: the margin `min f(x) (2^-24 - rel(x))` over the largest inputs fixes
`eps = pi margin / n_rot` and each rotation costs `0.56 log2(1/eps) + 5.3` T. For the E007 baseline it predicts
297,058 against the verified 296,738.6 (0.1%); every prediction below was within 0.3% of the screen run.

## Design 1: split phase (observation 2)

`V_0 = c_0 - P` held `c_hi` (the top `a = 7` bits, a table output of the address alone) and a borrow qubit for
the whole Horner stage. Phases add, so split `V_0` into a coarse word and a fine word:

* Complement form (`build_split`, `Params(ceil=True)`): the table stores `n = 2^K - c_lo` (`K = f_0 - a`), the Horner
  register ADDS the product, `T = n + P < 2^(K+1)`, and `V_0 = (c_hi + 1) 2^K - T` exactly. The coarse word
  `c_hi + 1` is loaded in the same unary-iteration pass, phased with positive angles, and cleared at once by a
  measurement-based lookup (about 25 Toffolis); the fine word `T >> guard` is phased with negative angles. The model
  phases `ceil(V_0 / 2^guard)`.
* The Horner stage then has no high part, no borrow qubit and no controlled decrement.

Measured (a = 7, frac 30,20,11, guard 4): 129 qubits (-7), 1,986 Toffolis (+37), 44 rotations (+11).
The rotations rise because the two words occupy overlapping position ranges once shifted by `s`, so about 12
positions are rotated twice (this matches the overlapping angle ranges seen in the public circuit). Predicted
297K, screen 296,058: **neutral**. 7 qubits (1.1K Toffoli-equivalents each 16) are exactly paid back by 37 Toffolis
and 11 rotations (about 80 Toffoli-equivalents) plus the second shifter.

## Design 2: one working qubit (observation 1)

`serial_phase` phases the coarse word without a shifted register: a one-hot of `s` (about 18 Toffolis, cleared by
measurement), then for every angle position `k` one working qubit receives `XOR_s' [s = s'] c_{k-s'}` (one Toffoli
per term), takes the rotation, and is measured; the fix-up is a conditional CZ per term, which costs nothing.
No headroom qubits and no unshift. It costs +33 Toffolis over the barrel shifter (1,785 against 1,752 on the
centered build) because a nine-bit word has 9 x 11 terms against 42 controlled swaps. The headroom it saves is not
at the qubit peak (the Horner stage is). **Loss of 1.6%** (predicted 259.6K against 255.5K). It would only pay if
the word being phased were produced bit by bit by an adder (never stored), which our architecture does not do.

## Design 3: the centered remainder (what paid)

Expand each segment about its middle: the Horner variable is `rho = r - 2^13`, a 14-bit two's complement number
(the top bit of `r` inverted by one `X`). Consequences, all measured:

* A radix-4 Booth recoding of a 14-bit two's complement number has 7 digits, not 8 (the 8th digit only recoded the
  top bit of the unsigned `r`, and was the widest row). Step 0 has 7 rows and step 1 has 5 (was 7).
* Every product is one bit smaller (`|rho| < 2^-8`), and the quantised coefficient errors enter as `rho^j` instead
  of `r^j`, so `V_1` and `V_2` lose one and two bits at the same accuracy: the model error at (30, 20, 11) is
  2^-24.53 against 2^-24.17, and (29, 19, 10) with guard 3 passes at 2^-24.27 after polishing.
* `V_0` needs no borrow: with `|P| < 2^21` the table stores `W = (c_0 mod 2^22) + 2^21` in a 23-bit window and the
  coarse word `CW = (c_0 >> 22) 2^22 - 2^21` absorbs the offset, so `V_0 = CW + W - P` exactly, the window is the
  register, and `CW >> guard` is a nine-bit table word (`2 (c_0 >> 22) - 1`).
* The middle levels hold `c_j mod 2^K` in `lo`, `(c_j >> K) - 1` in `hi`, and a one in the first of two extra window
  qubits (the signed product moves the window to `lo + 2^K - Q`, which stays inside `[0, 2^(K+2))`); one small
  `iadd(ext, hi)` finishes the high part.

Result at (a, frac, guard) = (7, (29, 19, 10), 3), polished: 123 qubits, 1,752 Toffolis, 45 rotations, predicted
254,896 (ratio 8.15). Per-stage Toffolis (forward + back): normalise 105 + 105, lookup 254 + 50 (clears), coarse
84, Horner step 1 134 + 134 + 16, step 0 353 + 353, fine 164. The accuracy sweep then moves the guard to 2
(`--frac 28,19,10 --guard 2`, polished, model error 2^-24.01): 122 qubits, 1,716 Toffolis, predicted 251,644
(ratio 8.25). `(29, 19, 9)` with guard 3 also passes (2^-24.18, predicted 252,504); `(28, 19, 9)` and anything below
`(28, 19, 10)` at guard 2, or guard 1, is addressed in the table of boundary probes below.

## Error analysis (the 2^-24 gate)

The verifier requires `|theta - target| <= 2^-24 / sqrt(x)` turns for every `x`, and spends what is left on the
rotations. The generated circuit equals its bit-exact model (`tests/unit/test_invsqrt_split.py` checks the phase of
simulated shots against `model_y` exactly), so the exhaustive error over all `2 * 2^21` normalised inputs is known
before any run: `rel = max |Y_model - Y| / Y`. Its parts, in units of the phased word (`2^-wy`, `wy = 26`):
coefficient rounding (each `c_j` to `2^-f_j`, entering as `rho^j`), one floor per Booth digit (up to 7 + 5 units of
`2^-f_0` and `2^-f_1`, which is why the guard bits exist), the final floor to `wy` bits (half a unit), and the
minimax truncation of the degree-2 polynomial (about 2^-25.4 at a = 7). The table fit does coordinate descent and an
exhaustive `+-1` joint search (`--polish`), then recentres `c_0`. The sweep boundary is sharp: dropping any one of
`f_0, f_1, f_2` below (29, 19, 10) or the guard below 3 leaves less than 2^-24 (2^-23.9 or worse), and the
verifier then has no tolerance left for the rotation synthesis error.

## Why the gap is still 2.6x, and the next lever

The frontier has 62 qubits and 1,393 static Toffoli-like gates, including only 205 controlled swaps. Our
normalise and un-normalise alone are 210 controlled swaps and tests; the two phase shifters add 248 more. So the
public circuit applies the factor `2^s` without a barrel shifter (the observation-1 route, a multiplexer into one
working qubit, costs more Toffolis than our shifter, so its saving must come from somewhere else: no stored phased
word at all), and holds about 40 qubits above `x` against our 101. Our qubit peak is the widest Booth row:
`x` 22, flags 5, `V_0` 22, `V_1` 21, `V_2` 10, operand register 20 and carries 21.

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

The next lever is therefore to remove the stored phased word and the barrel shifters together: a design where the
last accumulation is a phase adder (carries computed up, sum bits rotated while the carries are cleared, no
register written) and the factor `2^s` is applied by selecting which sum bit meets which rotation. That needs a
different Horner ending (the rows must land in a streaming adder) and a way to keep the Booth operand register
below 20 qubits; neither has a design yet.
