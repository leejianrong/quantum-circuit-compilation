# invsqrt by square root and division: the 46-qubit design re-derived (QCC-13)

Source studied (read-only, nothing executed): the public invsqrt circuit of Syed Asad Ali (Apache-2.0, Kaggle dataset
`syed3000/vqcc-own-circuit-portfolio` v12, sha256 `321aff836362...`; verified by us at 80,162.7 on 10 salts, see
`docs/research/uncompute-coulomb.md`), its builder sources and the walkthrough
`manwithacat/fortysix-where-the-16-qubits-went`. Everything below is re-derived in our words; the numbers marked
*measured* come from running the circuit in the kickmix simulator on 1,500 inputs and reading the qubits at the
stage boundaries (same method as `invsqrt-onepass.md`). The model is `src/invsqrt_gen/sqrtdiv.py`.

## The idea in one paragraph

Our Horner family keeps a wide table (about 47 qubits) next to the data and spends carries on wide adds. This design
keeps almost no table. It finds a 12-bit square root `s` of the normalised input in place, so that `n = s^2 + small`,
uses a one-coefficient first-order correction `1 - P` for the small part, and gets `1/sqrt(n) = (1 - P) / s` by a
non-restoring division whose quotient digits go straight into the rotations. State above the 26-qubit body (22
input qubits plus 4 shift flags) is about 20 qubits instead of 70.

## Derivation (ours)

1. **Normalise by even shifts.** `x` in `[1, 3,133,452]` (22 bits). Shift left by `2k`, `k` in 0..10, so that
   `n = x 4^k` lies in `[2^20, 2^22)`; keep `k` in 4 flag qubits. Then `1/sqrt(x) = 2^k / sqrt(n)` and the phase is
   `2^(k-10) Y` turns with `Y = 1/sqrt(N)`, `N = n / 2^20` in `[1, 4)`. The flags are four zero tests of the leading
   16, 8, 4, 2 bits with the shifts done by controlled swaps (the Coulomb-style iterative flags; about 51 Toffolis).
2. **Root in place.** `R = isqrt(16 n)` in `[4096, 8192)`, `v = R - 4096` (12 bits). *Measured:* after the root stage
   the 22 input qubits hold `v` in the top 12 and `h = (16 n - R^2 - R - 1) >> 4` as a signed 10-bit number in the
   low 10, exactly, on all 1,500 inputs. Write `t = 16 n - R^2 - R - 1`; `t` lies in `[-R-1, R)`, its low four bits are a function of
   `R mod 16`, so `(v, h)` is a bijective image of `n` (22 bits in, 22 bits out: the root consumes the radicand
   digit pair by digit pair, so the register never grows). A non-restoring digit recurrence costs about
   `sum_j (j + 2)` for 12 digits, 96 Toffolis forward, the same again to undo (stage Toffolis reported by the walkthrough: 96 and 96).
3. **First-order correction.** With the centred root `s = (2R + 1) / 2^13` we have `N = s^2 + (t + 3/4) / 2^24`, so
   `1 / sqrt(N) = (1 - eta/2 + 3 eta^2 / 8 - ...) / s` with `eta = (t + 3/4) / (2^24 s^2)`, `|eta| <= 2^-12`. Keeping only
   `P = D (t + 3/4)` with `D = 1 / (2 s^2 2^24)` leaves a relative error of 2^-25.42 over all 2,350,089 reachable
   inputs, and 2^-26.42 once the one-signed bias of the dropped `3 eta^2 / 8` is centred by a constant (exact
   numbers: `invsqrt_gen.sqrtdiv.worst_error_bits`). So no second-order term is needed.
