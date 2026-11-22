# State of knowledge by benchmark

One section per benchmark: how it is scored, where we stand against the best circuits we have verified, what we
learned, what failed, and what is still open. Every number is a ledger row or a log entry; the live table is the
[scoreboard](../results/scoreboard.md). Ratios are `baseline_cost / worst-salt cost` from the official verifier.
Detail and evidence sit in the [claims register](claims.md); open items in [open questions](open-questions.md).

## invsqrt

**Score** `Q * C`: qubits times Toffoli-equivalents ([costs and MBUC](../learn/costs-and-mbuc.md)). A given percentage cut in
either is worth the same.

| | Ratio | Qubits | Evidence |
|---|---:|---:|---|
| Our best (E023) | 12.34 | 93 | [uncompute](../log/entries/2026-11-13-invsqrt-uncompute.md) |
| Public 62-qubit circuit | 21.95 | 62 | [environment restore](../log/entries/2026-11-14-environment-restore-and-promotion.md) |
| Public 46-qubit circuit | 25.91 | 46 | [portfolio verified](../log/entries/2026-11-14-syed-portfolio-verified.md) |
| Public 43-qubit circuit (syed3000 v17, in `best/`) | 28.67 | 43 | [v17 promoted](../log/entries/2026-11-21-invsqrt-v17-verified-promoted.md) |
| Public 44-qubit circuit (koushik v54, earlier `best/`) | 27.77 | 44 | [v13 promoted](../log/entries/2026-11-17-public-v13-verified-promoted.md) |

**What we know.** The reference spends 88% of its cost in schoolbook multiplications
([cost drivers](../log/entries/2026-11-12-invsqrt-cost-drivers.md)). Our generator reached 93 qubits through lean qubits,
exhaustive windows and uncomputation ([generator](../log/entries/2026-11-12-invsqrt-generator.md),
[uncompute](../log/entries/2026-11-13-invsqrt-uncompute.md)). The 62-qubit public circuit uses the same mathematics
(degree 2, 256 table entries); its edge is engineering, and it does have a Horner unwind and about 10 scratch qubits
([stage 2](../log/entries/2026-11-13-invsqrt-stage2.md), [one-pass](../log/entries/2026-11-13-invsqrt-onepass.md)).

**What failed.** Serial and split phasing alone, a streaming phase adder, and a 28,19,8 table gave no gain
([bit-serial](../log/entries/2026-11-12-invsqrt-bitserial.md), [phase adder](../log/entries/2026-11-12-invsqrt-phase-adder.md),
[one-pass](../log/entries/2026-11-13-invsqrt-onepass.md)). Several early readings were corrected; see the
[corrections](../log/corrections.md).

**Open.** The consuming multiplier of the 46-qubit builder looks like a real lead and has not been re-checked by us
([syed decode](../log/entries/2026-11-15-invsqrt-syed-decode.md)). The project parks invsqrt unless there is a concrete new
idea ([HANDOFF](../HANDOFF.md)).

## dqi

**Score** `R(eps) * Q^2 * T`: qubits are squared: 1% of qubits is worth 2% of Toffolis, one qubit about 830 Toffolis ([S2](../experiments/spike-s2-exchange-rates.md)).

| | Ratio | Qubits | Static Toffolis | Evidence |
|---|---:|---:|---:|---|
| Our best (`fixed`, promoted) | 65.77 | 890 | 391,326 | [environment restore](../log/entries/2026-11-14-environment-restore-and-promotion.md) |
| Our `fixed4` (back half of the newer lineage, promoted) | 67.30 | 889 | 384,762 | [back half](../log/entries/2026-11-16-dqi-backhalf-outer.md) |
| Our `fixed3s` (nested-norm synthesis, promoted earlier) | 66.75 | 890 | 386,076 | [synthesis nested norm](../log/entries/2026-11-16-dqi-synthesis-nested-norm.md) |
| Our `fixed3` (newer extractor, promoted) | 66.50 | 890 | 386,178 | [extractor v3](../log/entries/2026-11-16-dqi-extractor-v3.md) |
| Best public circuit (syed3000 v17 `a31716fa`, in `best/`) | 72.2 | 890 | 356,981 mean (its newest profile `fc2564c6`: 356,677, 0.085% lower, not built by us) | [v17 promoted](../log/entries/2026-11-21-dqi-v17-verified-promoted.md) |
| Earlier best public circuit (v54 `00ac37d4`) | 70.04 | 890 | about 368,120 mean | [v13 promoted](../log/entries/2026-11-17-public-v13-verified-promoted.md) |
| Earlier public circuit (syed3000 v12) | 67.44 | 889 | 384,003 | [portfolio verified](../log/entries/2026-11-14-syed-portfolio-verified.md) |
| Our dialog-free BM decoder | 7.86 | 1,855 | 740,602 | [BM](../log/entries/2026-11-13-dqi-bm.md) |
| Our Thiele generator | 36.4 | 955 | 615,399 | [syed](../log/entries/2026-11-13-dqi-syed.md) |

