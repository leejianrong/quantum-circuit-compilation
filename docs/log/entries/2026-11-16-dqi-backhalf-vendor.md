---
id: 2026-11-16-dqi-backhalf-vendor
date: 2026-11-16
title: "DQI: vendored the 25-module back half of the newer pipeline (finish, scan, outer, deferred tail, padded seed)"
type: experiment
benchmark: dqi
methods: [source-decode]
status: done
outcome: n/a
commit: 522c6fb
prs: []
rows: []
studies: [docs/experiments/dqi-syed-decode.md]
corrects: []
backfilled: false
licence_touched: true
---

## Question

Can the back half of syed3000's newer pipeline (everything after our synthesis stage) run in our environment
as a closed set of modules, so it can be wired into `fixed.py` in later steps?

## Setup

Computed the import closure (by AST, from the modules `v7_pipeline.configure()` and `emit()` bind) of the
infinity-3 finish, the zero-mask scan with the adaptive gauge, the transpose14 outer, the deferred tail and
the padded seed, minus the 74 modules already vendored. Copied the 25 missing files byte for byte (cmp checked)
into `third_party/syed_dqi/controller_work/`, updated `NOTICE_VENDORED.md` and `docs/PROVENANCE.md`.

## Results

### Quantitative

25 modules, about 172 KB; all 13 entry modules import under our venv once `extract_v3.bind()` has run.
No circuit changed: `best/dqi` is unchanged (`f983871e`, 66.75x).

### Qualitative

The closure is small because the older accepted pipeline (finish, seam, tail) is already vendored. The new
part is the outer and its gauge-park lenders, which take the tail's gauge flag and `carry[12:]`.

## Decision

Next: wire the deferred tail, padded seed and gauge-park outer (the part expected to recover the 890th qubit),
measure per-stage deltas with `dqi_gen.stages` on the narrow instance, then verify at 10 salts on Kaggle.
Finish and scan follow as a second swap, since they are interlocked.

## Reproduce

```
uv run --no-sync python -c "from dqi_gen import extract_v3; extract_v3.bind()"   # then import the 13 entry modules
```

## Links

`docs/PROVENANCE.md` (stage 3 row), `third_party/syed_dqi/NOTICE_VENDORED.md`.
