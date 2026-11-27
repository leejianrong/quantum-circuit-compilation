---
id: 2026-11-28-dfthcsos-7bit-negative
date: 2026-11-28
title: "dfthcsos: a penalised fit at the public 7-bit shape (9, 127, 46) does not survive 7-bit or 8-bit rounding, 0.180 and 0.119 against a 0.02 gate"
type: experiment
benchmark: dfthcsos
methods: [penalised-fit, qat, 7-bit]
status: done
outcome: negative
commit: 1a4470c
prs: []
experiments: []
rows: []
studies: [docs/experiments/dfthcsos-gap-2026-11-26.md]
corrects: []
backfilled: false
licence_touched: true
---

## Question

The 2026-11-26 gap breakdown put the whole 4.07x on `T_total` times `Q_total`, almost all from brot 7 (public, shape (9, 127, 46)) against 11 (ours). Can our own penalised GPU fit at that shape be rounded to 7 bits, or to 8 bits on the half circle, and pass the `error_2 <= 0.02` gate?

## Setup

Penalised fit (`Lambda` penalty `mu = 3e-5`, the S4 stage-2 recipe) at shape (9, 127, 46), run from a copy of `scripts/run_fit_gpu.py` under pueue on the GPU, 105,180 L-BFGS iterations (10,803 s). Then `scripts/dfthcsos_qat.py` at `--brot 7` and at `--brot 8 --half`, both with the 33-stage progressive rounding on the same fit. All files live outside git in `~/qcc-fits/own/s9x127x46/` (`pen3e-5/log.jsonl`, `qat7.log`, `qat8_half.log`). No circuit was built, so there is no ledger row.

## Results

### Quantitative

| Step | `error_2` [M] | Gate |
|---|---:|---:|
| continuous penalised fit, 105,180 iterations | 0.0212 (still falling, about 1e-5 per 200 iterations at the end) | 0.02 |
| QAT, 7 bits, all rounded | 0.180 | 0.02 |
| QAT, 8 bits half circle, all rounded | 0.119 | 0.02 |

The continuous fit does not reach 0.02 in 105k iterations at this shape, so even the unrounded table is outside the gate. Rounding costs about 9x (7 bits) and 5.6x (8 bits) in `error_2`. Both QAT runs show the same pattern as the 8-bit runs at the 11-bit shape in `dfthcsos-stage2.md`: error is already 0.10 to 0.19 once 65% of the words are fixed, so the loss is in the grid, not in the last stage.

### Qualitative

[V] syed3000's own research notes, read as data, call plain 7-bit rounding closed and put the `lambda_eff` floor of the public table at 46.79; the public table gets there by word-move polish with exact pricing and an SQP weight refit, not by rounding a continuous fit. [I] Our fit and the public one are different basins at this shape, as at brot 11 (S4), and the gap between 0.02 and 0.12 to 0.18 is not one more QAT schedule.

## Decision

Close the 7-bit route as a negative result, agreed with the owner on 2026-11-28. dfthcsos loader work stays blocked until some table passes the 7-bit gates. Reopening needs a concrete new idea for the rounding (the word-move polish is the only known one and it starts from the public words, which we do not use).

## Reproduce

Fit: `~/qcc-gpu-venv2` with a copy of `scripts/run_fit_gpu.py` (penalised variant, `--mu 3e-5`) at shape (9, 127, 46), queued with pueue. QAT: `scripts/dfthcsos_qat.py ~/qcc-fits/own/s9x127x46/pen3e-5 <out> --tsym ~/qcc-fits/own/tsym/tsym.npy --brot 7` and `--brot 8 --half` (5 minutes each, CPU).

## Links

[Gap breakdown](../../experiments/dfthcsos-gap-2026-11-26.md), [S4 lambda](../../experiments/spike-s4-lambda.md), [low-brot note](../../experiments/dfthcsos-low-brot.md), [stage 2](../../experiments/dfthcsos-stage2.md).
