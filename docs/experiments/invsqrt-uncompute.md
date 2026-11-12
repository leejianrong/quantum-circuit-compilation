# invsqrt: uncompute, lean qubits and exhaustive windows (QCC-13)

Goal: from the 101-qubit Horner generator (195,062.72, ratio 10.65, `docs/experiments/invsqrt-phase-adder.md`) towards ratio 12,
then 15, then the public frontier (94,599.6 at 62 qubits, ratio 21.95). The brief was to attack the doubled un-computation
(Horner mirror 53% of the Toffolis) and the qubit peak. Everything here is our own derivation from the paper's description of
the problem and the host's reference builder (ADR-0009 stage 1). The only look at a public circuit was aggregate statistics
(operation counts, CSWAP control multiplicities, the nesting depth of its condition blocks), logged in `docs/PROVENANCE.md`;
no change below derives from it.

**Result: ratio 12 is reached (E023): 94 qubits, 1,489 executed Toffolis, 45 rotations, predicted cost 170,102.6 (ratio
12.21)**, 5 of 5 salts pass with 0 failures at 170,102.54 to 170,102.58 (the cost moves in the sixth digit with the
salt because the 11 conditional flag-clear Toffolis run on about half of the shots; circuit sha256 `25c0b722164e`). Ratio 15 and the frontier are not reached (E024, E025): the doubled
un-computation cannot be removed inside this architecture, and the qubit floor of the Horner family is close to 90 (analysis
below). Nothing here touches `best/`.

Reproduce: `uv run python -m invsqrt_gen.cli --a 7 --frac 28,19,10 --guard 2 --pm1 --rnd --polish --reachable --radius 2 out/e023`.

| Build (all predicted with `predict.py`, exact on every earlier verifier run) | Qubits | Toffolis | Cost | Ratio |
|---|---:|---:|---:|---:|
| Start: 29,19,10 guard 3 (E018) | 101 | 1,609 | 195,062.7 | 10.65 |
| carry out of bit m-2 straight into the top sum bit (no ancilla) | 100 | 1,609 | 193,131 | 10.75 |
| + no qubit for the always-zero top bits of `V_1.hi` and `V_2` | 98 | 1,605 | 188,877 | 11.00 |
| + `x[21]` (the leading one, always 1) lent as the window extension | 97 | 1,605 | 186,949 | 11.11 |
| + our ripple adder for `hi += ext` | 97 | 1,603 | 186,755 | 11.12 |
| + 28,19,10 guard 2 table (2^-24.01 on the reachable inputs) | 95 | 1,577 | 182,918 | 11.35 |
| + each row ripples only to the highest bit it ever changes | 95 | 1,507 | 176,268 | 11.78 |
| + one table-loaded extension qubit instead of two | 94 | 1,493 | 173,096 | 12.00 |
| + constant-one coarse bit moved with CNOTs | 94 | 1,491 | 172,908 | 12.01 |
| + polish radius 2 (2^-24.18, rotation margin 2^-37.5 instead of 2^-42) | 94 | 1,489 | 170,103 | 12.21 |

## What paid

All of it is removal of work or qubits that bought nothing, checked against the bit-exact model (unit tests, and 67k simulated
inputs on the full-size circuit: 0 phase mismatches, `x` restored, scratch clean).

1. **No ancilla for the last carry.** `ripple_add` allocated `m - 1` carries for an `m`-bit window. The carry out of bit
   `m-2` only feeds the top sum bit, so one Toffoli XORs it straight into that bit: same Toffoli count, one qubit fewer at every
   add (`ripple_add` now also accepts an addend as wide as the target).
2. **Constant table bits are free.** `V_1 < 2^18` and `V_2 < 2^9` for every input, so the top bit of `V_1.hi` and of `V_2` is
   always 0 (`unused_top_bits`): no qubit, no lookup fan-out. A one-bit operand of the lowest `V_2` row becomes just its rounding
   carry-in.
3. **`x[21]` is a free qubit.** After normalising it is the leading one, 1 for every input. Flip it to 0, use it as a scratch
   qubit (the window extension of `V_1`), give it back before un-normalising. It lowers the qubit count at every stage.
4. **Exhaustive windows (`row_window_tops`).** The verifier runs exactly the reachable inputs (2,350,089 normalised values), so
   for each signed-digit row we can compute, with the model's own arithmetic, the highest window bit it ever changes and cut the
   carry ripple there. The circuit then differs from the model only on inputs nobody runs. Step 0 (window 21): rows 0 to 4 stop
   at bit 16 or 17, rows 5 to 13 need all 21; step 1 (window 13): rows 4 to 6 stop at bit 7, 9 and 12. The two steps save 22 and 11 Toffolis per
   direction at the final widths (70 in all when it was added at 28,19,10 with radius 1). The window of a row is bounded below by the operand and above by `W mod 2^b` staying inside one aligned
   block for every address, which is why only the narrowest rows gain.
