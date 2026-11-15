---
id: 2026-11-16-dqi-extractor-v3
date: 2026-11-16
title: "DQI: the newer extractor in our front half is 5,148 T cheaper and verifies; ratio 66.50 (from 65.77), still 67.44 to beat"
type: experiment
benchmark: dqi
methods: [stage-ledger, vendoring, kaggle-verify]
status: done
outcome: positive
commit: 9fdf21f
prs: []
rows: [c9d53c1f, 37d8047d]
studies: [docs/experiments/dqi-syed-decode.md]
corrects: []
backfilled: false
licence_touched: true
---

## Question

Does the extractor of the newer lineage of the best public builder (first-three adapter, nested-norm return arithmetic)
plug into our `fixed.py` front half, and does the extractor return path, 62% of the gap, fall? Follows the decision of
`2026-11-15-dqi-stage-ledgers`.

## Setup

Vendored 16 more Apache-2.0 modules byte for byte (74 in all), wired them in `src/dqi_gen/extract_v3.py` by the same
module-attribute assignments his `configure()` makes, added generator `fixed3` (`fixed.py extractor="v3"`). Our tail, seed,
synthesis, outer, finish and scan are unchanged; `fixed` stays the oracle. Narrow instance for per-stage counts
(`dqi_gen.stages` on `dqi_gen.study`); official verifier on narrow at 3 salts; full size on Kaggle (`notebooks/dqi_gen`),
commit `9fdf21f`, 10 salts, build 116 s, verify 1,160 s, peak 4.7 GB.

## Results

### Quantitative

| Quantity | `fixed` | `fixed3` | Change |
|---|---:|---:|---:|
| Extract forward | 73,919 | 73,540 | -379 |
| Extract return | 83,158 | 78,389 | -4,769 |
| Synthesis, outer, finish, scan | unchanged | unchanged | 0 |
| Static Toffolis (full) | 391,326 | 386,178 | -5,148 |
| Qubits | 890 | 890 | 0 |
| Official worst-salt cost (10 salts, 0 failures) | 3.7156e11 | 3.6753e11 | -4.04e9 (-1.09%) |
| Ratio | 65.77 | 66.50 | +0.72 |

The -114 T per node on nodes 3 to 33 is exact; nodes 0 to 2 fall by 462, 366, 201. [M] Gap to the best public build (384,003
T): 2,175 T left (from 7,323). The extractor alone is 889 qubits under v3 (890 under v2), so our 890th is an in-stage peak
elsewhere. Narrow verify: 3 salts, 0 value and 0 phase errors.

### Qualitative

* The interface held: no need to adopt his front half. His deferred tail, padded seed, gauge-park outer and accepted-runtime
  loader were not needed for this gain.
* Answers the open question "which module gives -114 T per node": the bundle of nested-norm arithmetic plus
  `last_return_retained_norm`, which the extractors' arithmetic is rebound to. Not isolated one module at a time. [I]
* Next, from a narrow trial (not yet a result): nested-norm arithmetic in synthesis is another -102 T and passes narrow
  verify at 3 salts. Remaining extractor gap +196 T, convert +897, scan +759, synthesis +340.

## Decision

Keep `fixed3` as the generator for further DQI work. Not promoted: ratio 66.50 is below the 67.44 public circuit, and
promotion needs the owner. `bench promote dqi ... --dry-run` is the owner's call. Next experiment: synthesis nested norm,
its own branch.

## Reproduce

```
uv run python -m dqi_gen.instances --gen fixed3 --instance narrow --salts 3
uv run python -m dqi_gen.instances --gen fixed3 --instance narrow --salts 0 --save X.kmb --stage-log marks.json
uv run python -m dqi_gen.study X.kmb --out study.json && uv run python -m dqi_gen.stages study.json
uv run bench kaggle run notebooks/dqi_gen
```

## Links

Ledger row `c9d53c1f` (circuit sha256 `c9d53c1f9889...`); `docs/experiments/dqi-syed-decode.md`; `docs/PROVENANCE.md` (2026-11-16 row);
`analysis/numbers/dqi.json` key `steps`.
