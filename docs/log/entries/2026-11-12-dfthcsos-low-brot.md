---
id: 2026-11-12-dfthcsos-low-brot
date: 2026-11-12
title: "Seven-bit angle words fail error_2 by 8.8x, and even a passing 7-bit table would save only about 3%"
type: experiment
benchmark: dfthcsos
methods: [low-bit, qat, fit, cost-model]
status: done
outcome: negative
prs: [33]
studies: [docs/experiments/dfthcsos-low-brot.md]
backfilled: true
licence_touched: true
---

## Question

Can mixed angle widths, or rounding that targets the verifier's gates, get `brot <= 7` through the accuracy gates, and would it pay?

## Setup

This entry was backfilled from the study note and git history on 2026-11-15. Everything starts from the public refit (`best/dfthcsos`, shape (8, 143, 44), 8-bit words, cost 299,614,422.44).
Metrics come from the verifier's own `evaluate_words` (about 3 s per call). Circuits for the one real check come from the host's reference QROM generator (J = 5, 15 circuits); no third-party circuit
files are committed. Script `scripts/dfthcsos_low_brot.py`. Machine, commit: not recorded. No experiment id was opened.

## Results

### Quantitative

| Variant | `error_2` | Other |
|---|---:|---|
| public refit, 8 bit | 0.0200 | `E_gap` 3.91490, `lambda_eff` 46.891 |
| lowest bit rounded to even, 7,570 words (amp < 0.01) | 0.0206 | `lambda_eff` 46.897 |
| same, 23,633 words (amp < 0.05) | 0.0348 | `lambda_eff` 47.298 |
| nearest rounding to 7 bits | 0.425 | `error_1` 0.137 |
| nearest rounding to 6 bits | 0.728 | `error_1` 0.361 |
| continuous angles and weights (floor, unconverged) | 0.0192 | |
| progressive rounding, 50% fixed | 0.0193 | |
| progressive rounding, 70% fixed after re-fit | 0.163 | |
| progressive rounding, 100% fixed, weights re-fit | 0.175 | |

Real candidate, `bench verify dfthcsos <dir> --salts 3`: FAIL 3/3, `error_1` 30.2884 mHa, `error_2` 175.2625 mHa (both gates 20 mHa); `Lambda` 300.9, `E_gap` 6.229, so `lambda_eff` 60.9 [M].
Positive control: public words through the reference QROM PASS 3/3 at 865,005,498.40, model 865,005,498.4012733 [M].
Model, loaders unchanged: brot 7 scales cost x 0.968, brot 6 x 0.937; 7 bits pays only if B stays under about 147 [M, model].

### Qualitative

* The public refit has no slack: it sits on three gates at once, and even the smallest mixed-width step breaks `error_2`. Mixed widths cannot be tried without refitting the factorization.
* The one-body rows enter only `error_1`, but `error_1` is rebuilt from the decoded two-body vectors, so any two-body change blows it up (random 1 ulp changes on 1% of words: 0.02 to 0.23) unless the one-body rows are re-derived each time.
* Rounding noise also raises `E_gap`, so a noisier table loses `lambda_eff` as well as risking the gate.
* The cliff is at the odd words: half of the 8-bit words are even and sit on the 7-bit grid for free; forcing the odd ones off their optimum cannot be compensated by re-fitting the others.
* The shape has only 0.0056 of rounding budget in quadrature (sqrt(0.0200^2 - 0.0192^2)); a 7-bit design needs noise about 30x lower than the 0.175 we reached.
* Scaling `W` to bring `E_gap` down does not work: the gap is not monotone in the scale.
* The "2x" for 7 bits belongs to shapes like the baseline (65, 60, 60), where the QROAM block exponent drops; the refit already took that step at 8 bits.
* Largest untouched lever noted: the loader synthesis (55% of Toffolis); the reference QROM costs 4.4x more than the public loaders.

## Decision

QCC-38 and QCC-15 stay open, no more optimiser effort on 7 bits for this shape. Next: write a loader generator for the monomial-product structure the public circuits use (this led to `dfthcsos-loader` and `dfthcsos-codesign`).

## Reproduce

```bash
QCC_DATA=$PWD/data uv run python scripts/dfthcsos_low_brot.py check best/dfthcsos 7
QCC_DATA=$PWD/data uv run python scripts/dfthcsos_low_brot.py round best/dfthcsos 7 /tmp/out7
QCC_DATA=$PWD/data uv run python scripts/dfthcsos_low_brot.py finish best/dfthcsos 7 /tmp/out7
```

`round` takes about 20 minutes on a free machine.

## Links

PR 33; `docs/experiments/dfthcsos-low-brot.md`; `docs/experiments/dfthcsos-cost-model.md`.
