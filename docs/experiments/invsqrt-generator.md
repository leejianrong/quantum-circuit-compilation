# invsqrt: our own generator (QCC-12)

`src/invsqrt_gen/` builds an invsqrt circuit from parameters. It is written from the benchmark paper
(arXiv 2610.23832 section on Benchmark I), the host's Apache-2.0 reference builder and standard
numerics (ADR-0009 stage 1). Public circuits were used as cost oracles only (totals); the one
structural look we took is logged at the end. The package is called `invsqrt_gen` because the host
verifier is itself a package called `invsqrt` and `bench` imports it by that name.

```bash
uv run python -m invsqrt_gen.cli --a 7 --frac 30,20,11 --guard 4 out/g4   # writes out/g4.kmb and out/g4.kmx
QCC_DATA=$PWD/data uv run bench verify invsqrt out/g4.kmb --salts 5
```

## Design

Input `x` (22 qubits) is kept; everything else is scratch that returns to 0.

1. **Normalise.** Count leading zeros `z` in binary (5 flag qubits, levels 16, 8, 4, 2, 1) and shift `x`
   left by `z` in place with controlled swaps, so the top bit is set: `M = x_norm / 2^21` in [1, 2).
   `1 / sqrt(x) = 2^(s - 10) * Y` with `s = z // 2` and `Y = 1 / sqrt(M 2^(1 - z%2))` in (0.5, 1]. The
   parity `z % 2` is the top bit of the table address, so `M` in [2, 4) gets segments twice as wide.
2. **Look up.** One unary-iteration pass over the `2 * 2^a` entries writes the coefficients
   `c_0 .. c_d` of the segment into the Horner registers `V_0 .. V_d` (the output width is free).
3. **Horner.** `V_j -= T(r V_{j+1})` for `j = d-1 .. 0`, with `r` the `21 - a` low bits of `x_norm`
   (they are the controls). Each product is a sum of radix-4 Booth digits: per digit two ANDs per bit
   choose `V` or `2V` into a clean operand register, the digit sign complements the target window around
   one ripple add, and the operand is cleared by measurement. `T` floors each digit's slice, which the
   bit-exact model in `model.py` reproduces.
4. **Borrow trick.** The product is below `2^-a`, so a digit add only needs the low `K = f_j - a` bits of
   `V_j` plus one sign qubit; a single controlled decrement moves the net borrow into the `a` high bits
   afterwards, and the mirrored increment plus the adds' carries clear the sign qubit again. This cut
   the carry chains from 30 to 24 bits and removed about 18% of the Toffolis on its own.
5. **Phase.** The word `V_0 >> guard` (`wy` bits) is shifted up by `s` inside `wy + 10` qubits with four
   levels of controlled swaps (windows sized to the reachable `s <= 10`), then one `Z_POW` per bit
   (angle `2^(i - F)` turns, `F = wy + 10`), and shifted back.
6. **Uncompute.** Exact mirror: Horner undone, lookup cleared by `del_lookup` (measurement based),
   flags recomputed and cleared, `x` shifted back.

The circuit equals its numpy model bit for bit (`tests/unit/test_invsqrt_gen.py` runs both on
simulated shots), so the exhaustive error over all `2 * 2^21` normalised inputs is known before any
verifier run. `fit_tables` quantises per-segment minimax coefficients and refines them against the exact
truncated model.

Parameters (`Params`): `a` segment bits, `frac` fractional bits of `V_0 .. V_d` (degree is `len - 1`),
`guard` bits of `V_0` below the phased word.

## Results

Cost is the official verifier's `Q * C`; baseline 2,076,774, public best 94,599.6 (62 qubits).

| Step | Qubits | Static Toffolis | Cost | Ratio |
|---|---:|---:|---:|---:|
| Baseline (host reference) | 260 | 7,735 | 2,076,774 | 1.00 |
| v1: pair normalisation, 3 * 2^a table, binary rows, library adders | 151 | 3,252 | 524,931 | 3.96 |
| + borrow-window trick, own ripple adder | 146 | 2,400 | 383,157 | 5.42 |
| + lazy scratch, bit normalisation, tuned widths | 133 | 2,271 | not run (superseded) | |
| + radix-4 Booth digits (`--a 7 --frac 30,20,11 --guard 4`) | 136 | 1,949 | 296,738.6 | 7.00 |
| + centered remainder, split phase words, widths at the accuracy boundary (`--a 7 --frac 28,19,9 --guard 2 --centered --polish`, QCC-13) | 121 | 1,710 | 247,262.5 | 8.40 |

The Booth build passed all 5 salts with 0 failures (cost identical to the last digit: no Toffoli is
conditional, and the rotation margin comes from the arithmetic error, not from the measurement seeds),
and a reduced-shot screen of the `.kmx` file matches the `.kmb`. Per-stage Toffolis of the Booth build (`a = 7`, `frac = 30,20,11`, `guard = 4`), forward and back:
normalise 105 + 105, lookup 254 + 25, Horner step 1 191 + 191, Horner step 0 429 + 429, phase shifts
110 + 110. Rotations add about 240 Toffoli-equivalents (33 non-Clifford `Z_POW`).

## What drives the cost now

* Horner is about 57% (the step-0 product `r V_1` dominates: 8 Booth digits, each about 34 ANDs and a
  24-bit add). Both directions pay it because the uncompute is the mirror.
* Fixed costs are the lookup (14%), the two shifts of `x` and of the phased word (22%) and the 33
  rotations (11%).
* Qubits: 136 = 22 `x` + 5 flags + 67 Horner registers + about 40 transient (operand register, carry
  ancillas, three selects).

## Study of the public frontier (ADR-0009 stage 2, aggregate only)

We did not read the 62-qubit circuit gate by gate. From `operation_statistics`, per-window instruction
histograms and the `Z_POW` listing we learned two structural facts, both implemented in QCC-13
(`docs/experiments/invsqrt-bitserial.md`: neither pays alone, a centered remainder does):

* Every non-Clifford rotation (43 of them) acts on one qubit, with a `HMR` after each: the phase is
  applied bit by bit through a single working qubit instead of a phased register of `wy + 10` qubits.
* The rotations come in two blocks about 7,800 instructions apart with overlapping angle ranges, so the
  phase is split into a coarse word and a fine word that are phased and cleared separately (phases add),
  which is how the qubit count stays near 40 above `x`.

Both attack our two biggest multipliers, the 67 Horner qubits and the phase block. The next lever is a
generator that never holds the full `V_0`: phase the coarse table word, clear it by measurement, then
build and phase only the small residual `r V_1`.
