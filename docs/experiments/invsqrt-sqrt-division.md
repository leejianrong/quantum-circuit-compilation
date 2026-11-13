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

## Follow-up: what the reference's lifecycle looks like, and why a plain build does not pay (QCC-13)

Measured by running the 46-qubit circuit (kickmix simulator, 1,500 inputs, stage boundaries from the walkthrough):

* **Live width over the stages** (qubits holding a non-zero value for some input): 26 after the root, 42 after the first
  table load, 44 during the product, 31 right after the coefficient wires are measured away (op 6,720), 40 at the end of the
  divider (op 9,877), 42 at 10,668, 31 at 17,306 (after the divider clean-up), 45 at 26,132.
* **The phase endpoint rotates plain binary bits of `Y`.** For inputs with k = 5, the working wire at each of the 38
  `Z_POW` equals bit `e + k - 10` of `Y = 1/sqrt(n/2^20)` (or its recomputation for the low bits) for the bits that can be
  compared exactly (bits 1 to 16); the rotations come in two interleaved streams (angles 2^-4 up to 2^-17 and 2^-18 down to
  2^-31), so the quotient is a binary word of about 28 positions, not a signed-digit history. The wires carrying those bits
  include the former `h` wires q0 to q9 and the former root wires.
* **`h` is consumed in place.** During the product stage the wires q0 to q9 stop holding `h` (0.1% agreement at op 6,707)
  and part of the root wires change too (48% agreement): the product accumulates into rewritten `h` and root wires,
  and only 6 extra wires remain after the coefficient is measured away. So the reference never holds `v`, `h`, `P`, a
  remainder and 24 quotient wires side by side.
* **What a plain build costs.** With `h`, `P`, the remainder (15), 26 quotient bits, `v` (13), flags (4) and carries alive
  at once, our first-cut layout peaks near 86 qubits (the root stage alone is 42). At about 2,000 Toffolis plus 250 for
  rotations that is 86 x 2,250 = 193k, worse than E023 (168,237). The saving of the reference is therefore the in-place
  lifecycle of the product and divider (which wires are reused for what, and when), not the arithmetic count.

Consequence for the plan: the stages after the root should be built in the reference's lifecycle order, so the
next step is to decode that lifecycle (which registers the product, coefficient and divider rows read and write, by
tracking dependence of each wire on `v`, `h` and the table words across op ranges), not to build a wide first version. The
root stage (done, 102 Toffolis, 42 qubits) is common to both.

## Lifecycle decode of the reference, up to the product (QCC-13, study)

Method: 1,440 inputs with `k = 0` (60 root values `v`, 24 residuals `h` each), the circuit simulated to op 10,750 with a
snapshot every 50 ops; every wire at every snapshot is classified as an affine GF(2) function of the 22 bits of `(v, h)`
(a "frame"), or by constancy inside groups: `A` function of `v >> 5` only (table word), `V` function of `v` only, `N` also
depends on `h`, `0` zero. Plus gate statistics per stage (which wires are only controls, which are targets). Timeline
(ops; `.` zero):

```text
op        1.7k      2.4k        5.2k   5.6k    5.75k    6.0k     6.7k 6.75k      9.9k    10.7k
q0-q9    h ................................ h^h chain  N N N N N N N N N .  N N N N N  (in place: LSB first)
q10-q21  v .................... v (low bits u briefly A/V) ........ v ........ v / quotient bits
q26-q45  . A A A A A A A A A A V V V V V V V (13 wires D) N N N N N | 13 wires 0 | N N (6 wires) .. 18 wires N
         |load words, 1 wire at a time|  coefficient |  product    | measured away
temp     q42,q43 (and q7,q8): AND carries, zero between rows
```

What it shows (our reading):

* **Table words load onto 20 wires one by one** (class `A` appears wire by wire from op 1,750 to 2,650: 56 Toffolis and about
  6,500 CNOTs, the same in-place AND network as in `invsqrt-onepass.md` M5, here on 7 address bits).
* **The coefficient is refined in place** (`A` to `V` at 5,300 to 5,600): 13 of the loaded wires turn into `D(v)` using
  the low root bits, 44 Toffolis. While it runs, root wires `v0` to `v5` change frame (`v0 + v1`, `v1 + v2`, ...) and return
  to plain `v_j` by op 5,750: the low root bits are borrowed and given back, no wire is added.
