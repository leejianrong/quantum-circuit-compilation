# Claims register

Each row is a statement the work depends on, with its status and the log entry that is the evidence. Statuses:
**holds** (measured, derived or verified), **model only** (holds in our cost model, not built or verified),
**unverified** (inferred or guessed, no experiment yet), **refuted** (shown wrong; the entry says by what).
Rows were extracted from the backfilled log entries on 2026-11-15; the entries, not this table, carry the detail and
the numbers. `tests/unit/test_knowledge.py` checks that every evidence link exists and every status is valid.

## invsqrt

| Claim | Status | Evidence |
|---|---|---|
| The score is `Q * C`, so a given percentage cut in qubits is worth the same as the same cut in Toffolis | holds | [cost drivers](../log/entries/2026-11-12-invsqrt-cost-drivers.md) |
| The host reference is 88% schoolbook multiplications (three Newton multiplications plus Horner) | holds | [cost drivers](../log/entries/2026-11-12-invsqrt-cost-drivers.md) |
| Serial or split phasing alone does not pay; the centered remainder does | holds | [bit-serial](../log/entries/2026-11-12-invsqrt-bitserial.md) |
| A streaming phase adder loses (+3.3% fine, +8.8% coarse) | holds | [phase adder](../log/entries/2026-11-12-invsqrt-phase-adder.md) |
| The Horner mirror cannot be replaced by measurement for in-place sums | holds (derived) | [uncompute](../log/entries/2026-11-13-invsqrt-uncompute.md) |
| E023 verifies at 93 qubits, cost 168,237.5, at all 5 salts | holds | [uncompute](../log/entries/2026-11-13-invsqrt-uncompute.md) |
| The 28,19,9 fit is infeasible | refuted: it only looked so without `--reachable` | [uncompute](../log/entries/2026-11-13-invsqrt-uncompute.md) |
| A 28,19,8 table would give about 166.5k | refuted: predicted 168,320 once the margin cost is counted | [one-pass](../log/entries/2026-11-13-invsqrt-onepass.md) |
| The 62-qubit frontier uses our mathematics (degree 2, 256 entries); its edge is engineering | holds | [stage 2](../log/entries/2026-11-13-invsqrt-stage2.md) |
| The frontier has no Horner mirror | refuted: forward pass plus an unwind | [one-pass](../log/entries/2026-11-13-invsqrt-onepass.md) |
| The frontier's lookup needs a Reed-Muller layout with extra qubits | refuted: about 10 scratch qubits | [one-pass](../log/entries/2026-11-13-invsqrt-onepass.md) |
| Coefficient rounding alone cannot explain the frontier's error at 16-bit slopes | holds (lattice argument) | [one-pass](../log/entries/2026-11-13-invsqrt-onepass.md) |
| The consuming multiplier is a dead end | refuted by reading the builder source; our own re-check is pending | [syed decode](../log/entries/2026-11-15-invsqrt-syed-decode.md) |
| Going from 48 to 46 qubits is worth 4.2% of the cost, the Toffoli change only 2.0% | holds (arithmetic) | [syed decode](../log/entries/2026-11-15-invsqrt-syed-decode.md) |

## dqi

