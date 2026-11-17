# S1: calibrated expected-cost model (QCC-59)

Hypothesis: the official cost follows from the static gate count, so a fitted model can screen circuits without a
verifier run. Kill criterion: held-out relative error above 1%.

## Static model (invsqrt) [M]

Twelve distinct invsqrt circuits with a full official run in `ledger/results.jsonl` (qubits 44 to 94, static `toffolis`
from `operation_statistics().num_toffoli_like`). Cost per qubit `C = cost / Q` against static `T`:

* Best fit `C = 1.000 T + 239.5`: the slope is 1, the offset is the rotation and T charge (about 34 rotations at 7.35 each, see S2).
* Residual 3.7% mean, 7.0% max in sample; **leave-one-out 4.2% mean, 8.1% max**. Kill criterion met.
* The ratio `C / T` ranges from 1.069 to 1.208 because the fixed rotation charge is a bigger share of small circuits, and
  because the executed Toffolis are below the static count: static 1,533 against an official mean of 1,458.25 on syed3000's
  44-qubit circuit (5%), and 1,560 against 1,459 on koushik's (6.5%).

The gap is conditional execution (blocks under `PUSH_CONDITION` run on a fraction of shots), which depends on the
circuit and on the measurement statistics. The earlier `2^-depth` estimate overshot: for the 62-qubit public circuit it
predicted 155 saved of 1,393 static, but the official cost implies about 107 (cost 94,599.6 / 62 = 1,525.8, minus 240).

## Reduced-shot screening [M]

`bench verify --shots-divisor N` reproduces the full cost on all four invsqrt circuits that have both kinds of rows:
relative error below 1e-5 (for example `fc834b80`: 195,062.69 at divisor 20, 195,062.72 full), at 150 to 290 s per run.
Toffoli means over shots have very low variance here.

## Verdict

Killed as stated: a static model cannot screen to 1%. The question it was meant to answer is already answered by the
reduced-shot run, which is exact to 1e-5 on invsqrt. Still open: DQI, where the cost also depends on the failure
factor `R` (3.4895e11 worst of 10 salts against 3.4736e11 at the default salt for the same circuit), which no shot-reduced or
static run predicts; only salts do. A DQI screen would need a failure-rate estimate per salt, not a cost model.

Lesson: screen invsqrt and dfthcsos with `--shots-divisor`, never trust a static count better than 5%, and treat DQI
cost as a distribution over salts.
