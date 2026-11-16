---
id: 2026-11-16-dqi-synthesis-nested-norm
date: 2026-11-16
title: "DQI: nested-norm arithmetic in the synthesis is -102 T, all on the return side; ratio 66.75 verified"
type: experiment
benchmark: dqi
methods: [stage-ledger, kaggle-verify]
status: done
outcome: positive
commit: 508db56
prs: []
rows: [f983871e, c9d53c1f]
studies: [docs/experiments/dqi-syed-decode.md]
corrects: []
backfilled: false
licence_touched: true
---

## Question

His `configure()` also sets `Synthesis.Arithmetic` to the nested-norm module. Does that do the same for our synthesis
and what does it save? Follows `2026-11-16-dqi-extractor-v3`.

## Setup

Generator `fixed3s` (`extractor="v3s"`): `fixed3` plus `extract_v3.set_synthesis_nested(True)`, which assigns the fused
synthesis module's arithmetic to `gf24_nested_norm` (restored on every other build). Narrow stage counts, narrow
verify through `tests/unit/test_dqi_fixed_decoder.py` (2,048 shots), full size on Kaggle at `508db56`, 10 salts
(build 122 s, verify 1,162 s, 4.7 GB).

## Results

### Quantitative

| Quantity | `fixed3` | `fixed3s` | Change |
|---|---:|---:|---:|
| Synthesis forward | 27,965 | 27,965 | 0 |
| Synthesis return | 37,553 | 37,451 | -102 |
| Static Toffolis (full) | 386,178 | 386,076 | -102 |
| Qubits | 890 | 890 | 0 |
| Official worst-salt cost (10 salts, 0 failures) | 3.67525e11 | 3.66149e11 | -1.38e9 (-0.37%) |
| Ratio | 66.50 | 66.75 | +0.25 |

The saving is 3 T at each of 34 inverses, in the return only. [M] Gap to his 384,003 is now 2,073 T: scan 759, finish +
outer return 713, synthesis return 221, outer forward 211, extractor 196, finish forward -27 (sums exactly).

### Qualitative

* The ratio gain (0.37%) is larger than 102 T over 386k (0.03%) suggests: the official cost is a mean over shots with
  mid-circuit measurement, so static counts understate return-side savings. [I]
* Scoping the rest (reading source only): `zero_mask_scan` imports `projective_finish_infinity3`, so the adaptive-gauge scan
  (759 T) cannot be swapped alone. It comes with his infinity-3 finish and, through `finish_outer_seam`, his outer stage.
  The back half (outer, finish, scan, gauge) is one interlocked port of about 25 new modules; the deferred tail, padded
  seed and gauge-park outer are another 11 and feed a gauge flag into that outer.

## Decision

Not promoted (the owner promoted `fixed3`; `fixed3s` is a further candidate, owner's call). Next: allocation inside
stages to place the 890th qubit, then the back-half port as a staged plan.

## Reproduce

```
uv run python -m dqi_gen.instances --gen fixed3s --instance narrow --salts 0 --save X.kmb --stage-log marks.json
uv run python -m dqi_gen.study X.kmb --out study.json && uv run python -m dqi_gen.stages study.json
uv run bench kaggle run notebooks/dqi_gen
```

## Links

Ledger row `f983871e` (sha256 `f983871ec620...`); `2026-11-16-dqi-extractor-v3`; `analysis/numbers/dqi.json` key `steps`.
