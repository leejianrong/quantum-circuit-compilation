---
id: 2026-11-12-dqi-inplace
date: 2026-11-12
title: "A dialog-free Lanczos decoder halves the qubits (2,764 to 1,472) and verifies, but 0.75% of shots fail and R doubles"
type: experiment
benchmark: dqi
methods: [qubit-reduction, generator, decoder]
status: done
outcome: positive
prs: [63, 64]
studies: [docs/experiments/dqi-inplace.md]
backfilled: true
licence_touched: false
---

## Question

Can the key-equation solver be made reversible without storing a dialog, to move from 2,764 qubits toward the
public frontier's 892?

## Setup

This entry was backfilled from the study note and git history on 2026-11-15. Ideas came from papers and standard
numerical analysis (Chebyshev and Lanczos recursions, Gauss quadrature); the only public hint used is that the
892-qubit decoder is a Schur-type design with a scan of about 11 Toffolis per point (`docs/PROVENANCE.md`). No
circuit file was read. Code: `src/dqi_gen/lanczos.py`, classical model `src/dqi_gen/jacobi.py` (GF(2^12), 4,000
weight-law shots). Full size on Kaggle, official verifier, 102,400 shots, 5 salts. Commit: not recorded.

## Results

### Quantitative

| Version | Qubits | Toffolis | Official cost | Ratio | Failing shots |
|---|---:|---:|---:|---:|---|
| divstep (PR 51) | 2,764 | 1,017,742 | 9.262e12 | 2.64 | 0 |
| Lanczos | 1,472 | 1,210,488 | 5.39e12 to 5.59e12 | 4.37 (worst) to 4.53 | 755 to 834 of 102,400 |

5/5 salts PASS [M]; the circuit's full sha256 is cited as `caeb5e61...` and is not in the ledger under that prefix.
The static prediction was 5.5e12 (1,400 qubits predicted, 1,472 built). Qubits fell 47%, Toffolis rose 19%. Predicted
classical failure events: premature `h_k = 0` 0.9%, `p_k(0) = 0` 0.5% [M, classical].

### Qualitative

* Key idea: take the state to be the pair of consecutive monic orthogonal polynomials of the moment functional. The
  update then consumes its two quotients into two new coefficients, so the pair determines the step: a bijection with
  no dialog [I, proved on paper and tested in `jacobi.peel`]. Raw syndromes are erased as the pair grows.
* The Gauss-quadrature scan needs no Omega but costs one more product per position (171 per position built,
  against 108).
* The first-order failure prediction (1.4%, R about 2.7) was too pessimistic: the `p_k(0) = 0` event is handled by
  a controlled shift, leaving 0.75 to 0.81% observed and R of 2.0 to 2.1. With no failures the same circuit would
  cost about 2.6e12 (ratio 9.4).
* Dead ends (analysis only): the Chebyshev two-row form, series-form divsteps, single remainder plus quotients
  (about 1.2M Toffolis, no gain), in-place series reciprocal (no O(1)-scratch form), and retry with a shifted node
  set. Exact look-ahead for `h_k = 0` was estimated at +80% decoder for a net 20% and not built.

## Decision

Keep Lanczos as the best own DQI (ratio 4.37) and attack its Toffolis and failures. Floor of this family: about 420
qubits beyond the 840, since only `k` syndromes are erased at step `k`. A faster GF(2^12) multiplier (rank 42) and an
amplitude polynomial are the next Toffoli levers; the scan is 58% of `T`.

## Reproduce

```
QCC_DATA=data uv run python -m dqi_gen.instances --gen lanczos --instance narrow --shots 8192
```

## Links

PRs 63, 64; `docs/experiments/dqi-inplace.md`.
