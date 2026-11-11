# Primer: invsqrt

Benchmark I asks for a circuit that multiplies a quantum state by the phase `exp(2 pi i / sqrt(x))`
for an integer input `x` between 1 and 3,133,452. That is one inverse square root and one phase,
repeated for every pair of electrons in the simulation. The competition's science goal is the
stopping power of alpha particles in a plasma. Here we only need the arithmetic.

Prerequisites: [costs and MBUC](costs-and-mbuc.md). Terms are in the [glossary](glossary.md).

## The task as the verifier states it

From `verify_submission_invsqrt.py`: the register `x` has 22 qubits (`2 n_p + 2` with `n_p = 10`).
All other qubits are scratch. For each `x`, the circuit must leave `x` unchanged, return every
scratch qubit to 0, and apply a phase `theta` (in turns, where one turn is a full circle) with

```text
| theta - 1/sqrt(x) |  <=  2^-24 / sqrt(x)      (mod 1)
```

So the tolerance is relative: the phase may be wrong by one part in `2^24`, about `5.96e-8`. That
is the error budget. The input range is `max_x = 3 (2^10 - 2)^2 = 3,133,452`. The paper says the
earlier fusion resource estimates used `n_p = 6` and that the competition benchmark uses `n_p = 10`
(2^18 electrons), a larger instance with a 22-bit input.

Two consequences follow from the phase being a plain number of turns. First, adding phases is
addition of turns, so if `y` is an integer meaning `y / 2^F` turns, you can apply it with one
`Z_POW` per bit of `y` (bit `j` is worth `2^(j-F)` turns). The reference does this for `F = 40`
bits. Second, because a phase is applied once at the very end, everything before it is a classical
computation of `y` that must then be uncomputed.

## Fixed-point arithmetic

Circuits work on integers. A fixed-point number is an integer `v` standing for `v / 2^f`, where `f`
is the number of fractional bits. Adding two such numbers with the same `f` is an integer add.
Multiplying `f1` and `f2` fractional bits gives `f1 + f2` fractional bits, so you truncate: drop the
low bits that exceed the width you want. The reference circuit writes `T(.)` for this and its
model reproduces the circuit exactly. Each truncation adds an error of at most one unit in the last
place. Wider registers cost more Toffolis (a multiplier is roughly quadratic in width) and more
qubits, so the whole game is to use the narrowest widths that stay inside `2^-24`.

## Newton-Raphson

Newton's method for `1/sqrt(M)` iterates `y <- y (3 - M y^2) / 2`. It needs no division, only
multiplications. Its useful property is that the relative error roughly squares each step:
`e1 ~ 1.5 e0^2`. If a guess is good to 3 digits, one step gives 6.

## The Quake trick

The famous Quake III routine gets a first guess with a bit hack. Reinterpret a float's bits as an
integer `i`, compute `0x5F3759DF - (i >> 1)`, and reinterpret back. That halves the exponent and
flips its sign, which is nearly `1/sqrt`. One Newton step then cleans it up. The block below runs
it and counts the steps needed to meet `2^-24`.

```python
import struct

import numpy as np


def quake_rsqrt(x, newton_steps=1):
    """The famous float32 trick: a bit hack for the first guess, then Newton steps."""
    i = struct.unpack("<I", struct.pack("<f", x))[0]
    i = 0x5F3759DF - (i >> 1)  # halve the exponent, negate it, fudge the mantissa
    y = struct.unpack("<f", struct.pack("<I", i))[0]
    for _ in range(newton_steps):
        y = y * (1.5 - 0.5 * x * y * y)
    return y


for steps in (0, 1, 2, 3):
    xs = np.geomspace(1, 3_133_452, 2000)
    err = max(abs(quake_rsqrt(float(x), steps) * np.sqrt(x) - 1) for x in xs)
    print(f"newton steps={steps}: worst relative error {err:.2e}  (2^-24 = {2**-24:.2e})")

# Newton squares the error: e1 is about 1.5 * e0^2.
e0 = 1e-3
y = (1 - e0) / np.sqrt(4.0)
x = 4.0
y1 = y * (1.5 - 0.5 * x * y * y)
print("e0 =", e0, " e1 =", abs(y1 * np.sqrt(x) - 1), " 1.5*e0^2 =", 1.5 * e0**2)
```