| Claim | Status | Evidence |
|---|---|---|
| The score is `R * Q^2 * T`, so one qubit is worth about two Toffolis | holds | [cost drivers](../log/entries/2026-11-12-dqi-cost-drivers.md) |
| The reference's two Euclid passes are 73% of its 5,725,461 Toffolis | holds | [cost drivers](../log/entries/2026-11-12-dqi-cost-drivers.md) |
| Lanczos failures (about 0.75% of shots) are not fixable locally | holds | [failures](../log/entries/2026-11-12-dqi-failures.md) |
| Exact look-ahead costs about +30% T | refuted: only a lower bound | [look-ahead](../log/entries/2026-11-13-dqi-lookahead.md) |
| A perfect failure fix is worth at most 1.74x, and exact look-ahead is not worth building | holds (estimate) | [look-ahead](../log/entries/2026-11-13-dqi-lookahead.md) |
| The dialog is at its information minimum within the (S, v_g, v_f) state | holds for that state only | [qubits](../log/entries/2026-11-12-dqi-qubits.md) |
| The dialog-free BM decoder reaches ratio 7.86 at 10 salts with 0 failures | holds | [BM](../log/entries/2026-11-13-dqi-bm.md) |
| The reciprocal scan reaches ratio 11 to 12 | refuted: about 10, and only with an in-place Euclid history that was not found | [psi](../log/entries/2026-11-13-dqi-psi.md) |
| The 892-qubit public circuit is 840 plus 52 qubits, working in place | holds | [stage 2](../log/entries/2026-11-13-dqi-stage2.md) |
| A GF(2^24) pivot (or Cayley map) removes the failures | holds classically; the quantum build was verified later | [stage 2](../log/entries/2026-11-13-dqi-stage2.md) |
| Our `thiele` generator reaches ratio 36.4 at full size | holds | [syed](../log/entries/2026-11-13-dqi-syed.md) |
| Our own `fixed` circuit scores 65.77x (890 qubits, 10 salts, 0 failures) | holds | [environment and promotion](../log/entries/2026-11-14-environment-restore-and-promotion.md) |
| The newer extractor in our front half cuts 5,148 T and scores 66.50x (890 qubits, 10 salts, 0 failures) | holds | [extractor v3](../log/entries/2026-11-16-dqi-extractor-v3.md) |
| The gap to the best public circuit sits in convert and unconvert | refuted: 62% is the extractor return path | [stage ledgers](../log/entries/2026-11-15-dqi-stage-ledgers.md) |
| The extractor return gap is a constant +114 T at each of 31 nodes | holds (measured on both builds) | [stage ledgers](../log/entries/2026-11-15-dqi-stage-ledgers.md) |

## dfthcsos

| Claim | Status | Evidence |
|---|---|---|
| Our cost model reproduces the verifier score exactly (baseline and public refit) | holds | [cost model](../log/entries/2026-11-12-dfthcsos-cost-model.md) |
| Our unary J=13 loader on the public words verifies at ratio 6.85 | holds | [loader](../log/entries/2026-11-12-dfthcsos-loader.md) |
| The public table is fitted to a low-rank loader family | refuted | [loader](../log/entries/2026-11-12-dfthcsos-loader.md) |
| A rank budget can be imposed on already-rounded words | refuted | [co-design](../log/entries/2026-11-12-dfthcsos-codesign.md) |
| 7-bit words pass the gates | refuted (ours failed `error_2` by 8.8x) | [low bits](../log/entries/2026-11-12-dfthcsos-low-brot.md) |
| A passing 7-bit table would save only about 3% on the public shape | model only | [low bits](../log/entries/2026-11-12-dfthcsos-low-brot.md) |
| A fully own table passes the verifier (E019 at 1.81, E020 at 1.98) | holds | [structured](../log/entries/2026-11-12-dfthcsos-structured.md) |
| 8 bits is reachable by a gentler QAT schedule | refuted | [eight-bit](../log/entries/2026-11-13-dfthcsos-eight-bit.md) |
| Our own ANF loader plus 11-bit half-circle QAT verifies at ratio 2.50 (E040) | holds | [stage 2](../log/entries/2026-11-13-dfthcsos-stage2.md) |
| The public table is an arbitrary 8-bit table loaded by a good GF(2) decomposition | unverified | [stage 2](../log/entries/2026-11-13-dfthcsos-stage2.md) |
| The eighth plane is a helper that is almost always 0 | refuted: a fixed low monomial in all 15 batches, density 25% | [syed decode](../log/entries/2026-11-15-dfthcsos-syed-decode.md) |
| syed3000's table is output only, and our J=4 loader would give about 9.06x on it | model only | [syed decode](../log/entries/2026-11-15-dfthcsos-syed-decode.md) |
| The `Lambda` gap (283 against 490 to 560) is the basin, not the objective | unverified | [syed decode](../log/entries/2026-11-15-dfthcsos-syed-decode.md) |

## Public frontier, verified by us

| Claim | Status | Evidence |
|---|---|---|
| The public portfolio verifies at invsqrt 25.91x, dqi 67.44x, dfthcsos 11.31x (5 salts each, 0 failures) | holds | [portfolio verified](../log/entries/2026-11-14-syed-portfolio-verified.md) |
