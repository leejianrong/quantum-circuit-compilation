---
id: 2026-11-12-dfthcsos-structured
date: 2026-11-12
title: "A fully own dfthcsos circuit passes the verifier (ratio 1.98 at 11 bits); the gap to 6.85 is bit width and lambda_eff"
type: experiment
benchmark: dfthcsos
methods: [fit, qat, loader, cost-model]
status: done
outcome: positive
prs: [72, 73]
experiments: [E019, E020]
rows: [48dd4475, 42226887]
studies: [docs/experiments/dfthcsos-structured.md]
backfilled: true
licence_touched: false
---

## Question

Can an own factorization, fitted from the FCIDUMP with our optimiser and loaded by our own unary loader, pass the real verifier (milestone M1), and what stands between it and the public ratio?

## Setup

This entry was backfilled from the study note and git history on 2026-11-15. All ours (ADR-0007, ADR-0009): no public circuit, word table, gate list or constant was read, so nothing was added to `docs/PROVENANCE.md`.
Fits on a 32-vCPU RunPod CPU pod (spot, 0.96 USD/h, three pods, about 3.4 USD in all; one pod lost for 20 minutes to a relay sender that died). Own `tsym.npy` sent with `runpodctl send`.
Verifier runs E019 and E020 at 3 salts. The note also labels its fits E005 to E008, but those ids in `ledger/experiments.jsonl` are other benchmarks' experiments, so they are not listed.
QAT run: laptop, 14 threads, about 45 minutes per run. Commit: not recorded.

## Results

### Quantitative

| Quantity | E019 (12 bit, balanced tree) | E020 (11 bit, QAT) |
|---|---|---|
| shape | (8, 176, 56) | same table family |
| loader | unary, J = 8, 10 circuits, 117 qubits | unary, J = 9, 9 circuits, 13,338 Toffolis, 120 qubits |
| verifier | PASS 3/3, cost 1,850,153,217 | PASS 3/3, cost 1,697,674,805 |
| ratio | 1.81 | 1.98 |
| `error_1`, `error_2` | 0.0036, 0.0165 | 0.0070, 0.0179 |
| `Lambda`, `E_gap`, `lambda_eff` | 480.4, 4.0906, 62.56 | 481.8, 4.0898, 62.64 |

Both equal the cost-model prediction exactly [M]. Fit studies (`error_2`): shapes from random start after about 8,000 iterations 0.0215 (8,143,60) to 0.0270 (8,143,44, maxcor 100);
growth continuation to (8,176,56) 0.0138 versus plain continuation 0.0176 [M]. Rounding the 0.0215 fit: balanced tree 0.0555 at 10 bits and 0.0255 at 12, path tree 0.1207 and 0.0370 [M].
QAT from the 0.0138 table: 10 bits 0.0256 (short) / 0.0260 (long) fails; 11 bits 0.0179 passes [M]. Model ratios for the same shape: 12 bit 1.81, 11 bit 1.98, 10 bit 2.19, 8 bit 4.05 [model].

### Qualitative

* Growth (padding a converged fit with new `c` columns or `b` rows at 5% of the typical weight; zero start has zero gradient) crosses a plateau that more iterations do not: plain continuation gained 0.004, growth 0.006 to 0.009.
* Larger C and larger B both help at equal iterations; a larger L-BFGS memory is slower and no better.
* Rotation of the `c` index leaves `error_2` unchanged but halves `sum_c |w_c|_1^2` (about 1.5x in `Lambda`); fitting the capital `W` by SLSQP gave `lambda_eff` 61.7 to 62.6 against 136 for the one-parameter scan, and every start reached the same optimum.
* Tree matters for rounding; refitting `w` on the decoded vectors removes about a tenth of the quantization loss.
* QAT pattern: early stages are free (60% fixed costs 0.001); the last 10% of angles carries most of the loss. A gentler schedule end was proposed as next; `dfthcsos-eight-bit` tested it and found it was not the problem.
* The model says `Q_total` drops from about 790 to 494 only where the inner QROAM block exponent steps down, so reaching 8 bits is the single largest step (4.05).
* Not a promotion candidate: best verified overall stays 489,890,973 (6.85).

## Decision

M1 reached. Own table is behind by bit width (29,640 vs 14,616 angle Toffolis, `Q_total` 789 vs 491) and by `lambda_eff` (62.6 vs 46.9, a further 1.33x). M2, the structured fit with the bilinear loader, was not started.

## Reproduce

The note gives no commands (scripts named: `scripts/run_fit.py`, `scripts/dfthcsos_post.py`, `scripts/dfthcsos_qat.py`).

## Links

PRs 72, 73; E019, E020; `docs/experiments/dfthcsos-structured.md`; `docs/experiments/dfthcsos-codesign.md`; next: 2026-11-13-dfthcsos-eight-bit.
