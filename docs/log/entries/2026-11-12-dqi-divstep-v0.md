---
id: 2026-11-12-dqi-divstep-v0
date: 2026-11-12
title: "Our first DQI decoder (divsteps plus a GF(2^6) tower) has 4.8x fewer Toffolis than the reference but only 18% lower Q^2 T"
type: experiment
benchmark: dqi
methods: [generator, decoder]
status: done
outcome: positive
prs: [43]
studies: [docs/experiments/dqi-divstep-v0.md]
backfilled: true
licence_touched: false
---

## Question

Can constant-time division-free steps (divsteps) plus a tower-field inversion beat the host reference under the
official verifier, using only papers and standard algorithms (ADR-0009 stage 1; no public circuit file read)?

## Setup

This entry was backfilled from the study note and git history on 2026-11-15. `src/dqi_gen/decoder.py` runs `n = 2t`
divsteps on the syndrome series, keeps rows instead of polynomials, and does the Chien and Forney scan with a
tower field for the inversion. Checked with the official verifier at 3,072 shots on small instances and 25,600 on
`narrow` (full `n` and field, 71 positions). Full size ran on Kaggle (`notebooks/dqi_gen/run.py`, 102,400 shots per
salt). Commit: not recorded.

## Results

### Quantitative

| Instance | Reference Q, T | Ours Q, T | Ours Q2T | Better by |
|---|---|---|---:|---:|
| tiny 15,4,4 | 115, 22,090 | 129, 1,122 | 1.87e7 | 15.6x |
| small 63,10,6 | 229, 93,542 | 360, 9,246 | 1.20e9 | 4.1x |
| medium 255,20,8 | 462, 326,559 | 846, 43,010 | 3.08e10 | 2.3x |
| large 1023,40,10 | 972, 1,558,907 | 1,976, 271,447 | 1.06e12 | 1.4x |

Zero failures everywhere [M]. `narrow` passes 25,600 shots (606,530 Toffolis, 4,013 qubits). Full size: static
about 1.04M Toffolis (reference 5.73M) at 4,013 qubits (reference 1,893); static `Q^2 T` about 1.68e13 against
2.05e13, 18% lower. The version before the second tower level (1,184,435 Toffolis) passed three salts at full size
with zero failures in 417 s wall and 4.5 GB peak child RSS [M].

### Qualitative

* Toffolis fell 4.8x but qubits rose 2.1x and are squared, so the first version is only a small win by itself.
* The per-position cost went from 351 (Itoh-Tsujii) to 143 (one tower level) to 108 (second level, GF(2^3) over
  GF(2^6)). Odd degrees fall back to Itoh-Tsujii and pass too.
* Dead ends: a first version tracking the `u` rows too verified but was 3.2x worse (5,275 qubits, 2.37M Toffolis);
  evaluating the phase through power sums needs about 2,200 Toffolis per position, worse than 143; per-position
  division cannot skip work because `sigma = 0` is a quantum condition.
* The per-salt cost lines of the three-salt run were not captured (stdout was not kept); the runner now keeps them.
  The final version's full-size cost was not in the ledger when the note was written.

## Decision

Attack qubits first: the 4,013 are 840 read-only syndromes plus about 3,170 of state, the largest pieces being the
relabelling garbage of `v_f` (1,272) and the dialog (910). Then the Forney scan and the divstep row update (57%
of the key-equation Toffolis). The qubit work follows in the next entry.

## Reproduce

```
QCC_DATA=data uv run python -m dqi_gen.instances --gen divstep --instance narrow
```

`--instance full` runs on Kaggle through `notebooks/dqi_gen/run.py`.

## Links

PR 43; `docs/experiments/dqi-divstep-v0.md`; ADR-0009.
