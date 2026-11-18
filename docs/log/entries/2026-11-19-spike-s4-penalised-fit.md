---
id: 2026-11-19-spike-s4-penalised-fit
date: 2026-11-19
title: "S4 stage 2: a Lambda-penalised fit reaches the public Lambda (283.6 against 283.3); the Lambda gap was a basin"
type: experiment
benchmark: dfthcsos
methods: [lambda, penalised-fit, gpu]
status: done
outcome: positive
commit: 34a53dd
prs: []
experiments: []
rows: [30285faf]
studies: [docs/experiments/spike-s4-lambda.md]
backfilled: false
licence_touched: false
---

## Question

Is the gap between our `Lambda` (490 to 560) and the public 283 a basin that a penalty on the weight one-norm from the first
iteration reaches? Kill criterion: `Lambda` above 400 after three restarts at matched `error_2`.

## Setup

`scripts/run_fit_gpu.py --mu` (new penalty `1/4 sum_(rho c) (sum_b |w_bc|)^2`), six values of `mu` from 1e-7 to 3e-5, 40 minutes
each on the local GPU through pueue, from fit-c (8,176,56). Post-processing at 16 bits with 4 rotation restarts and 3 joint
rotation rounds. One `mu` run was cut at iteration 8,800 of about 9,500 by a session teardown.

## Results

### Quantitative

`lambda_eff` against fit-c's 63.05: 53.63 (`mu` 1e-7), 52.25, 50.60, 49.22, 48.24, 48.06 (`mu` 3e-5, `Lambda` 283.6,
`error_2` 0.0148) [M]. The public table is 283.3 and 46.93. Gauge-only work (stage 1) had given 58.21.

### Qualitative

The penalty reaches the public `Lambda` at `error_2` inside the gate, and at small `mu` it also lowers `error_2`. The residual
2.4% in `lambda_eff` is `E_gap` (4.10 against the 3.915 floor). A `Lambda` that the unpenalised fit could not reach by 6
to 20 hours of dense fitting plus gauge work came from a penalty from iteration zero.

## Decision

Kill criterion not met; hypothesis confirmed. Next: stage 3, 8 and 10-bit quantisation-aware rounding of the penalised fit
(the other half of the gap by S2), then a loader on the new words.

## Reproduce

`python scripts/run_fit_gpu.py --tsym tsym.npy --shape 8 176 56 --init-from <fit-c> --out <dir> --mu 3e-5 --max-secs 2400`
with a CUDA torch (2.9.1+cu128 works here), then `dfthcsos_post.py --brot 16 --rotate-restarts 4 --joint-rotate 3`.

## Links

QCC-62, QCC-55, `docs/experiments/spike-s4-lambda.md`.