* **The product is a consuming multiplier.** During 5,704 to 6,707 the only Toffoli targets other than the two AND
  carries (q42, q43, measured away after each use) are `q0` to `q7`, one each; the controls are the `D` wires and the `h`
  wires, with `h` control counts falling `9, 8, 7, 6, 5, 4, 3, 1`. The `h` wires turn `N` one after another from the
  least significant end (`q0` at 5,950 ... `q8` at 6,850) and stop being `h`. So the product accumulates into the wires that
  held its multiplier: a triangular in-place multiply, 103 Toffolis, giving the 16-wire word `P` (the 10 `h` wires plus 6).
* **Why that is reversible (our derivation).** Horner order, `acc <- 2 acc + h_i D`: if `D` is odd, `h_i` is the lsb of
  the new accumulator, so the old accumulator is `(acc - h_i D) / 2` and the multiplier bit needs no wire of its own. The
  dropped low columns of a truncated product are the only information that is lost; the reference measures them and repays
  the phase later (the 6,700 `CZ` of the clean-up). We have not built this.
* **Then `D` is measured away** (13 `HMR`, ops 6,707 to 6,720): width 44 to 31, `P` (16 wires), `v` (12) and the flags (4)
  remain, plus 0 to 3 wires of work. The table is loaded again for the undo (a different table, 70 Toffolis).
* **The divider's state is the same 16 wires plus a few** (31 live at 6,720 and 40 at 9,877): the quotient bits are not
  accumulated one wire per row. At the endpoint the wires holding the bits that are rotated include `q0` to `q9` (the former
  `h` wires) and `q26` to `q45`; the dividend wires are consumed as quotient bits appear, as the root consumes its radicand.

Redesign order that follows (register reuse first): (1) consuming root: done (102 Toffolis, peak 42 with its own temporaries);
(2) table load onto 16 wires and in-place coefficient refinement (peak 46: body 26 + 16 + 4 carries); (3) consuming multiplier with an
odd `D` (we must force `D` odd: one table bit); (4) measure `D` away; (5) consuming division of the 16-wire `P` by `2R + 1`
(open: what exactly produces 26 quotient bits in about 16 wires; the next dynamic experiment is the same classification
with `k` varied through the endpoint, 9,900 to 10,700); (6) rotations on the quotient wires through one working wire;
(7) undo in reverse with the table reloaded. A peak of 46 to 50 is plausible only if (5) works as in the reference;
until it is understood, no stage after the root is worth building.

## The divider and the deferred-phase adder (QCC-13, decoded and built as a gadget)

**Quotient bits appear one per row, in wires freed by the shrinking remainder.** Classifying every wire against the
binary digits of `Y` (inputs with `k = 0`, snapshots every 50 ops, ops 6,700 to 10,750): from op 7,000 a new wire
holds the complement of bit `y_3`, then `y_4`, `y_5`, ... one every 150 ops (one row each): the wires are first the former
table wires (q34, q36, q30, q32, q28, q35, q33, q31, q29, q26, q27, q37, q38 carry `y_3` to `y_15`), then the former `h` wires
(q6 down to q0 carry `y_16` to `y_22`), complemented until op 9,900 and plain at the endpoint. So the quotient is held as
one wire per digit (20 of them by op 9,650), while the remainder window shrinks from about 16 wires to a few: the total
grows only by 9 wires over the divider (31 live to 40), which resolves the earlier puzzle. It is the same consuming
pattern as the root.

**Row anatomy (forward).** One row is about 150 ops and 11 to 13 Toffolis: the window wires are complemented by the
previous digit wire (a fan of CNOTs), then a ripple add of the divisor bits (the root wires `v`) in which **only two carry
wires exist, used alternately and each measured (`HMR`) as soon as the next carry exists, with no phase repair at that
moment** (no `CZ` between the measurements; the outcome bits are kept). Before each measurement the divisor bit and the window
bit are un-primed (`cx c a`, `cx a t`): the sum bit is final and the carry is no longer a function of live qubits, so its
phase debt cannot be paid now.

