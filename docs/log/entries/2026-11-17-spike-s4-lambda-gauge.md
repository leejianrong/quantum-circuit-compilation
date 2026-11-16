---
id: 2026-11-17-spike-s4-lambda-gauge
date: 2026-11-17
title: "S4 stage 1: joint rotation lowers our dfthcsos lambda_eff 7.7% for free; the one-body part is not the gap, the weights are"
type: experiment
benchmark: dfthcsos
methods: [lambda, gauge, rotation]
status: done
outcome: inconclusive
commit: 46db5b8
prs: []
experiments: []
rows: [30285faf]
studies: [docs/experiments/spike-s4-lambda.md]
backfilled: false
licence_touched: true
---

## Question

Is our `Lambda` of 490 to 560 (public 283) a gauge or a basin? Kill criterion: above 400 after three restarts at
matched `error_2`.

## Setup

Verifier source (`evaluate_words`) read for the definition of `Lambda`; public v13 table decoded with the verifier's
own functions; our fit-c (8,176,56) through `scripts/dfthcsos_post.py` at 16 bits. No GPU used. Public data is
syed3000 v13 (Apache-2.0), read as a reference, nothing copied.

## Results

### Quantitative

`Lambda` (one-body + weight part): public 283.3 (13.5 + 269.8), `lambda_eff` 46.93 [M]; fit-c baseline 488.6
(13.0 + 475.6), 63.05 [M]; fit-c with 4 rotation restarts and 3 joint (w, W) rotations 416.8 (13.0 + 403.8), 58.21 [M]
at the same `error_2` (0.01474) and the same Toffolis.

### Qualitative

The one-body part is already as small as the public one; the gap is the weight part, which depends on a free
orthogonal gauge on the copy index (applied to `w` and `W`) and on the weight one-norms. The gauge is worth
7.7% of `lambda_eff`, about 30% of the distance to the public value. The rest is a sparser basin (our column one-norm
is about 1.4x the public). Kill criterion not met (416.8 is above 400 but the penalised fit is untested), so the
verdict is open. A plumbing bug (a parsed flag not passed on) was found by comparing with an independent scratch
run.

## Decision

Keep `--joint-rotate` and `--rotate-restarts`. Next, stage 2: the `Lambda`-penalised fit on the GPU queue
(card QCC-55 is the same work) once the GPU is free (the other session holds it until about 04:00).

## Reproduce

`python scripts/dfthcsos_post.py <fit dir> <out> --tsym ~/qcc-fits/own/tsym/tsym.npy --brot 16 --no-write --refit-iters 0 --rotate-restarts 4 --joint-rotate 3`

## Links

QCC-62, `docs/experiments/spike-s4-lambda.md`, `src/dfthcsos_gen/post.py` (`rotate_joint`).