4. **One small table.** `D` is a smooth function of `v`: `D ~ D0[a] + D1[a] u` with `a` the top 7 bits of `v` (128
   rows) and `u` the low 5 bits (a five-row add, the "coefficient" stage). With `D0` at `2^-38` and `D1` at `2^-44`
   the end-to-end error (exact product and division) is 2^-25.0 (centred 2^-25.4); `D0` at `2^-36` already fails
   (2^-23.9). An 8-bit address does not help (2^-25.0). The product `P = D (t + 3/4)` is a 17 x 15 bit multiplier but only
   the top 14 bits of `P` (`P < 2^-12`, resolution `2^-26`) matter, which is why the reference product is reported at 103
   Toffolis, not 250. The four low bits of `t` are a tiny table of `R mod 16` (the "metadata" wires).
5. **Division.** `Y = (1 - P) 2^13 / (2R + 1)`, quotient in `(1/2, 1]`. A non-restoring division, 24 rows, one
   add-or-subtract of the 14-bit divisor per row (about 11 Toffolis per row; the walkthrough reports 270 forward), gives signed
   quotient digits `d_j = +-1`; the digit is the sign of the running remainder, so it costs nothing to produce.
6. **Phase.** `Y = sum_j d_j 2^-j` plus constants; the rotations act on the digit qubits (angle `2^(k-10-j)` for
   digit `j`). `k` changes which digit meets which angle: the circuit routes digits to one working qubit with
   controlled swaps by the flags (63 CSWAPs, one wire takes 8 in sequence) and rotates it, 33 rotations in all (our own
   count for the same budget below). The constant parts of the sum are folded into the same routing.
7. **Undo.** Division rows back (323, with part of the quotient history retired and rebuilt), product, coefficient,
   table clean-up by measurement with a Clifford phase repair (about 6 Toffolis in the repaired block), root back
   (96), normalisation back (43). The table is loaded twice (first load 56 Toffolis, second 70) instead of held.

## Where the 46 qubits come from (walkthrough, widths checked by our own liveness count)

Body 26 (`v` 12, `h` 10, flags 4). The first table load peaks at 46 with 20 working wires (13 coefficient and 3
metadata bits are alive at its end). The coefficient wires are measured away (width 45 to 33) before the divider,
which carries a 14-bit remainder and the quotient history in the other 20 wires. Peak runs of 46 are short and
scattered (391 runs): the width is the sum of many small patches, not one trick. Our Horner design needs 70+ qubits
there; the saving is the algorithm, not the layout.

## Our error budget for this design

Relative budget `2^-24` of the phase. Contributions (worst case, all inputs): first-order truncation 2^-26.4
(centred), `D` quantisation 2^-25.4 (7-bit rows, 38 and 44 fractional bits), `P` rounding to `2^-26` absolute
(about 2^-26.3 of `Y`), quotient truncation `2^-26` (24 digits, last row exact), constant offsets from rotation angle
rounding handled as in `angles.py`. These add to about 2^-24.5 in the worst case before tuning, which leaves
0.5 bit for the rotation margin; they are not independent, and the error of the final circuit is measured, not
summed. The 33 rotations match the reference's count because the angle set is the same: one per 2^-j from the
largest used `2^(k-11)` down to the 2^-35 turn level.

## Cost expectation for a first build

Forward Toffolis: normalise 51, root 96, table 126 (unary iteration over 128 rows, our existing lookup),
coefficient 40, product 100 plus the `R mod 16` term 40, division 270, phase 100. Mirror about the same (reference, as reported:
775 undo against 736 forward). Estimated 1,700 to 1,900 Toffolis plus 230 for rotations, at 65 to 75 qubits
(table held, not reloaded; all digits kept): 65 x 2,100 = 137k (ratio 15) against 168k today. Each qubit shaved by
reloading the table, retiring history digits and releasing carries early is worth about 38 Toffolis at the end state.

## Status

Model and tests in the repo (`sqrtdiv.py`, `tests/unit/test_invsqrt_sqrtdiv.py`). Circuit stages are next: normalise and
root first, each verified against the model in the kickmix simulator before the next is added.