**The debts are paid in the mirror.** The clean-up rows (ops 10,800 to 17,300, 323 Toffolis against 270) recompute the same
carries (the borrow chain of the subtraction equals the carry chain of the addition) and apply a `Z` conditioned on the
recorded outcome bit directly on each recomputed carry (the `PUSH_CONDITION ... Z ... POP_CONDITION` triplets). The mirror's own
carries are erased in blocks of about 5 with the usual measured clean-up (the `HMR ... CZ if` pairs); a block boundary carry
is measured with a new pending bit and its debt is paid inside one `PUSH_CONDITION` block that recomputes the block
below and applies `CZ`s, so it costs Toffolis only on the shots whose outcome is 1.

**Our gadget (`src/invsqrt_gen/defadd.py`, `tests/unit/test_invsqrt_defadd.py`).** `fd_add` is the forward adder with two
carry wires (`m - 1` Toffolis, as `ripple_add`); `md_add` is its exact inverse with the debts paid and an optional split
(one boundary carry, low block recomputed under a condition). Verified on 49 parameter sets (windows 6 to 12, addends 4 and 8
bits, with and without carry-in, splits 1, 3, 5) against integers, with a clean global phase on every one of 512 random
shots. Carries alive: 2 forward; `max(s, m - s)` in the mirror with a split `s` (19 down to 10 at `m = 21`).

**Does it shrink E023? Not by itself.** E023's peak of 93 is reached in two places: the Horner step with the 19-bit window
(74 live plus 19 carries) and the coarse phase (22 + 5 + 47 + 9 + 10 headroom qubits). Making the Horner adders deferred
(`build_centered(..., deferred=True)`, off by default) leaves the peak at 93 because the coarse phase still needs 93, and the
unary-iteration lookup needs 91. Moving the coarse phase after the main table is cleared would remove that peak but keeps
the nine coarse-word qubits alive through the Horner stage (83 plus carries), so the best case is about 90 (about -3%). The
gadget is the enabler for the new architecture, where every add is a deferred add and the live set is 46 to 50.

## First verifying full circuit (V0, QCC-13)

Built from our own code: `rec.py` (recorder with automatic inverse), `sqrtdiv_stages.py` (even normalisation, in-place root,
`R -> t`, table lookup, coefficient refinement, product, numerator window, consuming division rows),
`sqrtdiv_circuit.py` (forward program, phase section by the existing barrel, mirror). Numbers: integer model in
`sqrtdiv.py` (`fit_sd(40, 29)`: `D0` 15 bits at 2^-40, `E` 10 bits, `P` at 2^-29 in 17 bits, 27 quotient digits).

| | value |
|---|---|
| exact integer model error (27 digits) | 2^-24.99 |
| simulated phase error on 108 inputs (restored `x`, clean scratch) | 2^-25.52 relative |
| qubits / static Toffolis | 134 / 2,618 |
| official verifier, 1/20 of the shots, 1 salt | PASS, cost 397,977.6 (ratio 5.2) |

Forward Toffolis by stage (the mirror costs the same again): normalise 84, root 102 plus 14 for `R -> t`, lookup 126, coefficient 100,
product 397, numerator 42, division 364 = 1,229; phase barrel about 160. Peak live qubits by stage: normalise 41, root 46,
lookup 58, coefficient 79, product 105, numerator and division 134 (everything alive: `P` 17, window 31, `D` 15, `E` 10, `t` 14,
`Q` 13, flags 4, digits 26 and carries).

Roadmap to the reference's profile (in order of expected effect on cost = qubits x charge): (1) consume `P` into the division
window and `t`, `D`, `E` out of the live set (measure `D`, `E` away after the product, reload for the undo): peak 134 to about 75;
(2) consuming odd-`D` multiplier in place of the 397-Toffoli product; (3) deferred-phase adders everywhere (`defadd.py`): carries
19 to 2; (4) one-wire endpoint instead of the barrel; (5) tighter table and digit count.

## V1: table released during the division, numerator built in place (QCC-13)

Two lifecycle changes, both from the reference's timeline, in `sqrtdiv_circuit.forward_program` (flags `release_table`, `inplace`):

