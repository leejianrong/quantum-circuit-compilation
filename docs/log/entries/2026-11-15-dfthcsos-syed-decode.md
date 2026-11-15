---
id: 2026-11-15-dfthcsos-syed-decode
date: 2026-11-15
title: "syed3000's 11.31x table is output only; our loader code could load it at 9.06x today, and matching 11.31 is not a win"
type: reading
benchmark: dfthcsos
methods: [source-decode, loader, cost-model]
status: done
outcome: correction
prs: [185]
studies: [docs/experiments/dfthcsos-syed-decode.md]
corrects: [2026-11-13-dfthcsos-stage2]
rows: [91d0ad25]
backfilled: true
licence_touched: true
---

## Question

How was syed3000's 11.31x dfthcsos circuit (cost 296,635,967.59) produced, can our loader code take his table, and what could beat 11.31 from it?

## Setup

This entry was backfilled from the study note and git history on 2026-11-15. Read-only study of the Apache-2.0 archive (copyright 2026 Syed Asad Ali): extracted to scratch, code read only, `submission.npz` loaded as data (`allow_pickle=False`)
and scored with the competition's `evaluate_words` and our `src/dfthcsos_model`. No circuit built or verified, ledger untouched. Tags: [V] source, [M] measured with our code on his data, [I] inference.
Scratch scripts (`eval_syed.py`, `plans_check.py`, `analyse_words.py`, `relsupport.py`, `scen.py`, `helper.py` and others) live in the session scratchpad, uncommitted. Commit, machine: not recorded.

## Results

### Quantitative

| Quantity | Value |
|---|---|
| shape, bits, addresses | (8, 143, 44), 8, 1,220 |
| `error_1`, `error_2`, `E_gap`, `Lambda`, `lambda_eff` | 0.019610, 0.0199988, 3.9148982, 282.974, 46.9073 |
| `T_total`, `Q_total`, cost | 14,810, 427, 296,635,967.5936 (model matches every digit) [M] |
| angle loaders | 8,148 Toffolis (55.0%); 2,945 products, 1,034 high ANDs, 90 low ANDs per pass |
| products per circuit | 213 (k=0), 212 (k 1-3), 193 (k 4-6), 189 (k 8-14); our per-plane planner 253 to 285 |
| median L1 per copy of `w`, exact zeros | his 1.12, 18%; our fit-b 2.46, 0%; fit-e 2.22, 0% |
| our loader on his words: J=4 as is / helper trick / his plans as data / bound 188 | 9.055 / 9.997 / 11.312 / 11.513 [M count, I feasibility] |
| match vs `best/` 91d0ad25 (11.20) | geometric-mean gain (11.31/11.20)^(1/3) = 1.0033 |

### Qualitative

* The archive ships the polish and the loader compiler, not the continuous fit; the research scripts start from earlier packages (v14, v18) not in the zip. We can reuse the table but not regenerate its basin.
* CORRECTION of 2026-11-13-dfthcsos-stage2: that note said the eighth plane is a "helper" `bit7 xor bit6` that is "almost always 0" and a cheap pure monomial. Measured: for every word of every batch it equals a pure function of the four low address bits, the same in all 15 batches,
  one monomial per slot (low monomials 3, 5, 6, 9, 10), density 25% [M]. It is a free gauge (rotating by +pi flips bit 7 only and negates the vector, which the objective ignores), and gives five free low lines by reusing the old word registers [I].
* Codes in the table [M]: bit 0 of each word has no nonlinear low part (k >= 4), plus a parity code on bit 1 over five words (k >= 8). Each relation removes about 4 products (212, 193, 189).
* The difference between 254 and 189 products is the cut search, which we lack; the 189 floor is a counting bound (`dim W >= 5 x 75`).
* His plans are certificates: all columns independent and every high-monomial cross matrix inside the span [M]. His loaders are proven only on two legal endpoints, so the helper trick is not valid for arbitrary register contents.
* Two generations of loader change are visible: the early batches were re-rounded (shares 1% to 16% of words with the public 11.20 table; batches 6 to 14 69% to 88%). All of his gain over 11.20 (1.0%) is loaders (8,302 to 8,148 angle Toffolis); `lambda_eff` is slightly worse.
* Lambda 283 vs our 490 to 560 is a gap in weights, not decided as basin vs objective; he minimises `lambda_eff` under gates, we penalise. Own-basin route (Lambda 489 to 283, 8 bits, cut-planned loader) tops out near 8.5x because our shape carries more Q and T_prep [I].
* Ranked levers beyond 11.31: recode batches 0 to 7 (+1.6%), wider circuits at lb 5, J 8 (up to +18%, floor assumes cuts exist), smaller shape (6,132,36) model 12.5; weights-only refit under 0.1%; 7 bits ruled out (see `2026-11-12-dfthcsos-low-brot`).

## Decision

Matching 11.31 has no leaderboard value alone. Cheap test of basin vs objective: an `alfit`-style constrained refit on our own vectors (item 7a). Wider circuits is the only lever with double-digit headroom. Four ideas to log in `docs/PROVENANCE.md` (helper line trick, relations as code, explicit plan data, padding rows); using his plan JSONs needs a notice in `THIRD_PARTY_NOTICES.md` (owner decision).

## Reproduce

The note gives no commands beyond describing small scripts (seconds each, `.venv/bin/python -I`): load the npz as data, `dfthcsos.verify.evaluate_words`, `dfthcsos_model.score`, `dfthcsos_gen.bilinear.centered_rank`, `dfthcsos_gen.anf.anf_toffolis`.

## Links

PR 185; `docs/experiments/dfthcsos-syed-decode.md`; corrects 2026-11-13-dfthcsos-stage2; `docs/PROVENANCE.md`; sibling 2026-11-15-invsqrt-syed-decode.
