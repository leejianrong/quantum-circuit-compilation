---
id: 2026-11-13-dfthcsos-stage2
date: 2026-11-13
title: "With public ideas allowed, our own ANF loader lifts an 11-bit own table to ratio 2.50, but fit basin (Lambda) and 8-bit rounding still block the frontier"
type: experiment
benchmark: dfthcsos
methods: [loader, fit, qat, source-decode]
status: done
outcome: positive
prs: [95, 103, 109, 111, 113, 135, 141, 146, 148, 166, 169, 173, 175, 185]
experiments: [E040]
rows: [b6b6dce0]
studies: [docs/experiments/dfthcsos-stage2.md]
corrects: [2026-11-12-dfthcsos-loader, 2026-11-12-dfthcsos-codesign]
backfilled: true
licence_touched: true
---

## Question

After ADR-0009's amendment of 2026-11-13 allowed study of public work, which public ideas close the gap between our fully-own ratio 1.98 and the public frontier (about 11.2), and how much of each can we build ourselves?

## Setup

This entry was backfilled from the study note and git history on 2026-11-15. The note grew over 14 PRs and about two days; this entry summarises its sections. Everything implemented is ours; sources read: a public notebook text,
public loader write-ups, the `andigu/uncompute chemistry-fe2s2` README (Apache-2.0, commit 64b5a13a), the reference set's decoded vectors (aggregate statistics) and syed3000's source archive (Apache-2.0, read from `~/qcc-circuits/syed_src/`).
Fits on Kaggle CPU kernels (`qcc-dfthcsos-fit`, `-fit-b`, `-fit-c`, fit-e and others) fetched to `~/qcc-fits/kaggle/`; QAT and post-processing on the laptop. E040 is the verifier run at 3 salts. Commit: not recorded.

## Results

### Quantitative

| Item | Value |
|---|---|
| compact seed from public description vs random start, 700 it | `error_2` 0.176 vs 0.083 (worse) |
| fit (8,176,56), 9,000 it / fit-b (8,143,44), 30,000 it | 0.01682 / 0.02274 (fit-b fails even continuously) |
| QAT of the 0.01682 table, all rounded | 11 bit 0.02259, 10 bit 0.03422 (fail) |
| ANF loader, 8 bit, lb 6, J 5 (own table) | 125 qubits, 7,257 Toffolis per pass |
| per-plane vs shared GF(2) search, per circuit | about 255 vs 253 Toffolis (under 1% gain) |
| fit-c continuous / 11-bit half-circle QAT / post | 0.01471 / 0.01906 / `error_2` 0.01901, `lambda_eff` 63.14 |
| E040 verifier | PASS 3/3, cost 1,342,757,005, ratio 2.50 (own unary table: 1.98) |
| fit-e: continuous / 11 bit / 10 bit / 8 bit QAT | 0.01158 / 0.01749 / 0.02703 / 0.08558 |
| `Lambda` across own fits (brot 16) | 488 to 557 vs public 282.8 |

E040: model prediction equal to the verifier cost to the digit [M]. Cost-model predictions for unbuilt options: 8-bit lb 6 J 5 ratio 5.3 (7.1 at lambda_eff 46.9); fit-e at 11 bits 2.43 (not verified) [model].

### Qualitative

Sections of the note: finding that matters; compact seed (negative); Kaggle fits and QAT; public loader by dynamic analysis; GF(2) decomposition search; ANF line basis loader; shared-product loader and a correction; the fe2s2 study; reverse engineering syed3000's set;
the basin question; E040; two-stage fit; matroid-parity planner; fit-e QAT; `Lambda` across fits.

* Public notebook text says frontier tables come from a seed built from the target alone plus a very long fit (60k-iteration rounds, 33-stage rounding). Our compact seed from that description was worse than a random start [M]; the long fit is mostly compute.
* Qubit finding: one-hot lines leave room for J = 1 at 8 bits. The public loader gets J = 5 because its lines are algebraic-normal-form monomials of the selection bits, where only products of degree 2 or more take a qubit. Our `anf.py` does that [M, exact on all addresses].
* The flip-graph GF(2) tensor search gained under 1%, and rank is the wrong objective once two terms share a Toffoli; the planted-rank test was not recovered [M].
* CORRECTION of 2026-11-12-dfthcsos-loader and 2026-11-12-dfthcsos-codesign: they read the public circuits as a table rounded into a low-rank code (rank-5 quadratic form per bit, plane rank about 10). Direct inspection shows each plane has full centered rank 15 at lb 4,
  all flattenings are full rank, and a capacity argument (a code of 214 terms constrains about a third of all table bits) makes a rounded-into-code table implausible. Now believed [I, not verified by decomposing a table]: an essentially arbitrary 8-bit table loaded by a good GF(2) tensor decomposition.
* Half-circle angles (bit brot-1 equals bit brot-2, top plane one CNOT) were taken from public write-ups and implemented. Two bugs found: an angle that rounds to exactly +pi/2 is off the grid and over 0.6% of words took `error_2` from 0.0186 to 0.0276; fixed by using -pi/2 with a carried sign.
* From syed3000's archive: Toffoli pairs `(l1+h1)(l2+h2)` fanned out by CX, 212 products per circuit, chosen by a matroid-parity formulation. The note recorded the 8th plane "helper" as `bit7 xor bit6`, "almost always 0" and a cheap monomial [V, as read then]. This is wrong; see 2026-11-15-dfthcsos-syed-decode (density 25%, a fixed low monomial in all batches).
* Our matroid-parity planner paired 262 products against 280 per-plane with no cuts; the random cut search found none, so the 25% angle saving (8% of `T_total`) stays open. Counting bound: at least 188 products for 1,220 addresses (public plan 212).
* Structured starts (sparse, centered) are 15 to 20% ahead at equal iterations but ended behind the dense fit (0.0238, 0.0262, 0.0260 vs 0.0147); the two-stage fixed-support fit is worse (0.112 vs 0.065). Locality is a property of the optimum, not a pattern to impose.
* Lower `error_2` bought a larger `lambda_eff` (fit-e); `Lambda` is worth 35% of `lambda_eff` and `E_gap` 2%. The gap at 11 bits is mostly a different basin (about 1.7x lower `Lambda`). The 8-bit wall is the rounding, not the continuous fit: a 22% better fit left it unchanged.

## Decision

Next for ratio 3 and beyond: the same pipeline at 8 bits (model 5.3), needing a continuous fit near 0.012 and a rounding polish. Open question left for the owner: a GPU run with a `Lambda` penalty from the start (`scripts/run_fit_gpu.py` ready, weekly Kaggle GPU quota exhausted at the time).

## Reproduce

The note gives no single command; scripts named: `scripts/run_fit.py` (`--init compact`, `--init-from`), `scripts/dfthcsos_qat.py --half --brot 11`, `scripts/dfthcsos_post.py --half --loader anf`, `scripts/run_fit_gpu.py`. E040 outputs: `~/qcc-fits/own/qat11_half_fitc/`, circuits `~/qcc-circuits/own_dfthcsos_11bit_anf/`.

## Links

PRs 95, 103, 109, 111, 113, 135, 141, 146, 148, 166, 169, 173, 175, 185; E040; `docs/experiments/dfthcsos-stage2.md`; `docs/research/dfthcsos.md`; `docs/PROVENANCE.md`.

> Corrected in part by [2026-11-15-dfthcsos-syed-decode](2026-11-15-dfthcsos-syed-decode.md): the helper plane is a fixed low monomial in all batches (density 25 percent), not almost always 0.
