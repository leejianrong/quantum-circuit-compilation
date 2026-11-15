# Entry template

Copy this block into `docs/log/entries/<YYYY-MM-DD>-<slug>.md` and fill it in. The file name is the entry
id. `make log` lints the entry and rebuilds the indexes; `make log-check` is what CI runs.

Rules of the log:

* **Append-only.** Do not rewrite an old entry's findings. If it was wrong, write a new entry of
  type `correction`, list the old id in `corrects`, and put `superseded_by` on the old one.
* **Negative results count.** Set `outcome: negative` and say why it failed.
* **Say what is measured and what is inferred.** Tag claims **[M]** measured by us, **[V]** read from a
  source, **[I]** inferred, as the studies do.
* **Numbers link to the ledger.** Put the circuit sha prefix (8+ hex characters) in `rows` and the
  experiment id in `experiments`; the lint checks they exist.
* **No third-party code, tables or circuits** in an entry (see `PROVENANCE.md`); describe and measure.
* Backfilled entries set `backfilled: true` and say, under Setup, how the entry was reconstructed.

````markdown
---
id: 2026-11-15-short-slug
date: 2026-11-15
title: "One line: the result, not the activity"
type: experiment            # experiment | run | decision | reading | correction | incident
benchmark: dqi              # invsqrt | dqi | dfthcsos | infra | docs
methods: [stage-ledger]     # free tags, lower-case, used for the by-method index
status: done                # open | done | superseded
outcome: positive           # positive | negative | inconclusive | correction | n/a
commit: abc1234             # the commit the work ran on
prs: [188, 189]
experiments: [E040]         # ids in ledger/experiments.jsonl
rows: [37d8047d]            # sha prefixes (8+) of circuits in ledger/results.jsonl
studies: [docs/experiments/dqi-syed-decode.md]
corrects: []                # entry ids this entry corrects (required for type: correction)
backfilled: false
licence_touched: false      # true if a third-party source or circuit was read or used
---

## Question

What we wanted to know, and why now. One or two sentences.

## Setup

Commit, machine or Kaggle kernel, salts, shot settings, inputs (by hash), what was held fixed.
Assumptions we made. Anything that makes the run non-standard.

## Results

### Quantitative

A table of the numbers, with units, and the figure or ledger rows they come from.

### Qualitative

What surprised us. What did not work. What we now believe differently. Dead ends.

## Decision

What we do next, or why we stop. Open questions this leaves.

## Reproduce

The exact command or commands, and where the outputs live (path, Kaggle kernel, dataset).

## Links

PRs, ledger experiment ids and row hashes, figures, the long study, ADRs.
````
