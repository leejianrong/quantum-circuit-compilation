---
id: 2026-11-14-dqi-gap-survey
date: 2026-11-14
title: "Our DQI circuit is 2.1% behind syed3000's, not where first guessed; the fused-finish switch fails with 1,512 of 3,072 phase errors"
type: experiment
benchmark: dqi
methods: [cost-breakdown, stage-ledger, survey]
status: done
outcome: inconclusive
prs: [181]
rows: [37d8047d, 7cbe8ecf, e9f54be3]
studies: [docs/experiments/dqi-gap-survey.md]
backfilled: true
licence_touched: true
---

## Question

Our `fixed` circuit (65.77x) matches the public extract stage verbatim, the extract plus synthesis round trip is within 0.6%
and the mask gauge is worth at most 0.2%. Where is the rest of the gap to syed3000's 67.4x, and which design changes could
close or beat it?

## Setup

This entry was backfilled from the study note and git history on 2026-11-15. Ours: `fixed.kmb` (350 MB, `37d8047d`), streamed
once with `dqi_gen.study` (about 60 s). The circuit has no `INFO_TAG`s, so stages come from the Toffoli-rate profile with
boundaries good to about +-3k T. Syed's numbers come from ledger row 84 (Kaggle, 5 salts) because his files were not on the
machine in the first pass; section 7 (2026-11-14) adds a static stream of his `dqi.kmb` after the dataset arrived in `public/`.
Vendored Apache-2.0 source under `third_party/syed_dqi/` was read, not run. Commit: not recorded.

## Results

### Quantitative

| | Qubits | Toffolis | Lowest-salt cost | Ratio |
|---|---:|---:|---:|---:|
| ours `fixed` | 890 | 391,326 | 368.43e9 | 65.77 |
| syed3000 (`7cbe8ecf`) | 889 | 384,003 | 360.73e9 | 67.4 |
| public frontier (`e9f54be3`) | 892 | 395,586 | 374.69e9 | 64.7 |

The same-salt gap is 2.1%: `T` gives 1.87% (7,323 Toffolis), `Q` gives 0.22% [D]. The scan is exactly 4,095 x 11 = 45,045 [M].
Syed's circuit has 7.6k fewer CCX, 3.7k fewer measurements, 150k fewer SWAP, and about three times the classical-bit and
conditional-block traffic [M]. Ours: extract plus synthesis plus unsynthesis plus unextract is 221.7k against 221.2k public.

### Qualitative

* Per-salt cost has three levels (x1, x1.0046, x1.0085) set by the verifier's salt. His 5 salts never reached the top level and
  ours did, so the headline 65.77 against 67.4 overstates the gap by 0.4%.
* Ours is asymmetric: unconvert (convert's mirror) is 12k above convert, while the public tags differ by 1.5k.
* The extractor's own ledger states peak 890 (864 + 26), so the 889th qubit must come from syed's composition. The 12 carry
  qubits are idle in the middle stages, but the peak is fixed by the extractor, so lending them does not lower the maximum.
* CORRECTION within the note. Idea 1, `fused=True` for the history-fused finish, does not work as a switch: `fixed.py` uses a
  history-free design, so on `narrow` the build verifies (890 qubits, 346,192 Toffolis) while the fused build fails with 1,512 of
  3,072 phase errors. The 3k to 6k T estimate is withdrawn. The remaining lead is the 12k convert/unconvert mismatch.
* The remaining 3.9k to 5.2k T is a guess [G] (convert/unconvert or options in syed's unvendored pipeline setup). Ranked ideas:
  per-call stage hooks, real gauge plus `j_min` 15 to 18 or 19 (about 0.6 to 0.7%), the 889th qubit (0.22%), a lower-rank GF(2^24)
  product (each unit of rank 1.3k T), and a sub-quadratic extraction (research bet). Ideas 1 to 3 together equal his lead.
* Later work (the stage-ledger entry) found the gap is mostly the extractor return path, so the guess that it sat in
  convert/unconvert was not supported.

## Decision

Get a native per-stage ledger of both circuits before changing anything; the first action is to run `dqi_gen.study` on his
circuit. No change to `fixed.py` came from this survey.

## Reproduce

The note gives no command beyond `dqi_gen.study` on the two circuits (one at a time).

## Links

PR 181; ledger rows `37d8047d`, `7cbe8ecf`, `e9f54be3`; `docs/experiments/dqi-gap-survey.md`; follow-up
[2026-11-15-dqi-stage-ledgers](2026-11-15-dqi-stage-ledgers.md).

> Corrected in part by [2026-11-15-dqi-stage-ledgers](2026-11-15-dqi-stage-ledgers.md): with native stage marks the gap is 62% extractor return path, not convert and unconvert.
