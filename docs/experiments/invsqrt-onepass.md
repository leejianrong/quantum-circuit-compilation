# invsqrt one-pass study: running the 62-qubit frontier and reading its registers (QCC-13)

ADR-0009 stage 2 (approved for all tracks 2026-11-13, amendment rules apply): the previous note
(`invsqrt-stage2.md`) read the public invsqrt `c6519219` (`docs/PROVENANCE.md`, 62 qubits, 94,599.6) by counting gates
and by prefix simulation of small pieces. This note is the dynamic version: we ran the whole circuit with kickmix's
`Simulator` on 720 chosen inputs (every normalised segment parity, 10 segments, 6 leading-zero counts, 12 remainders
each) and on all 256 addresses with four remainders, recording every qubit at every 50 instructions and the value on the
rotation qubit at each of the 45 `Z_POW`. Qubits were grouped by class (constant, function of the address, function of
the address and the leading-zero count, function of the remainder) and by what touches them. Nothing under `public/` was
edited or committed, the dump was written to the agent scratchpad, and no gate list, table, constant or code is reproduced
here: every number is a measurement, every mechanism is our reading, in our words.

**Result: no new verified circuit and no milestone reached (our best stays E023: 93 qubits, 168,237.4, ratio 12.34).**
The study corrects two statements of the stage-2 note, measures the frontier's qubit budget stage by stage, and shows
which of the three big levers (lookup, qubit census, conditional fix-ups) is implementable by us and at what cost. A fresh
one-pass generator was designed (last section) but not built: the lookup needs a synthesis tool that does not exist yet.

## Timeline (instruction index in the text dump; 36,450 instructions)

```text
 0      460        7,300     8,340    9,150  10,600   12,354    14,104    16,124 16,304     25,141      32,500   36,450
 |norm  |  lookup (CX/AND)   | coarse | clear |fix-ups |step 1   | step 0  |fine  | unwind    | table erase | unnorm |
 |19 AND|  166 CCX, 6.5k CX  | phase  |addr + |CZ only |V1+=r V2 |V0+=r V1 |26 rot| 439 CCX   | CZ only,    | 118    |
 |47 CSW|  39 outputs        | 8 bits |coarse |        |117 CCX  |212 CCX  |1 qubit| conditional| 25 qubits   | CCX    |
 live: 5  22 + 39 (+10)        62 -> 47   47     47        ~62        62      ~32      62          25           ~55
```

Every non-Clifford rotation sits on one working qubit; the other 62 - 1 are never rotated.

## Findings (measured)

**M1. The phase is coarse word + fine word, with tuned angles.** Summing the 45 rotations weighted by the bit on the
working qubit reproduces `2^(s-10) / sqrt(M 2^(1-parity))` on all 720 inputs with worst relative error `2^-24.16`
(the same number as our E023 model). The coarse word is 8 data bits, constant on every (parity, segment) pair, applied
at 8,340-9,150 before any arithmetic. The fine word `F` is 19 data bits at `s = 0`, nonnegative and below `2^-7`
(in units of `Y`), applied at 16,124-16,304. Per segment `F` is a quadratic in the remainder with residual `2^-25.3`
(linear fit: `2^-18.3`), so degree 2 with 256 table entries, as in our design. The rotation angles are not exact
powers of two: the lowest fine positions are off by about 1.2% (`log2` -35.012, -33.987, -33.007, then 0.1% and
less) and the coarse ones by about `2^-22` relative. These are margin-scale tweaks of the rotation set, free in
the cost model, and worth about 5 Toffoli-equivalents in rotation cost or a fraction of a bit of error budget.

