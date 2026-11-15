---
id: 2026-11-12-dqi-cost-drivers
date: 2026-11-12
title: "DQI reference: 73% of its 5,725,461 Toffolis are two Euclid passes, and every qubit counts twice"
type: reading
benchmark: dqi
methods: [cost-breakdown, decoder]
status: done
outcome: positive
prs: [39, 43]
studies: [docs/experiments/dqi-cost-drivers.md]
backfilled: true
licence_touched: false
---

## Question

Where does the host's reference DQI circuit spend its cost, and which of the public claims (Berlekamp-Massey
style beats Euclid, the Forney sweep dominates, qubits are counted twice) hold under the verifier's own formula?

## Setup

This entry was backfilled from the study note and git history on 2026-11-15. The reference builder and verifier
supplied with the competition data (stated Apache-2.0, read only) were audited with `src/dqi_gen/audit.py`, a
per-mark Toffoli tally checked against kickmix's own `operation_statistics()` total. Full-size numbers were first
extrapolated from measured small instances (the full circuit does not fit the 7 GB laptop, ADR-0002), then tallied
exactly on Kaggle (`notebooks/dqi_gen`, 71 s, 8.9 GB peak). Commit and salts: not recorded.

## Results

### Quantitative

| Stage of the reference (full size, 1,893 qubits) | Toffolis | Share |
|---|---:|---:|
| forward Euclid pass | 2,109,450 | 36.8% |
| reverse Euclid pass | 2,109,450 | 36.8% |
| Chien search, Forney, phase | 1,444,737 | 25.2% |
| initial shift and its inverse | 61,824 | 1.1% |
| total | 5,725,461 | |

Chien plus Forney is exactly 351 Toffolis per position (4,095 positions). The extrapolation gave 2.10M per Euclid
pass and 1.437M for the sweep, so it was within about 1% [M]. Qubits at full size: 1,893 = 840 syndromes + 1,053
workspace [M]. Score is `R * Q^2 * T` [V, read from the verifier]; with zero failures `R` is 1.19 for every exact
circuit (the floor), and each extra failure raises `eps_plus` by roughly 1.4e-4 at first [M].

### Qualitative

* The score squares the qubit count, so a 1% cut in Q is worth a 2% cut in T. This confirms the public claim.
* Executed T equals static T within 0.1% (the only conditional blocks test a classical bit true with probability
  1 - 2^-12), so there is no data-dependent saving to harvest at this level; conditioning on a quantum value is
  impossible.
* With fewer than about 1,400 shots the zero-failure bound already exceeds 1/16 and the verifier raises, so small
  runs need at least 2,048 shots.
* Inside one Euclid pass the multiply-and-subtract is 64% (the unary-iteration sweep alone 54%).
* "Berlekamp-Massey style beats Euclid" holds for Toffolis: our first divstep solver does the job in about 0.93M,
  4.6x cheaper, but at more qubits [M, see the divstep entry]. "Forney is 56% of the best design" is plausible: it
  is a fixed 1.44M that does not shrink with a better solver.

## Decision

Next levers in order: qubits (the 892-qubit public frontier must keep the key-equation state in or beside the
syndrome registers, since the map from syndromes to locator and Omega is a bijection on decodable syndromes), then
the per-position inversion in the sweep (351, 4,095 times), then the solver.

## Reproduce

```
QCC_DATA=data uv run python -m dqi_gen.audit --m 63 --n 10 --degree 6
```

Runs in seconds. The full-size tally is the Kaggle kernel `notebooks/dqi_gen`.

## Links

PRs 39, 43; `docs/experiments/dqi-cost-drivers.md`; ADR-0002.
