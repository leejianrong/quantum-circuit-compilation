---
id: 2026-11-12-dqi-qubits
date: 2026-11-12
title: "Cutting the divstep decoder from 4,013 to 2,764 qubits doubles the ratio to 2.64, and its dialog is at its information minimum"
type: experiment
benchmark: dqi
methods: [qubit-reduction, generator, decoder]
status: done
outcome: positive
prs: [51, 52]
rows: [4c3b4906, 9d91b487]
studies: [docs/experiments/dqi-qubits.md]
backfilled: true
licence_touched: false
---

## Question

Cost is `R * Q^2 * T`, so a qubit is worth two Toffolis. How many qubits can our own divstep decoder shed, and
where is the floor of that architecture?

## Setup

This entry was backfilled from the study note and git history on 2026-11-15. Start: the v0 decoder (4,013 qubits,
1.04M Toffolis, ratio 1.224). Each change was checked with the official verifier on the small instances and on
`narrow` (25,600 shots); full-size numbers are the static count `narrow + 4,024 x 108` Toffolis, confirmed on Kaggle
(`notebooks/dqi_gen`, about 7 min per run once started, 102,400 shots, 5 salts). Commit: not recorded.

## Results

### Quantitative

| Step | Qubits | Toffolis (full) | `Q^2 T` |
|---|---:|---:|---:|
| v0 | 4,013 | 1,041,122 | 1.68e13 |
| 1. freeze the dead f row | 3,243 | about 1.10M | 1.16e13 |
| 2. Omega in place in `S_0..S_{t-1}` | 2,835 | 1,141,782 | 9.18e12 |
| 3. row ranges by step, free early shift | 2,776 | 1,017,112 | 7.84e12 |
| 4. clear `mu` through the Forney sweep | 2,764 | 1,017,742 | 7.78e12 |

Official, 5/5 salts PASS, zero errors [M]: step 3 (`4c3b4906`) cost 9.3372e12, ratio 2.617; step 4 (`9d91b487`)
cost 9.2623e12, ratio 2.638, against 1.9973e13 (1.224) for v0. The static prediction matched to the Toffoli, and
cost is identical across salts. Remaining 2,764: syndromes 840, `v_g` + `v_f` 864, dialog 945, scalars 20,
Forney scratch about 95.

### Qualitative

* The `f` row is dead once it overflows: decodable syndromes have linear complexity at most `t`, so a row
  that would pass degree `t` is never read again. Dropping the tail without a freeze flag fails (value errors on
  83% of shots), so the tail is nonzero but unread. The freeze bit cannot be recomputed from the after-state.
* Omega can live inside the syndrome registers (descending in-place update), saving 420 qubits at +40k Toffolis.
* Dead ends: erasing `S_{t..n-1}` during Forney (-107 peak qubits for +154k Toffolis, net loss); Euclid-order
  divsteps with a shared register (2n + 2 slots, no smaller than syndromes + dialog); the series form (840 qubits of
  garbage replace the 840 of `S`); a Horiguchi-Koetter scan (worse).
* The dialog (`c`, `sw`, `sh`) cannot be dropped inside this state: `sw` and `sh` are not recoverable from the
  after-state, and `c` is real information (70 x 12 bits is the entropy of `S`). The obstruction is the choice of state.

## Decision

Both copies of the information (`S` and the dialog) are alive at the Forney peak; the 892-qubit public frontier must
hold one. The next lever is a different state: an in-place reversible solver with no dialog (the next entries).

## Reproduce

Small-instance checks use `dqi_gen.instances --gen divstep`; the note gives no other command. Full size ran on
Kaggle through `notebooks/dqi_gen`.

## Links

PRs 51, 52; ledger rows `4c3b4906`, `9d91b487`; `docs/experiments/dqi-qubits.md`.