The hack starts at 3.4% error and needs three steps to pass the budget. Each step costs three
multiplications in a circuit, which is why the reference does something better
for the start.

## What the reference circuit does

`nr_reference_circuit.py` has three stages. In the paper's notation `x_norm` is `x` shifted so it
sits in a fixed range.

1. **Normalise.** Count the leading zero pairs `s` of `x` into a unary register (10 flag qubits)
   and shift `x` left by `2s`. Then `M = x_norm / 2^20` lies in `[1, 4)` and
   `1/sqrt(x) = 2^(s-10) / sqrt(M)`. Shifting by pairs keeps the square root exact, since
   `sqrt(4^s) = 2^s`.
2. **Initial guess.** Pick one of four intervals (`[1,1.5)`, `[1.5,2)`, `[2,3)`, `[3,4)`) from
   the top three bits, load the cubic's four coefficients from a small table with cheap gates
   (the source says this is Clifford, so no Toffolis), and evaluate by Horner's rule. Only two
   cubics are fitted, one for `[1, 1.5)` and one for `[1.5, 2)`; the other two intervals reuse them
   with rescaled coefficients (`POLY_A` and `POLY_B` in the reference source, four coefficients each):
   `y0 = c0 - T(r2 d)` with `r2 = c1 - T(r1 d)` and `r1 = c2 - T(c3 d)`, where `d` is `M` minus the
   interval start.
3. **One Newton step.** `p = y0 (3 - M y0^2)`, which is about `2/sqrt(M)`, then shift back by `s`
   with unary-controlled swaps. The `1/2` of the Newton formula is absorbed in the bookkeeping.

Then it applies `Z_POW` per bit and runs stages 1 to 3 in reverse. Register widths (fractional bits)
are 14 for `d`, 17 for coefficients and Horner values, 28 for `y0^2`, 28 plus two integer bits
for `M y0^2`, and 29 for `p`.

Below is a numpy model of the same pipeline with my own cubic fits (the reference ships its own
coefficients) and the same widths. It is not the circuit, but it shows the budget being met.

```python
import numpy as np

NP = 10
WIDTH = 2 * NP + 2  # x has 22 bits
MAX_X = 3 * (2**NP - 2) ** 2
COEF_BITS, SQ_BITS, Z_BITS, P_BITS = 17, 28, 28, 29  # fractional bits, as in the reference

# Cubic fits of 1/sqrt(M) on four intervals of [1, 4). Only used to make y0.
EDGES = [1.0, 1.5, 2.0, 3.0, 4.0]
GRID = [np.linspace(lo, hi, 400) for lo, hi in zip(EDGES, EDGES[1:])]
POLYS = [np.polyfit(g - g[0], g**-0.5, 3) for g in GRID]


def trunc(v, bits):
    """Drop every bit below 2^-bits (the circuit's T(.) operation)."""
    return np.floor(v * 2.0**bits) / 2.0**bits


def invsqrt_model(x):
    x = np.asarray(x, dtype=np.int64)
    s = (WIDTH - np.floor(np.log2(x)).astype(np.int64) - 1) // 2  # leading zero pairs
    m = (x << (2 * s)) / 2.0 ** (WIDTH - 2)  # normalised: M in [1, 4)
    y0 = np.zeros(len(x))
    for k, (lo, p) in enumerate(zip(EDGES, POLYS)):
        sel = (m >= lo) & (m < EDGES[k + 1])
        c = np.round(p * 2.0**COEF_BITS) / 2.0**COEF_BITS  # coefficients to 17 bits
        d = m[sel] - lo
        r = c[0]
        for coef in c[1:]:  # Horner: r = r*d + coef, truncated at each step
            r = trunc(r * d, COEF_BITS) + coef
        y0[sel] = r
    sq = trunc(y0 * y0, SQ_BITS)  # y0^2
    z = trunc(m * sq, Z_BITS)  # M * y0^2, close to 1
    p = trunc(y0 * (3 - z), P_BITS)  # about 2 / sqrt(M)
    return (p / 2) * 2.0 ** (s - NP)  # undo the normalisation: 1/sqrt(x)


rng = np.random.default_rng(0)
xs = np.concatenate([rng.integers(1, MAX_X + 1, 300_000), np.arange(1, 3000), [MAX_X]])
approx = invsqrt_model(xs)
rel = np.abs(approx * np.sqrt(xs.astype(float)) - 1)
print(f"worst relative error {rel.max():.2e} = 2^{np.log2(rel.max()):.2f}")
print(f"budget 2^-24 = {2**-24:.2e}; reference circuit worst case 2.84e-08")
```

