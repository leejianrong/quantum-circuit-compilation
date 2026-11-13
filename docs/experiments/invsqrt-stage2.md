# invsqrt stage 2: what the 62-qubit frontier is made of (QCC-13)

ADR-0009 stage 2 (approved for all tracks 2026-11-13): we studied the structure of the public invsqrt `c6519219`
(cost 94,599.6, 62 qubits; `docs/PROVENANCE.md`) to understand its architecture. Method: dump to text with kickmix in
a scratch directory (nothing under `public/` was touched, nothing committed), then (a) count gates per stage and
per qubit lifetime, (b) simulate prefixes of the circuit on chosen inputs and read the qubits and the accumulated
phase, (c) compute algebraic degrees of qubit values as functions of the input. No gate list, table or constant was
copied or is reproduced here; every number below is a measurement of the circuit, every mechanism is our reading.

**Result: no new verified circuit. Ratio 15 and the frontier were not reached; our best stays E023 (93 qubits, 168,237.4,
ratio 12.34).** What this note delivers is the stage budget of the frontier, which pins down where the missing 1.8x
is, and four mechanisms we understand well enough to implement next. Stage-2 milestones in `bench exp` were not
opened because no circuit was built.

## Same math, different engineering

Probing the final phase on a grid of inputs shows the frontier uses our mathematics: a coarse word (16 rotations at
`2^-17 .. 2^-2`, constant on each segment) and a fine word (26 rotations at `2^-35 .. 2^-10`), a degree-2
piecewise polynomial with 7 bits below the leading one in each binade (256 table entries, parity of the leading-zero
count as the 8th address bit), relative error about `2^-24.4` (ours `2^-24.16`). Quadratic fits per segment leave
`2^-25` residual and cubic fits add nothing, so the polynomial degree and segment count are the same as E023. The
gap is therefore not an algorithmic one in the approximation; it is in how the pieces are built.

## Stage budget (static Toffoli-like, executed in brackets, `HMR`-measured temporaries free)

| Stage (instruction range) | Frontier | Ours (E023) |
|---|---:|---:|
| normalise (0-460): 19 AND chain + 47 CSWAP | 67 | 105 |
| lookup (460-7,300): 166 CCX, about 6,500 CX | 166 | 254 |
| lookup erase (7,300-8,340 and 25,100-32,500): about 6,600 conditioned CZ, no Toffoli | 0 | 25 |
| coarse word phase (8,340-9,150), one working qubit | 82 (76) | 107 |
| arithmetic and fine phase (9,150-16,300, 16,300-25,100) | 146 + 294 + 65 + 275 + 60 + 119 = 959 (about 750) | 372 x 2 + 164 = 908 |
| un-normalise (32,500-36,473) | 118 (74) | 101 (90) |
| **total** | **1,393 (1,234)** | **1,498 (1,487)** |

Conditional execution (294 `PUSH_CONDITION` blocks, executed fraction `2^-depth`) removes 155 Toffolis: 40 in the first
half of the post-fine region, 64 in the second, 40 in the un-normalisation. Ours removes 11.

The arithmetic stage is not smaller than ours (959 static against 908). The frontier's advantage is lookup (-113),
normalisation (-38), coarse phase (-25) and conditional execution (-150, shared across stages) and, above all, the
qubit count (62 vs 93: a 33% cut by itself).

## Mechanisms understood

1. **Lookup by CX-and-AND networks.** 166 CCX for 256 entries of about 37 output bits, with 40 CX between
   consecutive CCX that rewrite the address qubits in place and fan results out to the outputs. A truth-table check
   shows each output bit has algebraic degree 7 to 8 in the 8 address bits (full, about 128 monomials) and degree
   exactly `k` in every aligned block of `2^k` addresses for `k = 2, 3, 4`: the table is generic, not designed to be
   low degree. A split `n = p + q` with `p = 6, q = 2` gives `(2^6 - 7) + 1 + 37 * 3 = 169` ANDs, which matches the
   count (hypothesis; the circuit mixes in basis changes so it is not exactly this). Unary iteration pays 2 per
   entry-pair, hence our 254. Uncompute is free: the outputs are measured and the fix-up
   `(-1)^{m.f(a)}` is a sum of `CZ` terms over the address and a conditional `CCZ`.
2. **Normalisation by thermometer chain.** The first 19 Toffolis build `t_j = [top j bits are zero]` as a prefix AND
   chain. The binary digits of the shift are then plain parities of the `t_j` (free CNOTs), because
   `bit_k(z) = XOR over m>=1 of t_{m 2^k}`. The shift uses controlled swap sequences on reversed segments, about 10
   CSWAP per level against our 14 to 21, and the chain is erased early by `HMR` with Z/CZ fix-ups, leaving only the 5
   binary flags. Ours builds the flags directly with `multi_controlled_x` (26 Toffolis) plus 79 CSWAP.
3. **One working qubit for every rotation.** Each of the 42 non-Clifford `Z_POW` sits on the same qubit, which is loaded
   from the shifted word by a 2-3 CSWAP multiplexer on one-hot-style shift flags, rotated, measured, and fixed
   up with CZ. We measured this idea in `invsqrt-bitserial.md` (a loss in a design that stores the word); the
   frontier keeps no stored shifted word, the multiplexer reads from the word where it was produced.
