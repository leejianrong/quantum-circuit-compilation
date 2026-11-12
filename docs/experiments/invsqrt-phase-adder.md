# invsqrt: phase adder, signed-digit rows, lazy allocation (QCC-13)

Goal: close the gap to the public 62-qubit circuit (cost 94,599.6, ratio 21.95) from the 121-qubit centered build
(247,262.49, ratio 8.40, E016). The open lever left by `docs/experiments/invsqrt-bitserial.md` was a *phase adder*:
drop the stored phased word and both barrel shifters, and pick which sum bit meets which rotation so the factor `2^s`
is applied for free. Everything here is our own derivation from the paper's description of the problem and the host's
reference builder (ADR-0009 stage 1); no public circuit was read for this work, so `docs/PROVENANCE.md` has nothing
new to log.

**Result: the phase adder does not pay (below), but four other changes do: 101 qubits, cost 195,062.72, ratio 10.65, 5 of 5 salts pass (E018; was 121 qubits, 247,262.49, ratio 8.40). The frontier (ratio 21.95) is not reached; nothing here touches `best/`.**

Reproduce: `uv run python -m invsqrt_gen.cli --a 7 --frac 29,19,10 --guard 3 --pm1 --rnd --polish --reachable out/e017`.

| Build | Qubits | Static Toffolis | Rotations | Predicted cost | Verifier |
|---|---:|---:|---:|---:|---|
| E016 centered Booth, 28,19,9 g2 | 121 | 1,710 | 45 | 247,262 | 5 salts, 247,262.49 |
| signed-digit rows, 30,20,11 g4 | 106 | 1,700 | 45 | 213,686 | screen 213,685.64 |
| + rounding rows, 28,20,11 g2 | 104 | 1,631 | 45 | 202,564 | screen 202,564.53 |
| + allocate tables after normalising, 28,20,11 g2 | 101 | 1,631 | 45 | 196,721 | |
| + 29,19,10 g3 | 101 | 1,609 | 45 | 195,063 | 5 salts, 195,062.72 |

All costs are `Q * (Toffolis + T/4)`; `predict.py` matches every verifier run to the printed digit (the one new term is
the flag clear of the un-normalisation, which now runs on half the shots, see lever 4).

## The phase adder, designed and costed

Idea: the last Horner row is an adder `V_0 -= e_i V_1 2^sh`. A Gidney adder computes its carries on the way up and
writes the sum bits on the way down; if the sum bit that is produced is rotated on the spot and then discarded, the
sum is never stored, and a different rotation position for each `s` would replace the barrel shifter.

Costing it with the generator (`--fine serial`, `--split ... serial`: the multiplexed phase of `serial_phase`, which
is exactly "bit `p - s` of the word meets rotation `p`", with a one-hot of `s` and no head registers):

| Variant (29,19,10 g3 words) | Qubits | Toffolis | Predicted cost | vs barrel |
|---|---:|---:|---:|---:|
| barrel coarse + barrel fine (built, verified) | 101 | 1,609 | 195,063 | |
| mux coarse (no head, one-hot of `s`) | 108 | 1,642 | 212,146 | +8.8% |
| mux fine (no head, no unshift) | 101 | 1,672 | 201,426 | +3.3% |
| mux both | 108 | 1,705 | 218,950 | +12.2% |

Where the 33 rotations go: the phase frame has `F = wy + 10 = 36` positions (angle `2^(p-F)` turns); the top three
(Z, S, T) are free, so 33 positions need a rotation. The fine word (19 bits at positions 0 to 18, shifted up by
`s <= 10`) reaches positions 0 to 28 and the coarse word (9 bits at 17 to 25) reaches 17 to 35; the 12 positions in
both ranges are rotated twice, which is why 45 rotations exist. The multiplexer for position `p` of the fine word has
`min(p, 10) + 1 - max(0, p - 18)` terms (1, 2, ... 11, 11 ... 11, 10, ... 1), 209 Toffolis in all, against 164 for the
barrel and its unshift; the coarse word needs 99 against 84.

Why it cannot be better: position `p` needs bit `p - s` for the one `s` that is live, so every sum bit must be present
when the multiplexer for any position reads it. A streaming adder produces sum bit `i` once, at one moment of the
down-sweep, and the rotation for position `i + s` happens at a time that depends on `s`; reading the sum bits in
any `s`-dependent order needs them all stored (which is the phased word again) or `11 x` the rotations (one controlled
rotation per `(bit, s)`, 11 x 19 = 209 rotations at 7 Toffoli-equivalents each). The most a streaming last row could
save is its own mirror (about one 22-bit add, 1%), and only if the shift is free, which it is not. Error analysis:
the phase adder changes no arithmetic, so the error is the build's model error (below) and the 2^-24 gate is
unchanged. **Verdict: loss of 3.3% (fine) and 8.8% (coarse, which also costs 7 qubits for the one-hot), so not built
further.** The mux builds are in the generator (`build_centered(..., fine="serial")`) and equal their model in
the unit tests.

## What paid

### 1. Signed-digit (+-1) rows: no operand register (E018)

Booth radix 4 needs, per digit, two selects and one AND per operand bit to build `0, +-V, +-2V` in a scratch register
before the add (`2 w + (window - 1)` Toffolis, `w + 3` extra qubits at the widest row). The centered remainder
`rho = r - 2^13` can instead be written with digits that are never zero. Let `e_i = 2 r_i - 1` for the 14 bits
`r_i` of the remainder (so `e_i = +-1`) and `E = sum e_i 2^i = 2 r - 2^14 + 1`, an odd number in `[-(2^14 - 1), 2^14 - 1]`.
Then `rho' = E / 2 = r - 8191.5` is centered exactly on its segment, and

    rho' V = sum_i e_i 2^(i-1) V,