5. **One extension qubit.** The signed window `lo + 2^K - Q` needed two extension qubits. The table can instead choose, per
   address, `e = 1` when `lo < 2^(K-2)` and `e = 0` otherwise, load `e` itself into the single extension qubit, and store
   `hi = (c >> K) - e`: `lo + e 2^K +- Q` stays inside `[0, 2^(K+1))` because `|Q| < 2^(K-2)`. One qubit fewer, and every row of
   step 1 is one Toffoli shorter (20 in all).
6. **The lowest coarse bit is a constant 1.** The coarse words are odd, so the first barrel level only has to flip that bit and
   the slot above it when its flag is set (the slot is empty exactly then): two CNOTs per direction instead of a Toffoli.
7. **Tuning at the boundary.** With one qubit and a row less per window, the 28,19,10 guard 2 table (judged infeasible before:
   2^-24.01, margin 2^-42 turns) becomes the best configuration; a polish search of radius 2 instead of 1 on `c_1, c_2` improves
   it to 2^-24.18 (more margin, so cheaper rotations: 31.6 to 28.6 T each, about -37 Toffoli-equivalents).

## Lever (a): measurement-based uncomputation

The rule (paper, section A and the `HMR` definition): `HMR` on a qubit holding `g(x)` leaves the phase `(-1)^(m g(x))`, which is
free to fix only when `g` is linear in qubits that are still alive, or a single AND of two such linear combinations (a `CZ`).

* **Tables.** Already used: `del_lookup` clears a table register for 25 Toffolis whatever its width (measured: 25 for 9 and for
  51 bits at 256 entries). A custom two-level one-hot version would cost about 28.
* **Adder results.** The sum bit `s_j = a_j + t_j + c_j` is linear in the carry, so it is free to erase while the carries are
  alive, and each carry is one AND of linear combinations, free to erase while its inputs are alive. An in-place add overwrites `t`
  with a nonlinear function of its old value and the carries, so nothing alive can pay for the erasure: it costs a carry chain
  again, `n - 1` Toffolis, which is what the mirror add costs. An out-of-place sum erased by measurement costs the same carry
  chain. So the Horner mirror (258 + 114 per direction: 372 of 1,489, 25%, plus the equal forward pass) cannot be replaced by a
  measurement.
* **Streaming the last add.** If the last add's sum bit is rotated and measured as it is produced (carries kept, nothing written),
  it needs no mirror: at most the last row, about 20 Toffolis. The `2^s` shift then needs a multiplexer from every sum bit to 11
  positions, which costs more than the barrel (measured +3.3% for the fine word, +8.8% for the coarse one, in
  `invsqrt-phase-adder.md`).
* **Carry-save trees.** Erasing a carry-save layer is free (each carry is one AND of live combinations), but every full adder
  leaves a carry qubit alive until the end: step 0 has 188 operand bits, so 188 extra qubits against the 19 of a ripple. A
  column-wise multi-operand adder (popcount per column, 4-bit carry counter between columns) needs the same Toffolis as the
  rows but must keep every column's counter alive to erase the next one; with the shift by `s` applied to the multiplicand the
  columns grow from 21 to 36 (540 Toffolis against 294).
