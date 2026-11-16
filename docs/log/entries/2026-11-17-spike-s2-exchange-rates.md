---
id: 2026-11-17-spike-s2-exchange-rates
date: 2026-11-17
title: "S2: a qubit is 0.23% on DQI and dfthcsos but 2.3% on invsqrt; the dfthcsos gap is mostly the words, not the loader"
type: experiment
benchmark: infra
methods: [exchange-rates, cost-model]
status: done
outcome: positive
commit: a7986be
prs: []
experiments: []
rows: [997264ad, 30285faf]
studies: [docs/experiments/spike-s2-exchange-rates.md]
backfilled: false
licence_touched: false
---

## Question

What are one qubit, one Toffoli, one rotation and one unit of `Lambda` worth on each track, and where does the
dfthcsos gap sit? Hypothesis: the rates are stable enough (under 30% spread across circuits) to rank levers.
Kill criterion: spread above 30%.

## Setup

Algebra on the verifier formulas, `src/bench/rates.py`, tested by finite differences. Inputs from the ledger and from
public logs (reported, not yet verified by us for the v13-class circuits).

## Results

### Quantitative

| Track | 1 qubit | 1 Toffoli | qubit in Toffolis |
|---|---:|---:|---:|
| invsqrt | 2.27% | 0.0585% | 38.8 |
| DQI (889 to 890 q) | 0.225% | 0.00026% | 827 to 866 |
| dfthcsos | 0.234% | 0.0068% | 34.5 |

Rates between the two DQI points differ by 5% [M], so the spread criterion is met (not killed). invsqrt rotations:
7.35 Toffoli-equivalents each (43 bits), 14.6% of the cost [M]. `Lambda`: 0.178% per unit at 283. dfthcsos gap
11.31/2.50 = 1.65 (loader) x 2.74 (words) [M from ledger rows `997264ad`, `30285faf`]; `Lambda` is 1.32 to 1.41 of the
2.74 [I].

### Qualitative

The "one qubit is worth about two Toffolis" statement in `benchmarks.md` and `claims.md` mixed up percent and count:
it is 1% of qubits for 2% of Toffolis, one qubit is about 830 Toffolis. Both pages are fixed in this PR. The
dfthcsos gap is the words (2.74x) more than the loader (1.65x), which reorders S4 ahead of any loader work.

## Decision

Pursue S4 (words: `Lambda` penalty and 8-bit) before dfthcsos loader work. S2 is closed.

## Reproduce

`PYTHONPATH=src uv run pytest tests/unit/test_rates.py`; numbers in `docs/experiments/spike-s2-exchange-rates.md`.

## Links

QCC-60, `src/bench/rates.py`, E001 (`2026-11-12-dfthcsos-loader`).
