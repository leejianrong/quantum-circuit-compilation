---
id: 2026-11-25-circuit-explorer-spike
date: 2026-11-25
title: "Circuit Explorer spike: all three best/ circuits load in under a second, the circuits carry no module tags, and indah cannot embed a page"
type: experiment
benchmark: infra
methods: [circuit-viewer, indexing]
status: done
outcome: positive
commit: 8981278
prs: []
experiments: []
rows: [bb676b95, 141f02ac, 24516e97]
studies: []
backfilled: false
licence_touched: true
---

## Question

Before building the Circuit Explorer (QCC-71): can each circuit in `best/` be loaded and scanned quickly enough to index on demand, do the circuits carry any module structure, and can the dashboard library (indah) embed a standalone page?

## Setup

Measured with the pip kickmix wheel on this machine (31 GB RAM), DQI under a 14 GB address-space cap. Instruction counts come from `Circuit.operation_statistics()`, operation mixes from the text export, and the indah check from its component list, its `Frame` and `Plot` docs and its protocol notes.

## Results

### Quantitative

- invsqrt `bb676b95`: loads in under 0.1 s (0.03 GB), 60,766 instructions, 1,553 Toffoli-like, 37 qubits, 78,869 classical bits. The text export is 60,789 lines: 29,974 CX, 11,881 CZ, 5,166 Z, 3,119 SWAP, 1,470 CCX, 1,278 HMR [M].
- dfthcsos `angle_k_0`: loads in under 0.1 s, 51,907 instructions, 245 CCX, with named registers (`selection`, `word_0`, `word_1`, ...). The package holds 15 such files plus `submission.npz` [M].
- DQI `dqi.kmb` (618 MB): loads in 0.7 s using 0.62 GB. 69,782,187 instructions, 318,971 Toffoli-like, 900 qubits, 691,866 bits. The text export takes 5.3 s and is 1.3 GB. An `awk` count over it takes 7 s, and a pure Python line loop runs at about 3.8 M lines/s (about 19 s for the whole file before any per-gate work) [M].
- None of the circuits contains an `INFO_TAG` line (0 in all three), so no module structure is annotated.
- `kickmix.Circuit` has no slicing and no iteration. The only route to individual instructions is the text export.

### Qualitative

- The size premise in the plan was too pessimistic for invsqrt and dfthcsos: their full gate lists are 50 to 60 thousand lines, small enough to page directly. Only DQI (70 M instructions, 99.5% Clifford) needs summarising. For DQI the gate pages should hold the 312 k CCX and 40 k R only, with Clifford counts per bucket.
- Modules are inferred, not read. This confirms the plan. kickmix does have its own `flame_chart_svg`, which draws subroutines from `@enter:subroutine` and `@exit:subroutine` INFO_TAG pairs, and `html_diagram` and `text_diagram`. An inferred segmentation can write those tags into a copy so kickmix draws the chart.
- indah cannot embed the page: its render spec is data only and forbids script, iframe and object. The Circuits tab therefore shows the picker and the module summary natively and links to the standalone page. `create_app` returns a Starlette app, so the generated pages can be served from the same server under a mounted route (to be confirmed in P3).

## Decision

Phase 0 is done and the plan stands with three changes: (1) gate pages for invsqrt and dfthcsos hold every instruction, DQI's hold non-Clifford ones; (2) the dashboard tab links to the standalone page instead of embedding it; (3) kickmix's own flame chart becomes an optional panel fed by inferred module tags. Next is P1, `bench index` for invsqrt.

## Reproduce

`uv run python -c "import kickmix as km; c=km.Circuit.from_file('best/invsqrt/invsqrt.kmb'); print(c.operation_statistics())"`; for DQI `Circuit.from_file('best/dqi/dqi.kmb').to_file(<out>)` then `awk '{c[$1]++} END{for(k in c) print c[k],k}' <out>`.

## Links

QCC-71, [submission 33.17](2026-11-25-submission-33-17.md).
