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

## Hypothesis (S5, QCC-63)

The public v13 circuit routes under a measured flag: `hmr` the flag, apply the swaps as classically conditioned `SWAP`
(free, `PUSH_CONDITION` blocks), and pay the phase debt where the flag is recomputed. That would remove the CSWAPs, add
the 5x classical instructions, and cost only the recomputation of the flag. Prediction: removing the 12,384
CSWAPs alone takes our static T to 372,378 (ratio about 69.5x); the remaining 3,400 T (0.9%) are the 759 T of the adaptive
gauge scan plus the `CCX` and `CCZ` residue.

Not yet tested. The v13 source is not available to us (the dataset dropped the archives), so this has to be derived from
our own vendored v12 window code and our own wiring, not read from his.

## Next experiment

Narrow instance first: wrap `route` of the window object so the flag is released before the routing block and the routing
becomes a conditional swap, pay the debt where the closing code recomputes the flag, check the narrow instance verifies
(official verifier, narrow), then Toffoli and qubit deltas per stage. Then full size on Kaggle at 10 salts.
