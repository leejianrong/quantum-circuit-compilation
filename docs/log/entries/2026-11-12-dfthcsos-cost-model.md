---
id: 2026-11-12-dfthcsos-cost-model
date: 2026-11-12
title: "A cost model reproduces the verifier's dfthcsos score to nine digits and shows the loaders, not the factorization shape, carry the 11.2x gain"
type: experiment
benchmark: dfthcsos
methods: [cost-model, loader, low-bit]
status: done
outcome: positive
prs: [28]
studies: [docs/experiments/dfthcsos-cost-model.md]
backfilled: true
licence_touched: true
---

## Question

Can we score a dfthcsos circuit family without running the official verifier, and where does `score = lambda_eff * T_total * Q_total`
actually come from, so that we know which lever (loader, shape, bit width) to pull first?

## Setup

This entry was backfilled from the study note and git history on 2026-11-15. The model lives in `src/dfthcsos_model/` with tests in
`tests/unit/test_dfthcsos_model.py`. Inputs are the factorization shape (R, B, C), the loader's static Toffoli and qubit counts,
words per circuit `J`, bits per word `brot`, and the accuracy metrics `Lambda` and `E_gap` (taken from the verifier's `evaluate_words`).
State-preparation terms are re-derived from the formulas the verifier documents. Two reference points: the host baseline (65, 60, 60) at 12 bits,
and the public refit (8, 143, 44) at 8 bits (`best/dfthcsos`, one `bench verify ... --salts 1` run). Commit, machine: not recorded.
No experiment id was opened for this study.

## Results

### Quantitative

| Quantity | Baseline (65,60,60), 12 bit, J 8 | Public refit (8,143,44), 8 bit, J 5 |
|---|---:|---:|
| verifier score | 3,355,599,588.3155 | 299,614,422.4359 |
| model score | 3,355,599,588.3155 | 299,614,422.4359 |
| `T_total`, `Q_total` | 93,237, 730 | 14,964, 427 |
| `lambda_eff` | 49.301 | 46.891 |
| angle loader Toffolis (fwd + rev) | 79,480 (85%) | 8,302 (55%) |
| inner state prep Toffolis | 9,461 | 4,095 |

Both match to 1e-9 relative [M]. The 11.2x gap between them splits as 1.05 (`lambda_eff`) x 6.23 (T) x 1.71 (Q) [M].
Plain QROM of the same words costs 36,540 angle Toffolis against 8,302 for the public loaders [M].

### Qualitative

* The refit sits on every gate at once (`E_gap` = floor, `error_1` = `error_2` = 0.02 to eight digits) while `Lambda` 282.8 is far above its floor 49:
  `Lambda` is not binding, the error gates are.
* Most of the gain over the baseline is the loader synthesis plus the smaller address count `A`, not the factorization shape alone.
* `Q_total` is dominated by the inner QROAM temporaries (303 of 427); the angle circuits' own scratch (77) is not binding, so loader qubits are free up to the 128 cap.
* The `brot` cliff: the verifier lowers the QROAM block exponent `k` until temporaries fall strictly below `brot * (N-1)`. For the baseline shape, brot 7 or lower
  trades +7,528 Toffolis for -271 qubits, 1.33x at fixed accuracy. The "2x" quoted in public notes was not reproduced for this shape [M].
* The refit already used a cliff: `600 < 75 * 8` is false (equality), so brot 8 takes `k = 4`; brot 9 would score 0.61x. Below 8 there is no further cliff for this shape, so brot 7 or 6 only
  trims Givens and word qubits (about 3.3% and 6.7%) [M, model].
* Consequence: the 7-bit lead only pays for shapes where the cliff lands at 7; the model finds those in a second.

## Decision

Use the model to screen every loader family and shape before spending verifier time. Any new loader needs its Toffoli and qubit counts from kickmix statistics,
and any new words need `Lambda` and `E_gap`. The following studies (`dfthcsos-loader`, `dfthcsos-low-brot`) are built on it.

## Reproduce

```bash
uv run pytest tests/unit/test_dfthcsos_model.py
```

## Links

PR 28; `docs/experiments/dfthcsos-cost-model.md`; later entries 2026-11-12-dfthcsos-loader and 2026-11-12-dfthcsos-low-brot.
