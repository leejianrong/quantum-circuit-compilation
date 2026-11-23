---
id: 2026-11-24-loader-exact-synthesis-infeasible
date: 2026-11-24
title: "Exact SAT synthesis of the 128-row invsqrt table: each output bit needs at least 4 ANDs, and the method stops scaling at k = 3"
type: experiment
benchmark: invsqrt
methods: [sat, exact-synthesis, multiplicative-complexity]
status: done
outcome: negative
commit: e5fcb93
prs: []
experiments: []
rows: []
studies: [docs/experiments/ideas-adjacent-fields.md]
backfilled: false
licence_touched: true
---

## Question

Candidate 1 of the adjacent-fields note: can an exact multiplicative-complexity solver say anything useful about the 128-row by 16-output table that the invsqrt loaders write (56 and 70 ANDs on the 46-qubit line)?

## Setup

`python-sat` (Cadical) in an isolated venv outside the repo; encoder in `scripts/sat_mc.py` (is there an XOR-AND graph with k ANDs, over the 7-bit address). Validated on `x0&x1` (k = 1) and `x0&x1 ^ x2&x3` (k = 2). Table taken from the public generator's `phasefit_z1_K7_G4_m37_virtual_quadS2_36_12c0.json` (coefficients `A`, 13 bits, and `stored_slope`, 5 bits); each output bit asked on its own, k = 0, 1, 2, ... with a 30-minute cap per bit, 8 in parallel. An affine change of the address does not change the answer, so the loader's input frame is irrelevant.

## Results

### Quantitative

Bits A0 to A7: k = 0, 1, 2 UNSAT in under half a second each, then **k = 3 UNSAT after 160 to 390 s** [M]. So each of those bits alone needs at least 4 ANDs. k = 4 had not finished when the caps expired; no bit was shown SAT. The remaining bits (A8 to A12, the slope bits) did not get past k = 2 or 3 in the time given.

### Qualitative

Solve time grows about a thousandfold per extra AND (0.4 s at k = 2, minutes at k = 3), so the method settles single functions up to about 4 or 5 ANDs and cannot approach the whole 16-output table, where the owner used 56 shared ANDs. A lower bound of 4 per bit is far below 56 and says nothing about sharing. The route is useful only on small recurring sub-blocks (a handful of inputs), not on the loaders.

## Decision

Candidate 1 is closed for the loaders (outcome negative). Exact synthesis stays available through `scripts/sat_mc.py` for small blocks; nothing worth running was found. The public v17 loader uses a heuristic bank search (`joint_loader/bank_frontier.py`, quadratic code plans) that is a better fit than SAT at this size.

## Reproduce

`uv venv ~/qcc-builds/venv-sat && uv pip install --python ~/qcc-builds/venv-sat/bin/python python-sat`, then `~/qcc-builds/venv-sat/bin/python scripts/sat_mc.py <128-bit truth table> 4`.

## Links

QCC-61, [adjacent fields, verified](2026-11-23-adjacent-fields-verified.md), [harness stage 1](2026-11-23-search-harness-stage1-dead-gates.md).
