---
id: 2026-11-12-dfthcsos-codesign
date: 2026-11-12
title: "A loader whose cost is the table's GF(2) rank works, but our fit stalls at 0.029 and a rank budget cannot be imposed after rounding"
type: experiment
benchmark: dfthcsos
methods: [co-design, loader, fit, generator]
status: done
outcome: negative
prs: [42, 45, 62]
studies: [docs/experiments/dfthcsos-codesign.md]
backfilled: true
licence_touched: true
---

## Question

Can we beat the unary loader's ratio 6.85 by fitting our own angle table to a loader family that is cheap for it, with everything derived from first principles (ADR-0009 stage 1) and the factorization started from the FCIDUMP?

## Setup

This entry was backfilled from the study note and git history on 2026-11-15. The note labels its fits E003 and E004 (and E002 for the loader), but those ids in `ledger/experiments.jsonl` belong to other
benchmarks (dqi, invsqrt), so none is listed under `experiments`; no dfthcsos row was written. Code: `src/dfthcsos_gen/bilinear.py`, `fit.py`, `rankfit.py`; scripts `scripts/run_fit.py`, `scripts/eval_fit.py`.
Fit on the laptop (6 threads, load 40 to 80), then on a 32-vCPU RunPod CPU pod for 90 minutes (about 1.5 USD, four processes of 8 BLAS threads). The stand-in table for E004 reads the host's 12-bit baseline
angles (Apache-2.0 sample submission) as 8-bit angles, for development only. Commit: not recorded.

## Results

### Quantitative

| Item | Value |
|---|---|
| bilinear loader, plane cost | `ceil(rank / 2)` Toffolis, rank = centered GF(2) rank; random plane rank 31 = 16 Toffolis |
| per pass at public geometry | `15 * 70 + 600 s`; public 4,151 per pass means `s` about 5.2 |
| laptop fit (8,143,44), 700 iterations | `error_2` 0.083 (3 to 6 s per iteration) |
| pod fit (8,143,44), seed 0, 7,300 iterations | `error_2` 0.0288 (0.7 s per iteration) |
| pod fits, seeds 1, 2 (about 3,000 it) / (9,127,39) 7,300 it | 0.0414, 0.0406 / 0.0329 |
| best pod fit scored with the host metric | `error_1` ~0, `Lambda` 745, `E_gap` 12.6 Ha at W scan t = 1.40 |
| rank forced to 8 after rounding (stand-in table) | angle mean-square error x about 14,000 |
| nearest-rounded planes, centered rank | 61 to 62 (bits 0 to 5), 36 to 37 (bits 6, 7) |

Gate is 0.02; the public shape's reported floor is 0.0192. Ledger unchanged, best verified stayed 489,890,973 (6.85) [M].

### Qualitative

* The loader is exact: tests show plans for every rank, static count equals kickmix's `num_toffoli_like`, and the simulated circuit loads with no phase kickback and clean workspace.
* The counting reading was that the public circuits' 4,151 Toffolis per pass imply plane rank about 10 [I]. This was later shown wrong by direct inspection of the public table (each plane has full centered rank),
  see 2026-11-13-dfthcsos-stage2.
* A rank budget cannot be imposed on rounded words: no plane is low rank by accident, and forcing rank after rounding costs 14,000x in error, almost all in the top planes where one flip costs up to 128^2.
  The structure must live inside the factorization (parametrise planes as `F + G + rank-r`) [M on the stand-in table].
* The from-scratch fit descends slowly (about 0.0005 per 700 iterations at the end), so longer runs from this start do not reach 0.02. The pod made iterations 4 to 9x faster than the laptop but is not the fix.
* Seeds 1 and 2 ran 2.4x slower per iteration because processes competed for cores unevenly, so they are behind at equal wall time, not necessarily at equal iterations.
* The (9,127,39) shape is no better than (8,143,44).
* Fitting the capital `W` properly is a second lever once `error_2` passes (public sample: `Lambda` 308 at `E_gap` 3.958).
* No own table passes, so no verifier run was justified.

## Decision

Next lever is a better initialisation or optimiser for the continuous fit, then structure in the factorization. The loader (E002 in the note) and objective are ready. This became `dfthcsos-structured`.

## Reproduce

The note gives no commands beyond naming `scripts/run_fit.py` (fit) and `scripts/eval_fit.py` (host-metric scoring).

## Links

PRs 42, 45, 62; `docs/experiments/dfthcsos-codesign.md`; ADR-0009; follow-ups 2026-11-12-dfthcsos-structured and 2026-11-13-dfthcsos-stage2.

> Corrected in part by [2026-11-13-dfthcsos-stage2](2026-11-13-dfthcsos-stage2.md): public planes have full centered rank, not about 10.