* **Gradient catalyst.** Adding the rows into a prepared phase-gradient register removes the mirror of step 0 but needs the shifted
  multiplicand (barrel in and out, about 160), 14 adds of about 30 into a 36-qubit register (420), 36 more qubits, and 2 x 33
  fine rotations to prepare and unprepare the gradient (about 470 Toffoli-equivalents against 320 for today's 45 rotations):
  predicted ratio about 8.
* **Conditional execution.** The verifier averages executed gates over shots, so a block under a measurement condition costs the
  fraction of shots that run it. Only phase fix-ups of measured flags qualify, and the un-normalisation already uses them (11
  of its 22 conditional Toffolis run).
* **Approximate arithmetic.** `iadd`'s `btol` only helps classical offsets. Exhaustive validation over the finite input set is
  what made point 4 possible; the same check on the barrel cswaps (does any reachable input move a 1 through it) finds none to
  drop, and on the rotations finds every position used.

## Lever (b): table versus arithmetic

Unquantised relative error of the piecewise minimax polynomial of `1 / sqrt(M)` on `M in [1, 2)` (worst segment; the budget for the
approximation is about 2^-26):

| degree | a=5 | a=6 | a=7 | a=8 | a=9 | a=10 | a=11 | a=12 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2^-14.5 | 2^-16.4 | 2^-18.4 | 2^-20.4 | 2^-22.4 | 2^-24.4 | 2^-26.4 | 2^-28.4 |
| 2 | 2^-21.7 | 2^-24.7 | 2^-27.7 | 2^-30.7 | 2^-33.7 | 2^-36.7 | 2^-39.7 | 2^-42.7 |
| 3 | 2^-29.0 | 2^-32.9 | 2^-36.9 | 2^-40.9 | 2^-44.8 | 2^-48.2 | 2^-49.3 | 2^-49.4 |

* **Degree 1 with a larger table** needs a = 11: 2 x 2^11 entries, 4,094 Toffolis for the unary iteration (254 today) and a
  50-bit output. The SELECT-SWAP variant needs about 1,000 Toffolis and 800 qubits. Predicted cost: about 3 times today's.
* **Degree 3 with a = 5** (64 entries, lookup 62 Toffolis, 192 fewer than now): the remainder grows to 16 bits and a third step
  appears; rows 16 + 13 + 9 at windows 23, 16 and 12 cost about 670 per direction against 372, so +590 Toffolis for -205 in the
  lookup: predicted ratio about 9.
* **Degree 2 with a = 8** (error 2^-30.7, three bits of slack for narrower registers): lookup +256 and clear +10 Toffolis; one
  row fewer in each step and narrower windows (about -150); the slack buys about 3 qubits. Predicted: a wash (+1%). Not built.
* **Pair-normalisation without the parity shift.** Dropping the level-1 shift of `x` (-42 Toffolis) makes the two octaves
  need different address and remainder alignments; the cheapest consistent table has 384 entries (+130 Toffolis in the lookup)
  and saves one row per step (-70): predicted +2%.
* **Special table for `x < 64`** (the only inputs that use the shift by 8, 63 of them) would drop the last barrel level (-64
  Toffolis) and three rotations (-21), for 63 more lookup entries and an extra address qubit: a wash.

## Lever (c): shorter carries, Estrin, shared products

The Horner rows carry 69 Toffolis per direction of pure ripple above the operand in step 0 and 33 in step 1 (operand 7 to 19
bits, window 21 and 13; point 4 recovered 33 of them). Ways to remove the rest, costed:

* Accumulate the narrow rows in a separate small register and add it once: rows cost 13 instead of 21 but the accumulator has to
  be rebuilt for the mirror, so 126 + 21 + 126 against 168 for six rows: loss, and +14 qubits.
* Defer each row's carry-out into a counter and add the counter once: saves about 27 per direction, but the 4-qubit counter lives
  until the mirror and the peak rises by 4: a wash.
* Radix 4 with digits +-1, +-3 needs `3V` (21 qubits) and one multiplexer Toffoli per bit: no gain; the select-and-add form was
  the Booth rows already beaten by the signed digits.
* Estrin / explicit square: `rho'^2 = sum 4^(i-1) + 2 sum_{i<j} e_i e_j 2^(i+j-2)` has free parity signs but about 60 pairs above
  the precision floor, each a 13-bit add: 780 Toffolis against step 1's 114.
* Shared partial products: the two steps multiply by the same `rho'` but different multiplicands; nothing is shared.

## Lever (d): qubit reuse

Peak at 94: `x` 22 (one lent), flags 5, `V_0` window 21, `V_1` 12 + 6 (+ the lent extension), `V_2` 9, 19 carries of the widest
add. The coarse stage (cw 9 + 10 head) and the lookup stage (92) are within two of it, so a further qubit needs all three to move.
Each qubit is worth about 19 Toffoli-equivalents. What was tried: dirty carries in the idle `V_2` (4 Toffolis per borrowed
bit), splitting the carry chain (+1 Toffoli per bit per add), reloading `V_2` (254 Toffolis), a shifted copy of the fine word with
its measurement fix-up (needs 40 qubits: copy, headroom and a one-hot of `s`, at a stage with 20 free), and deferring the
coarse word. None breaks even.

## Lever (e): other architectures

* **Copy and measure the shifted word** (no unshift: -4 Toffolis per phased bit, about 110) needs the shifted copy, its headroom
  and an 11-qubit one-hot of `s` for the free `CZ` fix-ups: +40 qubits.
* **Additive (multipartite) tables**: phases add, so a sum of table words needs no arithmetic at all, but the first-order
  correction alone needs 13 address bits (`f'' h^2 / 2 < 2^-26`), 8,192 entries.
* **Limb-by-limb evaluation** (compute a 9-bit slice of the result, phase it, erase it) keeps the carries between limbs alive
  until the mirror and shifts three narrow words instead of one wide one: same barrel cost, same qubits.

## Where the rest is

Executed Toffolis by stage (1,489): lookup 254, normalise 105, un-normalise 101 (11 conditional), coarse 107, fine 164,
Horner 258 + 114 forward and again in the mirror. The public frontier executes about 1,238 with 62 qubits: its CSWAP count (205)
is about what our two normalisations cost alone, so it spends about half of our 248 on the `2^s` shifts, and a polynomial stage that
fits in 35 qubits above `x` and the flags. Neither follows from anything above; ratio 15 needs both.

## Reproduce

```bash
uv run python -m invsqrt_gen.cli --a 7 --frac 28,19,10 --guard 2 --pm1 --rnd --polish --reachable --radius 2 out/e023
flock /tmp/qcc-heavy.lock env QCC_DATA=$PWD/data uv run bench verify invsqrt out/e023.kmb --salts 10
```
