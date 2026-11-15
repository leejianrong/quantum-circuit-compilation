---
id: 2026-11-12-dqi-small-instances
date: 2026-11-12
title: "Smaller DQI fields run through the official verifier in seconds, once the shot floor of about 1,400 is respected"
type: decision
benchmark: dqi
methods: [small-instances, generator]
status: done
outcome: positive
prs: [41]
studies: [docs/experiments/dqi-small-instances.md]
backfilled: true
licence_touched: false
---

## Question

Can a DQI design change be checked in seconds with the official verifier, instead of waiting for a Kaggle run?

## Setup

This entry was backfilled from the study note and git history on 2026-11-15. `src/dqi_gen/instances.py` builds
a decoder for a smaller code and calls the official verifier, which already accepts any
`ProblemSpecDQI(m, n, degree, r, num_shots)`; nothing was re-implemented. `r` defaults to the bent-function size
for the field, the DQI weight distribution is recomputed for each instance, and register names are unchanged.
Reference decoder, 3,072 shots, one core, wall time including the build. Commit and machine: not recorded.

## Results

### Quantitative

| Instance (m, n, b) | Field | Qubits | Toffolis per shot | Q2T | Wall |
|---|---|---:|---:|---:|---:|
| tiny 15, 4, 4 | GF(16) | 115 | 22,090 | 2.92e8 | 0.9 s |
| small 63, 10, 6 | GF(64) | 229 | 93,542 | 4.91e9 | 1.4 s |
| medium 255, 20, 8 | GF(256) | 462 | 326,559 | 6.97e10 | 3.3 s |
| large 1023, 40, 10 | GF(1024) | 972 | 1,558,907 | 1.47e12 | 37 s |
| full 4095, 70, 12 | benchmark | n/a | n/a | n/a | Kaggle only |

All figures [M]. `large` is the largest that stays comfortable on the laptop.

### Qualitative

* Shot floor trap: with zero failures the Clopper-Pearson bound is `1 - 2^(-128/N)`, below 1/16 only from about
  1,376 shots. Fewer shots raise "Effective error rate >= 1/16" even for a perfect circuit. `min_shots()`
  returns 1,536 (a multiple of the 256 batch size); the default is 3,072.
* Trap two: `R * Q^2 * T` is meaningless at low shot counts because `R` depends on `eps_plus`. The tool also reports
  `q2t = Q^2 * T`, which compares designs directly.
* Tests in `tests/unit/test_dqi_instances.py` (marked `integration`) check that the reference passes tiny and
  small, that a decoder doing nothing is rejected, and that the shot floor is enforced.

## Decision

Use these instances as the inner loop for every later DQI decoder; the same tool verifies our own generators
(`--gen divstep` first). Failure rates cannot be judged on tiny fields, a point the later BM entry repeats.

## Reproduce

```
QCC_DATA=data uv run python -m dqi_gen.instances --gen reference --instance small
```

## Links

PR 41; `docs/experiments/dqi-small-instances.md`.
