---
id: 2026-11-16-dqi-backhalf-outer
date: 2026-11-16
title: "DQI: back half of the newer lineage in our front half (fixed4): -1,314 T and the 890th qubit"
type: experiment
benchmark: dqi
methods: [stage-ledger, source-decode]
status: done
outcome: positive
commit: c61a316
prs: []
rows: [599cb515]
studies: [docs/experiments/dqi-syed-decode.md]
corrects: []
backfilled: false
licence_touched: true
---

## Question

Does wiring syed3000's deferred tail, padded seed, gauge-park outer, infinity-3 finish and zero-mask scan into
our front half (fixed3s) close the remaining static gap and the one-qubit gap?

## Setup

`src/dqi_gen/backhalf.py` follows the order of `v6_pipeline.emit` (read as reference) and assigns module
attributes as his `configure()` does; geometry and instance handling stay ours. Generator `fixed4`. No
syndrome-weight gauge (as before). Narrow instance, `dqi_gen.stages` for per-stage counts.

## Results

### Quantitative

| Narrow | fixed3s | fixed4 |
|---|---:|---:|
| Static Toffolis | 341,812 | 340,498 (-1,314) |
| Qubits | 890 | 889 |
| Official verify, 2 salts | pass | pass, 0 value and 0 phase errors |

By group: outer forward -211, finish + outer return -713, synthesis return -221, finish forward +27.

### Qualitative

The outer needs the finish's live inverse, so finish and outer go in together. The qubit comes from the outer
borrowing the tail's gauge flag and `carry[12:]`. What is left of the 2,073 T gap is the adaptive-gauge scan (759 T).

### Official, full size

Kaggle kernel `qcc-dqi-gen`, 10 salts, 0 failures, worst cost 3.63139e11 (ratio 67.30, was 66.75), 889 qubits,
384,762 static T (narrow total - 781 + 45,045), sha256 `599cb51579cd`. Promoted into `best/dqi` on 2026-11-16
(`ledger/promotions.jsonl`; replaced `f983871e`). The cost fell 3.0e9 although the static count fell only 1,314 T,
so the return-side saving is worth more in the mean cost, as with the earlier steps.

## Decision

Promoted. Remaining distance to his 384,003 T is the adaptive-gauge scan (759 T); next step is porting it
(`adaptive_gauge64`, vendored) on top of `fixed4`.

## Reproduce

```
uv run python -m dqi_gen.instances --gen fixed4 --instance narrow --salts 2 --save X.kmb --stage-log marks.json
uv run python -m dqi_gen.study X.kmb --out study.json && uv run python -m dqi_gen.stages study.json
```

## Links

`docs/PROVENANCE.md` (stage 3 row), `src/dqi_gen/backhalf.py`.
