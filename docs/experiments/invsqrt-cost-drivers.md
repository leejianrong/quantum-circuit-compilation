# invsqrt: where the cost goes (QCC-11)

Audit of the host's Newton-Raphson reference (`data/verifiers/invsqrt/nr_reference_circuit.py`, 260 qubits,
cost 2,076,774) against the verifier's cost model, written to decide what our own generator
(`src/invsqrt/`, QCC-12) should attack. Numbers come from
`QCC_DATA=$PWD/data uv run python scripts/invsqrt_audit.py` (static counts per `mark` block) and
from kickmix `operation_statistics()` / `num_qubits`. The public frontier is used only as a total:
62 qubits, 1,393 static Toffoli-like gates (1,095 CCX, 93 CCZ, 205 CSWAP), 45 `Z_POW`, 871 `HMR`,
294 conditional blocks, cost 94,599.6 (ratio 21.95).

## What the cost formula rewards

`score = Q * C`, `C = E[toffolis executed per shot] + T / 4`, `Q = circuit.num_qubits` (the allocation
high-water mark).

1. **Q and C multiply**, so a 10% cut in either is worth the same. The reference is 260 x 7,988;
   the frontier is 62 x 1,526. Qubits dropped 4.2x, Toffoli-equivalents 5.2x.
2. **Toffolis are counted as executed, averaged over shots.** A Toffoli inside a
   `PUSH_CONDITION if bN` block on a measurement bit runs on about half the shots, so work that only has
   to happen when a random `HMR` outcome is 1 costs half. The static count is an upper bound
   (`max_toffoli_count` in the verifier output). The frontier's 294 conditional blocks and 871 `HMR`
   show it leans on this.
3. **Uncompute is not free.** The reverse pass repeats every arithmetic stage with the same Toffoli
   count (`isub` costs what `iadd` costs). Only the AND temporaries are free to clear (`del_and`: `HMR`
   plus a conditional `CZ`). The reference therefore pays each multiplier twice.
4. **Rotations are about 3%.** Non-Clifford `Z_POW` costs `0.56 log2(1/eps) + 5.3` T each, `eps` being
   what is left of the `2^-24` tolerance after the simulated arithmetic error, split over the rotations.
   Reference: 253 Toffoli-equivalents of 7,988. For the frontier the same arithmetic gives about 130 of 1,526
   (about 9%), so as everything else shrinks rotations matter more. Levers: fewer phased bits, and a
   smaller simulated error (more slack means a larger `eps`, fewer T per rotation).
5. **Accuracy slack is the budget.** Tolerance is `2^-24 / sqrt(x)` per `x`; the reference uses
   `2^-25.07`. Anything inside the tolerance can be traded for narrower registers.

## Reference Toffolis by stage (static, forward and reverse)

| Stage | forward | reverse | share of 7,735 |
|---|---:|---:|---:|
| normalize | 120 | 110 | 3.0% |
| select_interval + load coefficients | 3 | 0 | 0.0% |
| horner (3 steps, 14-bit `delta`) | 1,071 | 1,071 | 27.7% |
| square `y0^2` | 442 | 442 | 11.4% |
| multiply_m (`M * y0^2`) | 1,043 | 1,043 | 27.0% |
| correct (`3 - z`) | 28 | 28 | 0.7% |
| multiply_y0 (`y0 * (3 - z)`) | 867 | 867 | 22.4% |
| denormalize (CSWAP) | 300 | 300 | 7.8% |
| **total** | **3,874** | **3,861** | 100% |

Three multiplications of the Newton step plus the Horner chain are 88% of the Toffolis. All four are
schoolbook shift-and-add: one row per multiplier bit, each row is `AND` of the bit with the multiplicand
into scratch (width `w` Toffolis, cleared free) then a `w`-bit add (`w - 1` Toffolis), so about `2w`
Toffolis per row. `multiply_m` has 22 rows because it multiplies the 28-bit square by *all* of `x_norm`
although `M y0^2` is within `2^-13` of 1.

## Reference qubits

| Register | qubits |
|---|---:|
| `x` | 22 |
| `y1` (`29 + 1 + n_p`) | 40 |
| unary shift flags | 10 |
| interval selectors | 3 |
| coefficients `c0..c3` (17 each) | 68 |
| `y0^2` | 28 |
| `z` | 30 |
| shared scratch for row products | 30 |
| ancillas inside `iadd` / `isub` | 29 |
| **total** | **260** |

Measured with kickmix: `iadd` of `n` bits allocates `n - 2` carry ancillas (28 for `n = 30`, with `n - 1`
Toffolis); a controlled `iadd` costs `2n + 3` Toffolis (63 for 30 bits); `init_lookup` of `2^k` entries costs
`2^k - 2` Toffolis forward with `k` helper qubits, and `del_lookup` costs about 10 (`k = 6`) or 25 (`k = 8`).
So every wide adder holds a full carry register, which is where the 29 unnamed qubits come from, and
everything that is alive at the peak (the registers above, all at once) sets `Q`.

## What this says about the design

* **Qubits.** The reference holds `y1`, four coefficient registers, `y0^2`, `z` and scratch all alive
  together. A lean design keeps only what the current stage needs, phases an intermediate when it is
  ready (phases add, so `y1` need not exist as one register), and shrinks adder carries.
* **Toffolis.** The step that pays most is a full-width multiplication that only needs a few significant
  bits: `M y0^2 = 1 + e` with `|e| < 2^-12`, so `e` needs about 13 significant bits, not 28. Segments (more
  table bits) buy lower degree and narrower multiplications; a lookup costs about `2^k` Toffolis in the
  forward direction and almost nothing to clear.
* **Phasing.** `Z_POW` per bit of `y1` costs about 6 Toffoli-equivalents per bit at `eps` near `2^-35`.
  Phase the narrowest register that carries 24 relative bits and keep simulated error small.
* **Uncompute.** MBUC (`HMR` plus a conditional fix-up) is free for ANDs and cheap for lookups, and a
  fix-up that runs on half the shots costs half. Everything else the reverse pass repeats at full price, so
  designs where the late stages are cleared by measurement beat ones that mirror the forward pass.

Next: QCC-12 builds the parameterised generator (`src/invsqrt/`) and tests these levers one by one.
