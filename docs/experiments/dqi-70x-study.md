# DQI: where the public 70.04x circuit beats our `fixed4` (QCC-19, S5 lead)

Kaggle kernel `qcc-dqi-study-public` (`notebooks/dqi_study_public`, counts only through `dqi_gen.study`) on koushikrudra's
`00ac37d4` (890 qubits, in `best/`) and our `fixed4` (`599cb515`, 889 qubits). Output kept under `out/kaggle/` (gitignored);
numbers below are copied. [M] unless marked.

## The gap by gate type

| | `fixed4` (ours) | `00ac37d4` (public) | difference |
|---|---:|---:|---:|
| static Toffoli-like total | 384,762 | 368,991 | 15,771 (4.1%) |
| `CCX` | 365,309 | 362,965 | 2,344 |
| `CCZ` | 7,069 | 6,026 | 1,043 |
| `CSWAP` | **12,384** | **0** | **12,384 (79%)** |
| `SWAP` (free) | 380,182 | 382,091 | |
| `PUSH_CONDITION` | 496,132 | 2,576,153 | 5.2x |
| `BIT_INVERT` | 3,677,255 | 18,494,894 | 5.0x |
| `BIT_STORE0` | 218,552 | 2,825,199 | 13x |
| `HMR` | 72,221 | 72,070 | same |
| instructions | 37.9 M | 58.5 M | |

The cost ratio gap, 70.04 / 67.30 = 1.041, is the static Toffoli gap (4.1%); the one extra qubit of the public circuit
costs it 0.2%. The public circuit has no `CSWAP` at all and runs five times as many classical-condition instructions.

## Where our CSWAPs are

The narrow instance builds with the same CSWAP count as the full one (12,384), so it can be used to locate them
(`instances.build("fixed4", narrow, stage_log=...)`, counted between `stage:` tags [M]): 11,376 of 12,384 (92%) sit
in the two groups `stage:odd_border_and_elimination` (5,688) and `stage:shared_seam_undo_odd_full_preimage` (5,688). The first
is the outer's window transpose `core.emit(...)` after the odd border, the second its undo. The remainder are 24 per
node in the raw-query prefix and return (about 48 per node in all).

In the vendored window code (`third_party/syed_dqi/.../after_v3/blocks/transpose_handoff_window.py`) the routing step
`route()` does `cswap(flag, B[-1], B[-2])` (or a controlled cyclic rotation of the word `B` under `flag`) with a
**quantum** flag qubit. The same file already has `release()`, which measures the flag with `hmr`, frees it, and
keeps the outcome as a classical `flagmask` whose phase debt (`cz(flagmask, flag)`) is paid later.

## Hypothesis (S5, QCC-63), corrected the same day

First reading (wrong): the public circuit routes under a measured flag with conditional swaps. **This is not valid.** The
flag is `toggle_zero(B[-1], flag)`, a data-dependent predicate of a quantum register. `hmr` measures in the X basis and only
helps uncompute a bit whose phase debt is paid later; measuring the flag in the computational basis to route classically
would collapse the superposition, pass on basis-state inputs and fail as a quantum circuit. No competition gate set
allows it, and the five-fold classical instructions of the public circuit are most likely deferred-mask bookkeeping
(parities of `HMR` outcomes, the "GF(2^24) closings" of the v13 notes), not routing.

What stands: the public circuit has no `CSWAP` and 15,771 fewer static Toffolis; 79% of that is the count of CSWAPs in our
outer window routing. A controlled swap of two words costs one Toffoli per bit however it is written, so the public
design must avoid the data-dependent swap or keep the two words in a layout where the swap is a relabelling. How it does
this is unknown; the v13 source is not available to us.

## Condition statistics (2026-11-19, Kaggle, `dqi_gen.study` with condition counts)

Per operation, conditioned means inside a `PUSH_CONDITION` block or with an inline `if bN`; the origin is whether the
condition bit was written by an `HMR` (a measurement outcome) or by derived classical bit logic [M].

| op | ours conditioned / plain | public conditioned / plain | condition bit from HMR / derived (ours) | (public) |
|---|---:|---:|---:|---:|
| `SWAP` | 258,513 / 121,669 | 269,424 / 112,667 | 159,202 / 99,311 | 167,351 / 102,073 |
| `CX` | 922,587 / 30,372,086 | 916,940 / 29,409,640 | 677,289 / 245,298 | 629,217 / 287,723 |
| `CCX` | 45,687 / 319,622 | 45,519 / 317,446 | 3,815 / 41,872 | 4,099 / 41,420 |
| `CCZ` | 7,069 / 0 | 6,026 / 0 | 2,903 / 4,166 | 1,944 / 4,082 |
| `CSWAP` | 0 / 12,384 | none | | |

Toffoli-like gates by nesting depth of conditions (0, 1, 2): ours 332,006 / 48,171 / 4,585; public 317,446 / 46,498 / 5,047.

What this settles:

1. **Conditions are not where the public circuit wins.** The two circuits condition their gates the same way to within a few
   percent, with the same split between measurement and derived bits. The five-fold count of `BIT_INVERT` and `PUSH_CONDITION`
   instructions is classical bookkeeping (how the same bit parities are written out), not a different quantum design.
2. **The whole gap is in unconditioned Toffolis**: depth 0 differs by 14,560 (ours is higher), of which our 12,384 `CSWAP`s (all
   unconditioned) are 85%; the remaining 2,176 are plain `CCX`. Depth-1 and depth-2 counts are within 4%.
3. So the public circuit avoids a data-dependent word swap that ours performs coherently. A routing swap decided by a quantum flag
   cannot be skipped without changing what the circuit computes. Options: a different algorithm (no swap needed in its
   continued-fraction or Cayley step), or a priced approximation that ignores the degenerate branch and pays for it in failures.
   The second looks unlikely to pay: `R(epsilon)` reacts strongly to failed shots (2 failures in the public draw moved the
   leaderboard score 0.3%), and the degenerate branch (`B[-1] = 0` in GF(2^12)) has probability about 1/4096 per node.

## Status of S5

Both cheap ideas are closed: measured-flag routing is invalid, and conditioning is not the difference. What is left is to find
the algorithm that needs no data-dependent swap. Without the v13 source (the dataset dropped the archives) that is a design
question for the Thiele/Cayley outer, not an engineering port. The adaptive gauge scan (759 T, 0.2%) stays as the small sure item.
S5 is parked at low confidence and not started further; S6 (an in-place Euclid history) is the same kind of design question and is
next.