4. **Conditional blocks as measured uncompute of controlled products.** The condition blocks contain chains of
   `CX ... if b` that XOR classically selected register bits into one qubit (a parity `m.R` of a measured register),
   then one `CCZ` with two other live qubits, all inside `PUSH_CONDITION if (parity of outcomes)`. That is the
   fix-up of an erased AND of two live qubits with a word, run only when the classical parity is 1.

Mechanisms 1 and 4 together explain why there is no mirror of the Horner stage: the stage is run once forward, its
registers are erased by measurement, and only the controlled-product fix-ups cost Toffolis. We could not
reconstruct which registers play which role in the arithmetic (post-fine) stage, so we did not build it.

## Qubits

Peak 62 = 22 `x` + 40. Lifetimes: the 18 thermometer qubits live only through the first 450 instructions; the lookup
stage holds 38 output qubits plus about 10 scratch; the arithmetic stage holds 40 for 20,000 instructions (the
`x` bits are never moved after normalisation, including the low 14 bits, which are used up only in the fine block);
the erase stage keeps 40 qubits alive for 7,000 instructions of pure `CZ`. The 5 flags are included in the 40.
Everything is reused through measured-and-reset qubits (about 900 lifetimes over 62 wires).

## What a next attempt should do

In order: (a) thermometer normalisation, about -80 Toffolis in total, predictable with `predict.py`; (b) a blocked
Reed-Muller lookup (`docs/research/invsqrt.md` idea 1) with its `HMR` plus conditional `CCZ` erase, about -110; both
fit inside 93 qubits and move 168k to about 148k (ratio 14.0). Ratio 15 then needs a qubit cut (peak 93 to 85 at equal
Toffolis); the frontier needs the post-fine stage understood, which is the part not reconstructed here.

## Not done

No generator variant was written: the two mechanisms with an explicit algorithm (1, 2) each need a new gadget
(sparse-support Reed-Muller synthesis with don't-cares, reversal shifts with a thermometer erase) plus the model
and test changes this repository requires (a bit-exact model per gadget), and the evidence for their exact form is
partial. Negative findings: the frontier's table is not co-designed to low degree (idea 2 of the research note does
not explain it), and its arithmetic stage is not cheaper than ours.

## Reproduce the measurements

Scripts lived in the agent scratchpad (not committed): dump with `km.Circuit.from_file(...).to_file(out, format='kmx')`;
stage counts by instruction range; prefix simulation with `km.Simulator`, `write_across_shots('x', bits)`, `do`,
`read_across_shots(km.q(i))`, `read_shot_phase(i)`; algebraic degree by Moebius transform of a qubit's truth table.

## Follow-up costing of the three levers (2026-11-13, no circuit built)

Costed against our generator before writing code, because each lever turned out to fail for our qubit budget.

* **Conditional execution (lever 1).** The frontier's saving sits in blocks that fix up an erased AND of two live qubits
  against a classically selected parity of a measured register. Our Horner mirror erases in-place sums, which cannot
  be fixed up that way (`invsqrt-uncompute.md`), and our only erasable Toffoli blocks (flag clears) are already
  conditional. No candidate block exists in our architecture; it needs the frontier's different arithmetic stage,
  which was not reconstructed. Gain with today's layout: 0.
* **Thermometer normalisation (lever 2).** The chain replaces our 26-Toffoli `multi_controlled_x` ladder by 19, a
  saving of 7 forward. A move of `22 - m` bits into known-zero slots costs one Toffoli per bit whether written as a
  CSWAP or as `Toffoli + CX`, so the 79 CSWAP of the shifts only fall if the frontier's reversal trick (about 10 per
  level, orientation of the register not restored between levels) is reproduced; we could not derive how the later
  stages then read the address. Gain with a derived design: 7 of 40 hoped; the rest unproven.
* **Blocked Reed-Muller lookup (lever 3).** Cost `2^p - p - 1` (high monomials) `+ 2^q - q - 1 + m (2^q - 1)` Toffolis,
  with the `2^p - p - 1` monomials alive as qubits:

  | m outputs | p, q | Toffolis | extra qubits |
  |---:|---|---:|---:|
  | 37 | 6, 2 | 169 | 57 |
  | 37 | 7, 1 | 157 | 120 |
  | 37 | 5, 3 | 289 | 26 |
  | 51 (ours) | 6, 2 | 211 | 57 |
  | 51 | 5, 3 | 387 | 26 |

  Our lookup stage already sits at 92 of 93 qubits, so the 57 qubits of the cheapest split cost about 57 x 19 =
  1,080 Toffoli-equivalents against a saving of 43 to 70. The frontier's 166 with 38 output qubits therefore
  cannot be this scheme with stored monomials; it computes products of address parities directly into the outputs
  with CX basis changes between them, a synthesis we did not reconstruct. Negative for our layout.
* **Qubit cut (lever 4).** Depends on 1 to 3. No cut derived.

Conclusion: dead end for a patch of the Horner generator; the frontier needs a rebuilt architecture (one forward
pass, no mirror, products erased by conditional fix-ups) whose arithmetic stage we have not recovered.