**What we know.** The reference's two Euclid passes are 73% of its Toffolis
([cost drivers](../log/entries/2026-11-12-dqi-cost-drivers.md)). Lanczos failures were not fixable locally, and a
GF(2^24) pivot (or Cayley map) removes them classically ([failures](../log/entries/2026-11-12-dqi-failures.md),
[stage 2](../log/entries/2026-11-13-dqi-stage2.md)). The 7,323 T gap to the best public builder is not one trick: with native
stage marks on both builds, 62% of it is the extractor return path, a constant +114 T at each of 31 nodes
([stage ledgers](../log/entries/2026-11-15-dqi-stage-ledgers.md)).

**What failed.** Exact look-ahead (more expensive than first estimated), and the reciprocal scan, which needs an in-place
Euclid history nobody has found ([look-ahead](../log/entries/2026-11-13-dqi-lookahead.md),
[psi](../log/entries/2026-11-13-dqi-psi.md)). An early guess that the gap sat in convert and unconvert was refuted
([gap survey](../log/entries/2026-11-14-dqi-gap-survey.md)).

**Open.** Which of the public extractor's modules accounts for the +114 T per node; which stage holds the 890 and 889
qubit peaks. The next experiment (plugging the public first-three adapter and deferred tail into our front half) is
separate from this page.

## dfthcsos

**Score** `lambda_eff * T_total * Q_total`, with accuracy gates on `error_1`, `error_2`, `Lambda` and `E_gap`; a failed
gate rejects the circuit whatever the score ([primer](../learn/primer-dfthcsos.md)).

| | Ratio | Evidence |
|---|---:|---|
| Our best (penalised-fit 11-bit table, ANF loader) | 3.28 | [stage 2](../log/entries/2026-11-13-dfthcsos-stage2.md) |
| Earlier own best (E040) | 2.50 | [stage 2](../log/entries/2026-11-13-dfthcsos-stage2.md) |
| Public 11.31x table | 11.31 | [portfolio verified](../log/entries/2026-11-14-syed-portfolio-verified.md) |
| Public 11.38x table (koushik v54, in `best/`) | 11.38 | [v13 promoted](../log/entries/2026-11-17-public-v13-verified-promoted.md) |
| Public refit | 11.20 | [environment restore](../log/entries/2026-11-14-environment-restore-and-promotion.md) |

**What we know.** Our cost model reproduces the verifier score exactly
([cost model](../log/entries/2026-11-12-dfthcsos-cost-model.md)). A fully own table passes the gates
([structured](../log/entries/2026-11-12-dfthcsos-structured.md)). Our `Lambda` is 490 to 560 for every fit against 283 for
the public one. The public table is not a rounded low-rank loader family, and its eighth plane is a fixed low monomial,
not a mostly-zero helper ([loader](../log/entries/2026-11-12-dfthcsos-loader.md),
[syed decode](../log/entries/2026-11-15-dfthcsos-syed-decode.md)).

**What failed.** Fewer than 8 bits per word, and 8 bits through gentler QAT: only 11 bits passed the `error_2` gate in
our runs ([low bits](../log/entries/2026-11-12-dfthcsos-low-brot.md),
[eight-bit](../log/entries/2026-11-13-dfthcsos-eight-bit.md)).

**Open.** Whether the `Lambda` gap is the basin or the objective (a constrained refit on our own vectors would tell). Wider
circuits are the only lever with double-digit headroom in our model, and the model assumes cuts we do not yet have
([syed decode](../log/entries/2026-11-15-dfthcsos-syed-decode.md)).