* **Release.** After the product the refinement is undone and `D`, `E` are cleared by measurement (`del_lookup`, 18 Toffolis); the
  mirror reloads them (126) and redoes the refinement. +344 Toffolis, 25 wires fewer while dividing.
* **In place.** The product register is initialised to `-1` (all ones) so that it holds `P - 1`; its complement is `-P`, and with
  `d` odd the term `(2^14 - d) << 13` is `[1, ~Q_0 .. ~Q_12]` with no carry, so the window of `r_1 = 2 (1 - P) - s` is the product wires plus
  one zero wire and 13 sign copies, plus one carry-in add: -58 Toffolis, no separate window.

| build | qubits | static Toffolis | official verifier, 1/20 shots | cost |
|---|---:|---:|---|---:|
| V0 | 134 | 2,618 | PASS | 397,977.6 |
| in place only | 113 | 2,560 | not run | about 326k |
| V1 (both) | 105 | 2,904 | PASS | 341,878.1 (ratio 6.07) |
| deferred adders on (`DEFER["on"]`) | 105 | 3,296 | not run | no gain: peak unchanged |

Peak by stage (virtual live wires): normalise 41, root 46, lookup 58, refinement 79, product 105, then 105 at the numerator and
division. The peak is the product's AND temporaries (15 wires) plus the adder carries (about 15) on top of 73 live wires
(`Q` 13, `t` 14, flags 4, `D` 15, `E` 10, `P` 17), not the divider. Deferring the adds (flag `DEFER`) removes carries but the
mirror's split blocks and the temporaries keep the peak at 105.

**Distance to the targets, honestly.** E023 is 168,237 and the reference 80,163. Our floor with the changes still open (on-the-fly
controlled adds without a temporary register, deferred adders everywhere, release of `E` earlier) is about 82 qubits at about 3,300
Toffolis, about 295k. To reach E023 the Toffolis must fall to about 1,900 as well as the qubits to about 65: the forward stages
are 84 + 116 + 126 + 100 + 397 + 364 = 1,187 against the reference's 51 + 96 + 56 + 44 + 103 + 270 = 620 (its product alone is 4x
cheaper) and the mirror repeats them. The part that is not within reach by derivation alone is the reference's product: a consuming
multiplier that keeps only the top 16 columns of the in-place product and measures the low columns away, with their phase repaid in
the clean-up. We derived the odd-multiplier reversibility but not how the low-column debts are repaid cheaply.

## V2: signed-digit product rows (QCC-13), and the consuming multiplier (dead end so far)

