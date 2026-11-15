---
id: 2026-11-12-dfthcsos-loader
date: 2026-11-12
title: "Our own unary angle loader verifies at ratio 6.85 on the public words, 1.64x behind the public loaders"
type: experiment
benchmark: dfthcsos
methods: [loader, generator, cost-model]
status: done
outcome: positive
prs: [37]
experiments: [E001]
rows: [997264ad]
studies: [docs/experiments/dfthcsos-loader.md]
backfilled: true
licence_touched: true
---

## Question

Can we generate the `ANGLE_k` circuit family ourselves (ADR-0009 stage 1, paper first) and how close does it get to the public loaders on the public refit words?

## Setup

This entry was backfilled from the study note and git history on 2026-11-15. `src/dfthcsos_gen/` builds unary iteration (Babbush et al., arXiv:1805.03662) with two prunings: a subtree
whose rows agree loads once at its root, and an all-zero subtree costs nothing. Words: the public refit (8, 143, 44), 8 bits. Verified with `bench verify dfthcsos --salts 3`
(E001). Public circuit gate statistics are aggregate counts logged in `docs/PROVENANCE.md`. Commit, machine: not recorded.

## Results

### Quantitative

| Loader | Circuits | Angle Toffolis (both passes) | Qubits | Cost | Ratio |
|---|---:|---:|---:|---:|---:|
| host reference QROM, J = 5 | 15 | 36,540 | 61 | 865,005,498 | 3.88 |
| ours, unary, J = 13 | 6 | 14,616 | 125 | 489,890,973 | 6.85 |
| public loaders, J = 5 | 15 | 8,302 | 128 | 299,614,422 | 11.20 |

E001: PASS 3/3 salts [M]. The cost model predicted 489,890,973.1788 from statistics alone and the verifier returned the same [M]. At J = 13, `Q_total` rises 427 to 491 [M].

### Qualitative

* A unary loader costs `A - 2` Toffolis per circuit whatever the word width (words are CNOT fan-out), so the only lever is the number of circuits `K = ceil(75 / J)`; the 128-qubit cap gives
  `J = 13` at 8 bits. "Wider circuits, not cheaper circuits": angle Toffolis fall 2.5x against the reference, net 1.77x better.
* Counting argument [I]: a generic 35-bit-wide table needs roughly one Toffoli per address (about 180 at minimum, over 400 for a sum of products), yet the public circuits cost 270 to 296 each.
* Checks on the public table [M]: the 40 delta bit columns have GF(2) rank 35, every 7x4 or 5x6 address split is full rank, and the table is not in a Reed-Muller code of degree up to 6.
* Gate statistics of one public circuit (291 CCX, 41,645 CX, 75 measured ANDs) were read as 75 product ancillas plus about 200 CCX of about 5 per output bit, a rank-5 quadratic form per bit.
  The note concluded that the table "was fitted to the loader, not the other way round" [I]. This reading was later reversed in 2026-11-13-dfthcsos-stage2.
* The cost-model ratio with the public loader's Toffoli count (8,302) would be 11.2, so a co-design of table and loader is the next lever.

## Decision

Next lever: co-design angles and weights with a per-bit rank budget against the `error_2` gate. Not tried yet because the public refit already sits on the 0.0200 gate. This became `dfthcsos-codesign`.

## Reproduce

```bash
# build the loaders for the public words (data stays local), then verify
uv run python - <<'EOF'
import numpy as np
from dfthcsos_gen import build_family, write_family
w = np.load("best/dfthcsos/submission.npz")["angle_words"]
write_family(build_family(w, 8), "/tmp/run_j13")
EOF
cp best/dfthcsos/submission.npz /tmp/run_j13/
flock /tmp/qcc-heavy.lock env QCC_DATA=$PWD/data uv run bench verify dfthcsos /tmp/run_j13 --salts 3
```

## Links

PR 37; E001; `docs/experiments/dfthcsos-loader.md`; `docs/PROVENANCE.md`; ADR-0009.

> Corrected in part by [2026-11-13-dfthcsos-stage2](2026-11-13-dfthcsos-stage2.md): the public table is probably not rounded into a low-rank loader family.