one add or subtract of the multiplicand per bit, the sign being the bit itself (the window is complemented around the
add when `r_i = 0`: free Cliffords). The multiplicand register is the adder's addend directly, so there is no operand
register and no select: 14 plain adds replace 7 Booth rows, and a row costs `window - 1` Toffolis. Step 0 goes from
353 to 280 per direction (at the old widths), the widest row from 43 to 20 transient qubits, and `x[13]` no longer
needs its inversion. The price is accuracy: 13 floors instead of 7 (one per row whose slice drops low bits), which
moved the widths from 28,19,9 g2 to 30,20,11 g4 (2^-24.31 over the reachable inputs) at first.

### 2. Rounding is free: the carry-in of the adder

The slice of row `i` is `floor(V 2^sh)`; the bit just below it is `V` bit `-sh - 1`. Feeding that bit to the adder as
its carry-in rounds the slice to nearest at no Toffoli (Gidney's first stage has the same one AND with or without a
carry-in; a borrow-in for the subtracting form). Error per row falls from `[0, 1)` to `[-1/2, 1/2)` LSB, which buys back
one to two guard bits: 29,19,10 g3 and 28,20,11 g2 pass at 2^-24.10 and 2^-24.23.

### 3. Allocate the tables after normalising (-3 qubits)

`multi_controlled_x` on the top 16 bits (the zero test of the first normalisation level) allocates 14 ancillas
inside the library call. The generator allocated every register (90 qubits) before normalising, so the circuit
peak was `90 + 14 = 104`, three above the true Horner peak of 101, and invisible in the builder's allocation counter
(found by allocating after each stage and reading the ids). Normalising first, then allocating the tables, and freeing
them before the un-normalisation brings the peak to the Horner stage: 101 qubits, free.

### 4. Measurement-cleared flags in the un-normalisation (-15 Toffolis)

Each flag `z_j` is cleared by `HMR`, and the phase `(-1)^[top m bits are zero]` is fixed only on the shots whose
outcome is 1 (a conditional AND chain over the top bits). 22 Toffoli-like gates are now conditional and run on half
of the shots, so the executed count is 11 below its static value, which `predict.py` accounts for
(`build.conditional_toffolis`).

## Error analysis (the 2^-24 gate)

Model error over the reachable inputs, polished tables (`--polish --reachable`), signed-digit rows. `rnd` rounds the
slices; `margin` is the exponent of `min f(x) (2^-24 - rel(x))` in turns, which sets the rotation synthesis error.

| frac f0,f1,f2 | guard | rows | reachable error | feasible |
|---|---:|---|---:|---|
| 30,20,11 | 4 | floor | 2^-24.31 | yes |
| 29,20,11 | 3 | floor | 2^-24.06 | yes (margin 2^-39) |
| 29,20,10 | 3 | round | 2^-24.68 | yes |
| 29,20,9 | 3 | round | 2^-24.60 | yes |
| 29,19,10 | 3 | round | 2^-24.10 | yes, cheapest (195,063) |
| 28,20,11 | 2 | round | 2^-24.23 | yes (196,721) |
| 28,20,10 | 2 | round | 2^-24.00 | marginal (margin 2^-51, 203,626) |
| 28,19,10 / 28,19,11 | 2 | round | 2^-24.01 | no |
| 29,20,10 | 3 | floor | unpolished 2^-23.5 | no |

## Levers costed and not built (Toffoli-equivalents; one qubit is about 19 of them)

| Idea | Effect | Verdict |
|---|---|---|
| Phase adder / mux phase | +3% to +6% (above) | no |
| Reload `V_2` for the mirror (idle for 11 qubits across step 0), table interpolated from 6 address bits | -11 qubits, +about 200 Toffolis | wash |
| Split the add window or use block carries (fewer carry ancillas at the Horner peak) | -10 qubits, +1 Toffoli per bit per add (about +500) | loss |
| Narrow rows added into a small accumulator, then one wide add | rows cost 14 instead of 21, but the accumulator is rebuilt for the mirror | loss |
| Radix 4 with digits `+-1, +-3` (7 rows) | needs `3V` stored (21 qubits) and a mux per bit | no gain |
| Fresh shifted copy of the fine word, cleared by measurement (unshift for free, fix-up is one CZ per `(s, bit)` from a one-hot) | -82 Toffolis, +29 qubits at a stage that sits at 91 qubits, so the peak rises to 110 | loss |
| Single phased word again (coarse word held through Horner) | -193 Toffoli-equivalents, +9 qubits at the peak | wash |
| Non-uniform segments (fewer entries where `f'''` is small) | -60 lookup, an extra Booth row or a 15-bit remainder | loss |
| Newton step instead of a degree 2 polynomial | `M y0^2` needs an absolute 2^-28 product, the same width as Horner | no |
| Degree 3 with `a = 6` | -150 lookup, step 2 and an extra row per step | loss |

Every qubit-for-Toffoli trade I could find sits within a few percent of break-even, because one qubit costs about as
much as one 20-bit add; what moved the cost was removing work that bought nothing (the Booth operand and selects, a
rounding error, a stray allocation).

## Next lever

Rows are 53% of the Toffolis (846 of 1,609: 14 + 10 adds per direction, each one `window - 1`). The narrow rows
(operand 6 to 12 bits) pay the full window for the carry ripple; a design that lets a narrow row's carry-out wait for
the wide ones without holding a qubit per row, or a different decomposition of `rho' V_1` with fewer than 14 adds,
is the remaining large lever. The qubit peak (101) is now flat across the Horner, coarse and lookup stages
(101, 100, 98), so a further qubit saving needs all three to move together.
