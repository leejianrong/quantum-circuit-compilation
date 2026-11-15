---
id: 2026-11-15-dqi-stage-ledgers
date: 2026-11-15
title: "DQI: the 7,323 T gap to the best public builder is 62% extractor return path (+114 T per node)"
type: experiment
benchmark: dqi
methods: [stage-ledger, source-decode, reproduction]
status: done
outcome: positive
commit: 5e17635
prs: [186, 187, 188, 189]
rows: [37d8047d, 7cbe8ecf]
studies: [docs/experiments/dqi-syed-decode.md]
corrects: [2026-11-14-dqi-gap-survey]
backfilled: false
licence_touched: true
---

## Question

Our own DQI circuit (391,326 Toffolis) is 2.1% behind the best public one. Where do the extra
Toffolis sit, and is it one trick or many?

## Setup

Read the Apache-2.0 builder source as data; rebuilt its `dqi.kmb` byte for byte inside a rootless container
(no network, inputs read-only; the competition `kickmix.so` needs a newer glibc than the host), and tagged
its build with our own stage driver without editing its tree. Added native stage marks to our `fixed.py`
(`--stage-log`), checked that without them the narrow circuit is byte-identical to `main`'s.
Narrow instance for the per-stage counts; the full scan is 4,095 x 11 = 45,045 T.

## Results

### Quantitative

| Quantity | Ours | His | Difference |
|---|---:|---:|---:|
| Qubits | 890 | 889 | +1 |
| Static Toffolis | 391,326 | 384,003 | +7,323 |
| Extractor return | 83,158 | 78,611 | +4,547 (62% of the gap) |
| Synthesis forward | 27,965 | 27,965 | 0 |

The return-path gap is a constant +114 T at each of 31 nodes (3,534 T), plus 1,029 T in the first three
return charts and 475 T of forward tail-controller cost. Figures: `docs/img/analysis/dqi-*.png`, numbers
in `analysis/numbers/dqi.json` (`make report`).

### Qualitative

* Not one trick: 6,411 T sit between our vendored base and the base of his final pipeline, and 912 T in 15
  small patches.
* CORRECTION of `2026-11-14-dqi-gap-survey`, which put the 7.3k T gap in convert plus unconvert (its tag-based comparison).
  With native marks on both builds convert is only +897 T; the extractor is +5,225 T, synthesis +442 and the scan +759.
* The estimate that put the gap in synthesis was wrong; its stage boundaries were estimated from an
  instruction profile. Native marks replaced it.
* Three configuration choices we worried about (`fused`, `j_min`, the adaptive gauge) are not the lever.

## Decision

First module to attack: the extractor return path. Next experiment: plug his first-three adapter and
deferred tail into our `fixed.py` front half and see whether the interface to our synthesis holds. Keep
the old stage as the oracle; require the per-stage count to fall and the official verify to pass at 10
salts. That experiment is separate from this entry.

## Reproduce

```
uv run python -m dqi_gen.instances --gen fixed --instance narrow --salts 0 --save X.kmb --stage-log marks.json
uv run python -m dqi_gen.study X.kmb --out study.json
make report
bash scripts/dqi_reference_build.sh
```

## Links

PRs 186, 187, 188, 189; `docs/experiments/dqi-syed-decode.md`; ledger rows `37d8047d`, `7cbe8ecf`.