**What the decode of the product stage gave.** Row anatomy of ops 5,704 to 6,707: each row is a fan of CNOTs from one `h` wire into the
accumulator wires, one plain ripple add of the coefficient bits (carries on two alternating wires, no AND temporaries), and the same
fan again. That is the complement trick with the digit as control: `h_i` selects `+D` or `-D`, so `h` is used as signed digits
`e_i = +-1` (the centred variable makes that natural) and every row costs one adder, not an adder plus `2 w` ANDs. We adopted this
(`sqrtdiv.p_int_pm1`, `sqrtdiv_stages.product_pm1`): `2 t + 1 = sum_{i<13} e_i 2^i - e_13 2^13` with `e_i = 2 b_i - 1`, rows
`e_i R(D >> (12 - i))` with the rounding bit as carry-in (E023's trick), `+ R(D >> 13)` for the `3/4`, and a constant that
centres the error (`-3` units, free as the register's initial value). Exact model error 2^-24.94 at 27 digits; circuit phase error 2^-25.4.

| build | qubits | executed Toffolis | official verifier, 1/20 shots | cost |
|---|---:|---:|---|---:|
| V1 (AND-temporary product) | 105 | 2,904 | PASS | 341,878 |
| V2 (signed-digit product, deferred adders, lazy carry allocation in `md_add`) | 90 | 2,780 | PASS | 281,802 (ratio 7.37) |

**What did not decode: the consuming multiplier.** At fixed `v`, with all 813 residuals `h`, the reference's product register is 16 wires
(`q0` to `q8` plus seven new ones) whose flip rates over consecutive `h` fall 669, 645, 572, 480, 323, 286, 161, 81, 41, 21, 11, 5, 3, 1:
a counter of about 14 bits in which `q0` to `q8` are the high columns and about 5 new wires the low columns (slope about 20 per unit `h`),
so the product wires reuse the multiplier's wires as its high part. The integer read in flip-rate order is not affine in `h` (the wires
are in an XOR frame), and the information count says why the idea is not free: `h -> P` is injective only if `D / 2^k >= 1` and the
circuit must recover `h` from `P` without a second copy, which needs either the dropped low columns (a 29-wire full product, no saving
over our `t` plus `P`) or a debt repaid by measured low columns, whose rule we could not identify from the gate text (the
`CZ` networks that repay it sit in the 7,000-gate clean-up block). We do not have an exact repayment rule, so we did not implement the
consuming product.

**Where that leaves the cost.** Executed Toffolis by stage (forward; the mirror repeats it, the table is loaded again): normalise 84, root 116,
lookup 126, refinement 100 (twice, with its undo), product 239, division 364, phase barrel about 300 for three calls. Realistic further steps
with derivations in hand: one-wire endpoint (-190), signed-digit refinement (-120), trimmed adder windows (-100), giving about 2,350 executed
Toffolis at about 80 qubits, about 215k, still above E023 (168,237). Beating E023 needs the consuming multiplier or an equivalent 14-wire
saving, and the 80,163 reference needs all of the reference's measured-away registers.

## Repaying the multiplier's low columns by recomputation in the mirror: the algebra does not close (QCC-13)

Proposal tested: measure each finished low column of the signed-digit product in the X basis, keep the outcome `m_j`, and in the mirror pay
`(-1)^(m_j b_j)` with a `Z` on the recomputed bit `b_j`, as `md_add` pays its carries.

* **What closes.** In a product where `t` stays alive (ours), a finished low column of `P` is a function of `(t, D)`. Measuring it at the end of the
  forward product and recomputing it in the mirror (a product restricted to those columns, from the live `t` and `D`) before undoing the
  rows reproduces the same bit, so `Z^{m_j}` on the recomputed wire pays the debt exactly (the same algebra as `fd_add`/`md_add`). But the columns of our
  rows are only final after the last row, they are the low bits of the numerator `X` that the division consumes, and the saving is the
  number of dropped columns (2 or 3 wires, about 30 Toffolis to recompute): not the 14 wires.
* **What does not close: the consuming multiplier.** Consuming `t` into the accumulator means the dropped bits `delta_j = (acc_j + e_j D) & 1` are the
  only place the digits' information survives. Measured away, they cannot be recomputed in the mirror: given `acc_{j+1}`, both values of `delta_j` give
  an in-range predecessor `acc_j = 2 acc_{j+1} + delta_j - e_j D`, in 100% of the steps (`tests/unit/test_invsqrt_lowcols.py`), although the final
  accumulator is injective in `t`. The digits are recovered globally by successive approximation (`e_{N-1} = sign(acc_N)`, then compare against
  `D/2` ...), which is a non-restoring division of the accumulator by `D`: the inverse of a consuming product is a division-like recurrence of
  about the same cost as the forward product, and it needs `D`, so the table would have to be alive (or reloaded) exactly there.
  The reference's inverse product costs about 130 Toffolis against 103 forward, consistent with that.
* **So the reference's 16 wires are not explained by repaying low columns.** Its low columns are never measured (the product stage measures only the
  two alternating carry wires and `q8`); they stay live as the low bits of `P`, are consumed by the division as the dividend's fine bits, and are restored by
  the division clean-up before the product is undone. The saving over our `t` plus `P` (31 wires) is that its `h` has 10 bits instead of our 14 (the
  four low bits of `t` are a function of `R mod 16` and are handled by a three-row seed term) and that the product register reuses the `h`
  wires. The 4-wire part is derivable (clear the low four bits of `t` with a 16-entry function of `Q`, recompute them in the product rows),
  but it does not move our peak, which is the product stage (table words alive), not the divider.

Conclusion: roadmap 2 as a 14-wire saving is a dead end by derivation. What remains derivable (one-wire endpoint, signed-digit refinement, trimmed
windows) is worth about 215k at best, above E023.