**M2. The table registers are also the polynomial registers, as in ours.** The 39 table qubits (class "function of the
address" from instruction 650 on) turn into functions of the remainder at 12,354 (11 qubits) and 14,104 (about 20 qubits), and every one of them returns to a function of the
address only at 25,141 and 22,056 respectively. So this is a forward pass and an unwind, not a mirror-free one-pass
design: the stage-2 note's "no Horner mirror" reading is wrong. What differs is the unwind. The first half costs 117 + 212 `CCX`
(ours 372 per direction at E023), the second half 253 + 176 + 10 `CCX` with 164 condition blocks and 78 `CCZ`, and
the arithmetic total (about 760) is within 2% of ours. The adders are the same signed-digit rows (one remainder bit
complements a window by CNOTs, then one plain add), 14 rows per step, trimmed windows included.

**M3. The adder uses 11 to 16 temporaries, not a carry per bit.** Counting qubits that are created by a `CCX` and
destroyed by an `HMR` inside a row, the live temporary count never exceeds 13 in step 1 and 11 in step 0 for a 21-bit
window; carries are computed in short runs and erased in last-in-first-out order by measurement with `CZ` fix-ups
from the data qubits, with the run-boundary carries kept. Static `CCX` per row is not below `n - 1`, so this saves
qubits, not Toffolis. Our `ripple_add` keeps `m - 1` carries live, which is where our 17 transient qubits at the peak
come from.

**M4. Qubit census.** Persistent (never measured in the window) and measured-temporary qubits per stage:

| Stage | Persistent `x` low 14 | Persistent address and table | Temporaries | Total live |
|---|---:|---:|---:|---:|
| after coarse phase (9,500-10,500) | 0 (idle) | 43 | 4 | 47 |
| step 1 (12,354-14,104) | 8 of 14 used | 30 | 16 | 54 |
| step 0 (14,154-16,124) | 13 | 37 | 11 | 61 |
| unwind (18,354-22,056) | 13 | 35 | 13 | 61 |
| table erase (22,056-25,141) | 8 | 10 | 30 | 48 |

The "address and table" count includes six of the seven address qubits, which hold polynomial data in step 0. Ours at
the same point: 22 `x` + 5 flags + 49 table and Horner + 17 carries = 93. The 62 is most likely the sum of
three things (our reading; the first is measured, the other two are inferred from which qubits flicker): the table and
address data take about 37 qubits, not 49 + 8 + 5; the adders need 11 temporaries, not 17; and temporaries are drawn from
qubits that are idle at that moment (the eight coarse-word qubits after 9,154, address qubits 17 to 20 between 10,570
and 12,354). Where the five shift flags live after the normalisation chain is erased was not determined.

**M5. The lookup is an in-place network of ANDs of live linear forms.** The 166 `CCX` of the lookup write into 39
output qubits (23 outputs get five, 11 get four, 4 get one, 1 gets three), and the operand qubits are overwhelmingly
the address qubits (one fixed address qubit is an operand of 129 of the 166), which are rewritten between `CCX` by
about 6,500 CNOTs: each AND multiplies two linear forms of the *currently live* qubits, so address qubits and
finished outputs act as variables for later ANDs. This is a Boolean-circuit synthesis result (low multiplicative
complexity with a bounded live set), not a unary iteration and not a table-structure trick (the truth tables are
generic, degree 7 to 8). Erasing it is free: measure each output in reverse order, the phase fix-up of an AND of two
live linear forms is one `CZ`.

**M6. The only conditional `CCZ`s are folded fix-ups.** A phase fix-up of the form `(u AND v) * (sum over t of c_t q_t)`,
with `c_t` classical (parities of measurement outcomes), is applied as: conditional `CX` of the chosen targets into one
qubit, one `CCZ(u, v, that qubit)`, undo. The block is inside `PUSH_CONDITION` on the parity bit, so the `CCZ` runs on
about half the shots (nested conditions run on `2^-depth`). Cost: one Toffoli-like per fix-up, executed rarely, instead
of one per `t`.

**M7. Address qubits are cleared mid-circuit.** At 10,520-10,570 eight address and scratch qubits are rewritten by XORing
table qubits into them and measured (`HMR`), followed by about 700 conditional `Z` and `CZ`, and they sit at 0 until
12,354, where they serve as carry qubits. Only two linear forms of the address lie in the span of the table columns
(the parity bit and the XOR of the seven address bits), so the clearing is not free by linearity; the fix-up phase of
the measured address bits is a quadratic in the table qubits. We could not rebuild which table design makes that
possible.

## What the dynamic view changes in our plan

| Lever | Stage-2 estimate | After dynamic analysis |
|---|---|---|
| Lookup 254 + 25 to 166 | needs a Reed-Muller layout with 57 extra qubits | wrong frame: the frontier has no extra qubits (about 10 scratch). The structure is an in-place AND network (M5). A search procedure is needed; counting says a search can succeed (below). |
| Normalisation 105 to 67 | thermometer chain, derived | unchanged (already costed: saves 7 in our layout) |
| Conditional execution (-155) | blocks of conditional Toffolis | only in the unwind and the table erase, as folded fix-ups (M6); our unwind is a mirror of unconditional adds, so nothing to fold until the unwind is measurement-based |
| Qubits 93 to 62 | "rebuilt one-pass architecture" | no mirror-free architecture exists; the 31 qubits are layout: narrower table, flags inside the table, short-carry adders, recycled idle qubits (M3, M4) |
| Arithmetic | not reconstructed | same rows as ours, same cost (M2); no gain here |

So the next lever, in order of expected return per effort:

1. **Short-carry adder (M3).** Replace `ripple_add`'s `m - 1` live carries with runs of about 5 carries and
   last-in-first-out measured erasure, run boundary carries kept. Estimate at equal Toffolis (not predicted with `predict.py`): 93 to about 84 qubits
   (-10%, ratio 13.7). This is our own gadget to design and unit-test against the bit-exact model; the open point is
   whether the boundary carries can be erased without extra ANDs (our analysis in `invsqrt-uncompute.md` says an
   in-place sum cannot be erased for free, but an adder built from runs is a different object; the frontier shows
   11 temporaries at a window of 21).
2. **Idle-qubit recycling.** The coarse word (9 qubits), the address qubits after the table is loaded and the leading-one
   qubit are idle during the adders. Using them as the adder temporaries removes allocation instead of adding it.
   Together with 1 this should reach the high 70s (ratio 15).
3. **Lookup as an in-place AND network.** Needs a synthesis search; it removes 100 to 110 Toffolis (7%) and nothing
   else. Counting: a new output on a live set of dimension `d` is described by `2d` bits per AND (two linear forms),
   a 256-bit truth table needs at least `256 / (2d)` ANDs, about 3 at `d = 45` and 5 at `d = 25`; the frontier
   averages 4.3. A greedy search that picks the pair of live linear forms whose product reduces the Hamming distance
   to the next target the most, with the live set grown by finished outputs, should reach 5 to 6 per output
   (about 200 total, -50 Toffolis) as a first target.
4. **Measured unwind** of the Horner stage (the second half of M2), which is where the frontier's conditional
   blocks live. Not derived by us yet.

## One-pass design (not built)

We do not copy the frontier's circuit; the architecture we would build from M1 to M7 is:

```text
x (22)  ->  normalise (thermometer, flags kept as 5 binary qubits)
        ->  lookup by in-place AND network: table words (coarse 8, fine 19, slope 12 + 6, quad 7) in ~37 qubits
        ->  coarse word phased through the working qubit, then its 8 qubits and 4 address qubits become scratch
        ->  step 1, step 0: signed-digit rows with short-carry adders, scratch drawn from idle qubits
        ->  fine word phased through the working qubit (tuned angles)
        ->  unwind by the same rows (later: by measurement), lookup erased in reverse by measurement
        ->  un-normalise
```

Error analysis (ours): relative error budget `2^-24` of `2^(s-10) Y`; the polynomial minimax error at `a = 7`, degree 2
is `2^-27.7` (table in `invsqrt-uncompute.md`), so about `2^-25` is left for coefficient and truncation noise: that is why
`F` needs 19 data bits and the rows can drop to `2^-26`. The tuned angles (M1) should be fitted by a linear program over
the reachable inputs, per rotation position, against the margin `2^(s-10) Y (2^-24 - |err|)`.

## Not done, and why

* No generator code: the first lever (short-carry adder) needs a verified-by-model gadget (new `ripple_add`, bit-exact
  model, tests), and the second depends on it. The lookup synthesis (third lever) is a separate research tool.
* Stage-2 milestones in `bench exp` for a one-pass build were not opened: no circuit exists.
* Attempted and abandoned: decoding the table basis. The 39 table qubits are not the bits of `c0`, `c1`, `c2` (none of
  `F(r = 0)`'s 20 bits lies in their GF(2) span, nor do the address bits), because the network keeps XOR-mixed bases and the
  stored constant is the value at the segment centre, so the widths of `c1` and `c2` could not be read.

## Reproduce

Scripts were in the agent scratchpad (not committed): dump with `km.Circuit.from_file(...).to_file(out, format='kmx')`;
simulate in chunks of 50 instructions outside condition blocks with `km.Simulator(n, seed=...)`,
`write_across_shots(km.q(k), bits)`, `do(km.Circuit(text))`, `read_across_shots`; the rotation value trace by running up
to each `Z_POW` and reading the working qubit; classes by constancy within groups of equal address, address and
leading-zero count, or remainder; GF(2) spans of the 256-address truth tables for the linear-form tests.
