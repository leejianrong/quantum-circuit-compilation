---
id: 2026-11-12-invsqrt-cost-drivers
date: 2026-11-12
title: "invsqrt: the host reference is 88% schoolbook multiplications, and qubits and Toffolis weigh equally in the score"
type: reading
benchmark: invsqrt
methods: [cost-breakdown, source-decode]
status: done
outcome: positive
prs: [35]
studies: [docs/experiments/invsqrt-cost-drivers.md]
backfilled: true
licence_touched: false
---

## Question

Where does the host's Newton-Raphson reference (260 qubits, cost 2,076,774) spend its cost under the verifier's
formula, and so what should our own generator attack?

## Setup

This entry was backfilled from the study note and git history on 2026-11-15. Static counts per `mark` block come from
`scripts/invsqrt_audit.py` and kickmix `operation_statistics()` / `num_qubits`. The public frontier (62 qubits,
1,393 static Toffoli-like gates, cost 94,599.6, ratio 21.95) is used only as a total. Commit and machine: not recorded.

## Results

### Quantitative

| Stage of the reference | Forward T | Reverse T | Share of 7,735 |
|---|---:|---:|---:|
| normalize | 120 | 110 | 3.0% |
| Horner (3 steps) | 1,071 | 1,071 | 27.7% |
| square `y0^2` | 442 | 442 | 11.4% |
| multiply_m | 1,043 | 1,043 | 27.0% |
| multiply_y0 | 867 | 867 | 22.4% |
| denormalize (CSWAP) | 300 | 300 | 7.8% |
| total | 3,874 | 3,861 | 100% |

260 qubits: `x` 22, `y1` 40, coefficients 68, `y0^2` 28, `z` 30, scratch 30, adder ancillas 29 [M]. Rotations
are about 3% of the reference (253 of 7,988 Toffoli-equivalents) but about 9% for the frontier (about 130 of 1,526) [M].

### Qualitative

* Score is `Q * C`, so a 10% cut in qubits equals a 10% cut in Toffolis. From reference to frontier qubits fell
  4.2x and Toffoli-equivalents 5.2x [M].
* Three Newton multiplications plus the Horner chain are 88% of the Toffolis, all schoolbook shift-and-add at about
  2w Toffolis per row. `multiply_m` multiplies a 28-bit square by all of `x_norm` although `M y0^2` is within
  2^-13 of 1, so most of the width is wasted [I].
* Executed Toffolis are averaged over shots, so work under a measurement condition costs the fraction of shots
  that run it; the frontier's 294 conditional blocks and 871 `HMR` show it leans on this [V].
* Uncompute is not free except for AND temporaries; designs that clear late stages by measurement beat mirrors [I].

## Decision

QCC-12 builds a parameterised generator and tests these levers one by one: narrow multiplications, phase the
narrowest register, lean carries, measurement-based clearing.

## Reproduce

`QCC_DATA=$PWD/data uv run python scripts/invsqrt_audit.py`

## Links

PR 35; `docs/experiments/invsqrt-cost-drivers.md`; next entry `2026-11-12-invsqrt-generator`.
