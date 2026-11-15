---
id: 2026-11-12-dqi-failures
date: 2026-11-12
title: "Lanczos failures (0.75% of shots) cannot be fixed locally; a rank-42 multiplier and tower inversions cut Toffolis to 905k instead"
type: experiment
benchmark: dqi
methods: [decoder, generator]
status: done
outcome: positive
prs: [68]
rows: [aa309296]
studies: [docs/experiments/dqi-failures.md]
backfilled: true
licence_touched: false
---

## Question

Which inputs make the Lanczos decoder fail, can any local change remove them, and which Toffoli cuts are available
instead? Cost is `R Q^2 T`; 0.75% failures cost R of about 2.0 against 1.19 with none.

## Setup

This entry was backfilled from the study note and git history on 2026-11-15. Classical enumeration with
`jacobi.solve`, GF(2^12), n = 70, DQI weight law, 75,000 shots. The Toffoli cuts were each verified on `mid12` and
`narrow`, then at full size on Kaggle. Commit and salts of the classical run: not recorded.

## Results

### Quantitative

| Event (75,000 shots) | Shots | Rate |
|---|---:|---:|
| premature `h_k = 0` at a step `k < w` | 516 | 0.69% |
| `p_k(0) = 0` at an erasing step (handled by the controlled shift) | 563 | 0.75% |

| Step | Qubits | Toffolis (full) | Official cost, worst salt | Ratio |
|---|---:|---:|---:|---:|
| Lanczos (PR 64) | 1,472 | 1,210,488 | 5.59e12 | 4.37 |
| rank-42 multiplier (PR 66, `aa309296`) | 1,472 | 950,487 | 4.347e12 (5/5 PASS) | 5.62 |
| tower inversions and divisions (PR 67) | 1,457 | 905,338 static | see the next entry | |

The circuit's observed 0.72 to 0.81% agrees with the classical enumeration [M].

### Qualitative

* The failure set depends only on the error word (weighted Vandermonde minors), not on the circuit: each step fails
  with the probability that a random field element is zero (about `2^-12` per step; `w` is 28 to 34 for 80% of
  shots), so no local fix lowers it.
* Ruled out: rescaling nodes and shifting the origin (same zeros), a shifted moment window (needs `2w <= n - s`, only
  97% / 88% / 73% of shots allow shifts 1 / 3 / 5), a multiplier on the functional, and randomised Hankel
  preconditioning (already at the floor). Exact look-ahead is the only exact fix; the note estimates +80% decoder,
  about +30% `T` for R 2.0 to 1.25, net about 1.2x, and did not build it. The next entry shows that estimate was
  optimistic.
* The multiplier writes GF(2^12) as a degree-4 extension of GF(8), evaluates at 7 points of the projective line,
  and costs 42 Toffolis per product (against 63) at 3 extra qubits. Tower inversion costs about 82 to compute and 46
  to clear (against 315 each), saving 45k Toffolis and 15 qubits.
* After the cuts, the scan is 4,095 x 138 = 0.565M and near the floor of its formula; the decoder profile is
  products 74%, controlled swaps 14%, controlled adds 5%. Peak qubits sit in the scan (1,457).

## Decision

Keep the failures (no local fix), take the Toffoli cuts, and look at look-ahead and qubit trims next.

## Reproduce

The note gives no command; the classical enumeration is `src/dqi_gen/jacobi.py` and the multiplier test is
`tests/unit/test_dqi_gfmul.py`.

## Links

PR 68 (PRs 66 and 67 are named in the table); ledger row `aa309296`; `docs/experiments/dqi-failures.md`.

> Corrected in part by [2026-11-13-dqi-lookahead](2026-11-13-dqi-lookahead.md): the look-ahead cost estimate above (+80% decoder, +30% `T`) is a lower bound; alignment makes it worse, so look-ahead is not worth building.
