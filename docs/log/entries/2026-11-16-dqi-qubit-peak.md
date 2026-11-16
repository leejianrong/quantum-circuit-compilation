---
id: 2026-11-16-dqi-qubit-peak
date: 2026-11-16
title: "DQI: the 890th qubit is reached in the outer stages, not the extractor; v3 already brings the extractor to 889"
type: experiment
benchmark: dqi
methods: [qubit-timeline]
status: done
outcome: positive
commit: eb74b80
prs: []
rows: []
studies: [docs/experiments/dqi-syed-decode.md]
corrects: []
backfilled: false
licence_touched: true
---

## Question

Our circuit is 890 qubits, the best public one 889 (one qubit is about 879 T). Which stage holds our peak? The stage marks
only read the allocation at stage ends (864 to 866), so the in-stage peak was unplaced.

## Setup

`scripts/dqi_peak_stages.py`: a proxy around the builder reads `num_allocated_qubits` after every allocation and keeps the
maximum per stage tag, narrow instance, generators `fixed` (`v2`) and `fixed3s` (`v3s`) at `eb74b80`.

## Results

### Quantitative

| | extractor (forward) | outer forward | finish return | outer return (synthesis return) | circuit |
|---|---:|---:|---:|---:|---:|
| `fixed` (v2) | 890 | not listed | | | 890 |
| `fixed3s` (v3s) | 889 | 890 | 890 | 890 | 890 |

Rows are the allocation peak in the stage that follows the named tag; for `fixed` only the extractor stages, which already
reach 890, were read. [M]

### Qualitative

* The newer extractor lowers the extractor's own peak from 890 to 889, matching his circuit, but the width stays 890 because the
  outer stages (forward, and the two returns that mirror it) reach 890.
* So the missing qubit is in the outer stage. [V] His outer is called with `gauge_flag` (the deferred tail's flag) and
  `gauge_other=carry[12:]`, so it borrows its working qubits from the tail and the carry. [I] That loan is the likely source
  of his 889, and it ties the qubit to the same port as the 2,073 T gap: deferred tail, padded seed, gauge-park outer.

## Decision

The qubit and the back-half Toffolis are one project: port the tail (deferred), seed (padded) and outer (gauge park) with the
finish and scan, in stages with a verify after each. Next.

## Reproduce

```
QCC_DATA=$PWD/data uv run python scripts/dqi_peak_stages.py v3s
```

## Links

`2026-11-16-dqi-synthesis-nested-norm`; `docs/experiments/dqi-syed-decode.md` section 8.
