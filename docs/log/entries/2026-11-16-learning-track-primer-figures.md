---
id: 2026-11-16-learning-track-primer-figures
date: 2026-11-16
title: "Primers and basics get figures from the same numbers as the text: 6 more figures, a compact circuit drawer, the adder diagram checked against kickmix"
type: decision
benchmark: docs
methods: [docs-site, figures]
status: done
outcome: positive
prs: [200]
backfilled: false
licence_touched: false
---

## Question

After the first figures and widgets, which pages still taught with text and code alone, and can the new figures use only
numbers that the pages already state, so a figure cannot drift from its text?

## Setup

Same method as [the first learning-track entry](2026-11-16-learning-track-figures-and-widgets.md): functions in
`analysis/learn_figures.py` draw committed SVGs, the numbers live in `analysis/numbers/learn.json`, and tests check them.
New: `circuit_draw` can pack gates into shared columns (`compact=True`), and a gate can write or wait on a classical bit.
Figures inspected in Chromium on the light and dark backgrounds. Commit: not recorded.

## Results

### Quantitative

| Page | New figure |
|---|---|
| qubits and gates | the Bell state as a circuit; memory of a state vector against qubit count (46 qubits need about a petabyte) |
| primer invsqrt | Toffolis per direction by stage: the Horner and three Newton multiplications are 3,423 of 3,871 (88%) |
| primer dqi | the reference decoder's 5,725,461 Toffolis by stage (the two Euclid passes are 74%) |
| primer dfthcsos | the baseline's `T_total` 93,237 and `Q_total` 730 by part |
| kickmix hands-on | the 4-bit adder as a circuit, 24 gates in 11 wires |

### Qualitative

* Tests tie each figure to its page: the stage numbers must add up to their totals and appear in the page text, so editing
  one without the other fails.
* The adder diagram is checked against the real kickmix circuit: three Toffolis, 11 qubits, and 27 instructions, where
  kickmix counts `init_and` and `del_and` as two instructions each. The diagram draws `init_and` as a Toffoli into a fresh
  qubit and `del_and` as `HMR` plus a CZ that runs when the measured bit is 1.
* First drafts had overlapping labels on narrow bar segments and clipped axis labels; narrow segments are now labelled
  above the bar. The state-vector title first said "hopeless long before 46 qubits", which overstated it; it now states the
  petabyte.

## Decision

Learning-track figures are complete for every page that had a numbers table or a circuit. Further pages get figures when
they gain such content.

## Reproduce

```
make learn-figures
uv run pytest tests/unit/test_learn_figures.py
make docs
```

## Links

PR 200; `analysis/learn_figures.py`, `analysis/circuit_draw.py`, `analysis/numbers/learn.json`.
