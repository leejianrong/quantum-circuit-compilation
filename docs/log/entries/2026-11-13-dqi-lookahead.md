---
id: 2026-11-13-dqi-lookahead
date: 2026-11-13
title: "Exact look-ahead is not worth building (a perfect fix is worth at most 1.74x); five Lanczos qubit trims lift the ratio from 6.08 to 6.81"
type: experiment
benchmark: dqi
methods: [decoder, qubit-reduction, generator]
status: done
outcome: positive
prs: [81]
experiments: [E021]
rows: [3b456a35, 64951ff3]
studies: [docs/experiments/dqi-lookahead.md]
corrects: [2026-11-12-dqi-failures]
backfilled: true
licence_touched: false
---

## Question

Is an exact look-ahead step for the premature-zero failures worth building, and how much qubit and Toffoli trimming
is left in the Lanczos decoder? Start: 1,457 qubits, 905,338 Toffolis, R about 2.07 (0.75% failing shots), ratio 6.08.

## Setup

This entry was backfilled from the study note and git history on 2026-11-15. Local checks on `narrow`; full-size
static prediction `narrow + 4,024 x 138` Toffolis at the same qubit count. Trims verified on `narrow` (3 salts at
25,600 shots, 0 phase errors, 0.67 to 0.83% failing), then on Kaggle (official verifier, 102,400 shots, 5 salts,
kernel `qcc-dqi-gen`). Commit: not recorded.

## Results

### Quantitative

| Failing shots | 0.75% | 0.50% | 0.30% | 0.10% | 0.01% | 0 |
|---|---:|---:|---:|---:|---:|---:|
| R | 2.07 | 1.83 | 1.62 | 1.39 | 1.23 | 1.19 |

| Full size version | Qubits | Toffolis | Worst-salt cost | Ratio |
|---|---:|---:|---:|---:|
| before | 1,457 | 905,338 | 4.017e12 | 6.08 |
| PR 79 (`3b456a35`) | 1,412 | 868,770 | 3.6576e12 | 6.68 |
| PR 80 (`64951ff3`) | 1,403 | 868,770 | 3.5895e12 | 6.81 |

All 5/5 salts PASS, and the static prediction matched to the Toffoli [M]. On `narrow` the trims took Toffolis from
350,026 to 313,458 and qubits from 1,457 to 1,403.

### Qualitative

* CORRECTION. The earlier failures note estimated exact look-ahead at +80% decoder, about +30% `T`, net about 1.2x.
  That is only a lower bound: after a degenerate step the pair's degree runs one ahead of the loop index for the
  rest of the run, and every array length, erased syndrome, head window, termination count and scan degree depends
  on that index. A data-dependent offset turns each into a controlled shift or a doubled dot product. A perfect fix
  is worth at most 1.74x before paying; a fix on a third of the steps removes a third of the failures (R 1.83) for
  about +10% Toffolis, a wash. Not built.
* The amplitude polynomial (scan near 11 per position) is not reachable from the pair: it needs the low raw moments,
  already erased, or another solver (cost estimates in the note: about 100k Toffolis for 420 more qubits, a loss at `Q^2`).
* The measured trims: fresh products cleared by measurement in the reverse pass (the tape had made every inverse a
  second full product), `A + B` in place inside the tower inversion, scan accumulators released while the tower
  runs, idle zero registers lent as scratch. Ideas dropped on paper: a fake node of known weight, detecting a
  premature zero for a retry (cannot be conditional in a static circuit), a window shift.
* Decoder now 304k of 313k Toffolis on narrow: heads 78k, erase 50k, row update 100k, cswaps 46k.

## Decision

Not promoted: `best/` needs 10 full-strength salts and 6.81 is far below the public circuit (about 65). Both the
decoder (1,400 to 1,403) and the scan (1,400) peaks would have to fall together for more qubit gains.

## Reproduce

The note gives no command. Static prediction: `narrow + 4,024 x 138` Toffolis.

## Links

PR 81; experiment E021; ledger rows `3b456a35`, `64951ff3`; `docs/experiments/dqi-lookahead.md`.
