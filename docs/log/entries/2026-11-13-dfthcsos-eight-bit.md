---
id: 2026-11-13-dfthcsos-eight-bit
date: 2026-11-13
title: "Our own table cannot reach 8 bits: every rounding schedule leaves about 0.025 of noise, and the gentle end of the schedule is not the problem"
type: experiment
benchmark: dfthcsos
methods: [qat, fit, low-bit, cost-model]
status: done
outcome: negative
prs: [85, 86]
experiments: [E022]
studies: [docs/experiments/dfthcsos-eight-bit.md]
backfilled: true
licence_touched: true
---

## Question

The cost model says the fully-own ratio 1.98 (11 bits) jumps to about 4 at 8 bits (`Q_total` 790 to 494). Is there a gentler end to the quantisation schedule, or a fit, that reaches `error_2 < 0.02` on an 8-bit grid?

## Setup

This entry was backfilled from the study note and git history on 2026-11-15. Laptop, our own (8,143,44) fit from the pod (`error_2` 0.0288), `tsym.npy` from the FCIDUMP, balanced tree. The earlier 0.0138 (8,176,56) table and its
11-bit words were lost with a deleted worktree, so every number is on the weaker 0.0288 seed and compares with each other, not with E020. E022 is the closing experiment. The note also names E008, E019, E020; those are other studies'.
The public table's tree was analysed in aggregate only (logged in `docs/PROVENANCE.md`). Commit: not recorded.

## Results

### Quantitative

| Experiment | Bits | `error_2` |
|---|---:|---:|
| naive rounding of the seed (continuous 0.0288) | 8 / 10 | 0.2105 / 0.0607 |
| schedule of 6 stages x 80 it | 8 / 10 | above 0.09 (stopped) / 0.0383 |
| 66 stages, nearest-to-grid order | 10 | 0.0380 |
| 24 or 66 stages, floor/ceil by quadratic model | 10 | 0.0423 / about 0.042 |
| noise-robust fit (mean over 2 noise draws) | 8 | 0.159 (naive 0.21) |
| lattice descent, single +-1 moves | 10 | no move set lowers it |
| L1 term mu = 4e-6 (400 it) | - | `error_2` 0.03063 vs 0.02848; Lambda proxy 247.3 vs 285.4 |

All [M]. E022 closed as "8 bits not reachable". Shape search by cost model only (unary loader, `lambda_eff` 62.6): (8,143,44) 5.13 / 2.97 / 2.65 / 2.39 at 8 / 9 / 10 / 11 bits; (8,176,56) 4.05 / 2.44 / 2.18 / 1.98 [model].

### Qualitative

* At 10 bits the loss above the continuous fit is sqrt(0.038^2 - 0.0288^2) = 0.025 whatever the schedule; the earlier session saw 0.0216 on the better table. A finer end (66 stages) changes it by 1%.
* Fixing 40% of angles at 8 bits already costs 0.03, so the loss accumulates and is not concentrated in the last angles at this width.
* Naive 8-bit noise is 0.206 (4x the 10-bit noise), so QAT would have to cut it 14x; every variant delivered 2.3x.
* Choosing floor or ceil by a quadratic model is worse than nearest rounding: the Hutchinson diagonal is dominated by off-diagonal noise, curvature differs 600x between vectors, and single moves are strongly coupled.
* Noise-averaged fitting does not find a flat table in 100 L-BFGS iterations per ramp step.
* Mean-field tree model: about `n log2 n` for any tree on near-uniform masses (mass entropy 6.21 of 6.25 bits), so path or mass-sorted trees are no better. The public table's tree is binomial (mean depth 2.95), hence depth is not what makes its 8 bits work.
* L1 trade is poor: 13% off `Lambda` costs 7% of `error_2`, which the 11-bit table (0.0179 of 0.02) cannot spare.
* A smaller shape is worth up to 1.5x at 10 to 11 bits if its continuous fit reaches the gate (a fit-quality question). The 8-bit `Q` cliff exists only for B above 128.
* 8 bits needs a base error far below ours or a discrete joint optimiser in angles and weights.

## Decision

Fetch the two Kaggle fits (`leejianrong/qcc-dfthcsos-fit`, 8,176,56 for 9,000 iterations; `-fit-b`, 8,143,44 for 30,000 iterations). If (8,143,44) reaches about 0.015, QAT at 10 and 11 bits gives 2.65 and 2.39. 8 bits is parked until a discrete optimiser exists. Past 2.4 the loader is the cost (78% of `T_total` at 11 bits).

## Reproduce

```bash
uv run bench kaggle fetch leejianrong/qcc-dfthcsos-fit   # and -b; outputs land in out/kaggle/
```

Kernel source: `notebooks/dfthcsos_fit/`. Schedule scripts named in the note: `dfthcsos_qat.py`, `dfthcsos_qat2.py`, `dfthcsos_noisefit.py`, `dfthcsos_lattice.py`, `run_fit.py --l1 mu`, `dfthcsos_l1_eval.py`.

## Links

PRs 85, 86; E022; `docs/experiments/dfthcsos-eight-bit.md`; `docs/experiments/dfthcsos-structured.md`.
