---
id: 2026-11-22-dqi-v17-generator-reading
date: 2026-11-22
title: "v17 dqi generator read: the circuit we hold is its stack100 profile, and its newest profile is only 0.085% better"
type: reading
benchmark: dqi
methods: [source-study]
status: done
outcome: negative
commit: 058b837
prs: []
experiments: []
rows: [a31716fa]
studies: [docs/experiments/dqi-70x-study.md]
backfilled: false
licence_touched: true
---

## Question

What does the v17 `dqi_generator` contain, does it explain the 7% gap between our `fixed4` (67.30x) and the public circuit we now hold (`a31716fa`, about 72.2x), and is there a cheap gain in it? Static reading only; nothing was built or run.

## Setup

`public/syed3000__vqcc-own-circuit-portfolio-20261121/files/dqi_generator/dqi_generator/` (Apache-2.0 with NOTICE, untrusted data): README, `build.py`, `manifest.json`, the four `verification/*.json` receipts, file counts.

## Results

### Quantitative

The package is 647 files, 57 MB: nine new modules (586 lines) around `vendor/d70-source` (630 files, 430 of them Python; the D70 decoder lineage of Syed Asad Ali and collaborators) [M]. `build.py` has four profiles, and the manifest pins their outputs [V]:

| profile | sha256 | official score | mean Toffolis | change |
|---|---|---|---|---|
| `stack100` (the historical D70) | `a31716fa` | 336,846,688,159 | 356,981.4 | this is the circuit in `best/` |
| `deferred-bulk` | `9ab4da25` | 336,727,624,337 | 356,855.2 | -126 static gates |
| `head-deferred` | `5bd25c66` | 336,652,203,914 | 356,775.3 | -80 more |
| `paired-plain` (the default) | `fc2564c6` | 336,559,961,203 | 356,677.5 | -42 and -56 more |

All four: 890 qubits, 102,400 shots, 0 value and 0 phase errors (his receipts) [V]. The default profile is 0.085% lower in cost than `a31716fa`, which is 0.028% of the geometric mean. His build takes about 13 minutes and 5.5 GB of free disk and writes an 829 MB circuit.

### Qualitative

The public circuit we hold is the base of this stack, not something else: `a31716fa` is the `stack100` output (the hash is `BASE_SHA` in `build.py`). The four new modules are local rewrites worth about 300 static gates in total (deferred bulk cleanup, an in-place head evaluation, a paired GF(8) kernel); none changes the structure. So the 7% gap between `fixed4` and the public line is the D70 arithmetic itself (keyed field tensors, retained flags, the GF(4096) chart), not a trick we are missing in the last passes. The generator lowers each Fredkin to CX-CCX-CX at the end (`lower_fredkin.py`), so the public circuit has no `CSWAP` in the file but pays a Toffoli-class gate for each swap it uses. That refines the S5 finding (our 12,384 unconditioned `CSWAP`s) without answering it: how D70 avoids a data-dependent word swap in the outer would take a read of the 430 modules.

## Decision

1. Not porting the D70 generator now: the circuit is already in `best/`, and the stack above it is worth 0.085%. A port would give us the ability to modify a 430-module lineage whose last four edits are 0.01% each.
2. The 0.085% is available by building the `paired-plain` profile and verifying it on Kaggle at 10 salts (13 minutes plus a 10-salt DQI verify, about 40 minutes). The earlier DQI container approval covers a different builder, so building this one needs the owner's approval. Asked 2026-11-22.
3. The open design question (a DQI outer with no data-dependent word swap) stays open; the D70 source is the place to look if DQI is taken up again.

## Reproduce

Read the files named under Setup.

## Links

QCC-19, QCC-63, [v17 promoted](2026-11-21-dqi-v17-verified-promoted.md), [S5](2026-11-19-dqi-condition-statistics.md).