Sampled, not exhaustive, so treat the printed number as a lower estimate of the true worst case.
The reference's own tuned model reports `2.84e-8` (`2^-25.07`) at `x = 2,588,411`.

## Where the cost goes

The paper's figures for the reference circuit at `n_p = 10`: `Q = 260` qubits, 7,735 Toffolis,
1 T gate, 37 non-Clifford rotations, so `C = 7,988` and the score `Q * C = 2.08e6`. Per direction
(forward, then the reverse repeats most of it), the paper breaks the Toffolis down like this:

| Stage | Toffolis |
|---|---|
| Normalise (`n_p (n_p + 2)`) | 120 |
| Horner, three steps | 1,071 |
| Square `y0^2` | 442 |
| Multiply by `x_norm` | 1,043 |
| `3 - z` | 28 |
| Final multiply `y0 (3 - z)` | 867 |
| Denormalise (CSWAPs, `30 n_p`) | 300 |
| Sum | about 3,870 |

The reference source says "about 3.9k Toffolis per direction", which matches. The three Horner steps and the three Newton
multiplications account for about 88% of that sum (3,423 of 3,871). The `Z_POW` rotations are about 3% of the total: each costs
`0.56 log2(1/eps) + 5.3` T gates and `eps` is the margin left after the arithmetic error. From the
reference numbers (inferred, not in the paper): the margin gives `eps` near `2^-39`, so about 27
T gates per rotation and 1,012 T in total, which is the 253 Toffoli equivalents between 7,735
and 7,988. The verifier computes `eps` as `pi * min_margin / 2^64 / n_rot` from the simulated
error margin, so the exact figure needs the full 200M-shot run; the Kaggle-measured baseline cost
of 2,076,774 against `260 * 7,988 = 2,076,880` agrees with this to five digits.

The cost has three parts to push on: fewer or narrower multiplications, a better starting guess so
the Newton step can be cheaper, and qubit count, since the score multiplies `Q` by `C`. The reference
uses only half its error budget (`2^-25.07` against `2^-24`), and spending that slack on narrower
registers is the obvious first idea. The public notebooks listed in
[COMPETITION.md](../COMPETITION.md) report a table plus quadratic evaluation in place of Newton.
We have not verified that.

Checked against the source: building the reference circuit with kickmix gives 260 qubits, 7,735
Toffolis, 1 T-like gate and 40 `Z_POW` rotations (2 Clifford, 1 T and 37 others, matching the
paper's 37 non-Clifford rotations). The shipped baseline `invsqrt.kmb` has the same counts. The
registers the source names add up to only 231 qubits (22 for `x`, 40 for `y1`, 10 flags, 3
selectors, 68 for the four coefficients, 28, 30 and 30 for the square, `z` and scratch). The other
29 are not in any named register. The top-level code allocates nothing else, so they must come from
scratch space that the kickmix routines it calls (multipliers, shifts) allocate internally. We have
not traced which routine uses how many.

## Exercises

1. Starting from the Quake guess at 3.4% error, how many Newton steps reach `2^-24`? Use
   `e1 = 1.5 e0^2`.
2. At the largest input `x = 3,133,452`, what is the allowed phase error `tol(x)` in turns? The
   verifier requires it to be at least `2^-48`. Does it pass?
3. `y0` has 17 fractional bits and `y0^2` is kept at 28. How many fractional bits does the exact
   square have before truncation, and how many bits are dropped?

## Answers

1. `3.4e-2 -> 1.7e-3 -> 4.6e-6 -> 3.2e-11`. Three steps. The block above shows the first three
   results.
2. `2^-24 / sqrt(3,133,452) = 5.96e-8 / 1770 = 3.4e-11`, about `2^-34.8`, which is above `2^-48`.
3. Exact square: `17 + 17 = 34` fractional bits. Keeping 28 drops 6.
