---
id: 2026-11-12-invsqrt-bitserial
date: 2026-11-12
title: "invsqrt 121 qubits, ratio 8.40: serial and split phasing do not pay alone, the centered remainder does"
type: experiment
benchmark: invsqrt
methods: [generator, qubit-reduction, phase-adder]
status: done
outcome: positive
prs: [54, 57]
experiments: [E012, E013, E014, E015, E016]
studies: [docs/experiments/invsqrt-bitserial.md]
backfilled: true
licence_touched: true
---

## Question

Can two structural observations about the public 62-qubit circuit (phase the value one bit at a time through a
single working qubit; phase a coarse word and a fine word separately) close the gap from our 136-qubit
generator (cost 296,738.6, ratio 7.00) towards 94,599.6 (ratio 21.95)?

## Setup

This entry was backfilled from the study note and git history on 2026-11-15. The two observations come from an aggregate-only look at the public
circuit logged in `docs/PROVENANCE.md`; both are implemented fresh in `src/invsqrt_gen/split.py`, with no gate list,
table or constant taken from a public circuit. Builds are parameterised `--a 7 --frac f0,f1,f2 --guard g`, plus
`--centered --polish` from the third row. Screens run 1/20 of the shots on one salt and never gate. Commit,
machine and salts of the screens: not recorded. Held fixed: the Horner architecture and the verifier cost model.

## Results

### Quantitative

| Build (experiment) | Qubits | Toffolis | Predicted cost | Verifier |
|---|---:|---:|---:|---|
| Baseline generator 30,20,11 g4 (E007) | 136 | 1,949 | 297,058 | 296,738.6, 5 salts |
| Complement split (E012) | 129 | 1,986 | 297,442 | screen 296,058 |
| Centered, serial coarse phase, 29,19,10 g3 (E013) | 123 | 1,785 | 259,552 | screen 259,212 |
| Centered, barrel, polished, 29,19,10 g3 (E014) | 123 | 1,752 | 254,380 | screen 254,380 |
| Centered, 28,19,10 g2 (E015) | 122 | 1,716 | 250,038 | 250,037.98, 2 salts |
| Centered, 28,19,9 g2 (E016) | 121 | 1,710 | 247,262 | 247,262.49, 5 of 5 salts, identical cost |

Final ratio 8.40, 2.6x short of the frontier. `predict.py` reproduces 247,262.4885, 250,037.98 and 254,379.6 to
every printed digit once only the inputs the verifier runs (2,350,089 of 4,194,304) are counted [M].

### Qualitative

* Split phase is neutral (E012): 7 qubits saved are repaid by 37 Toffolis, 11 rotations and a second shifter.
  The two words overlap in 12 positions, so those are rotated twice [M].
* Serial phasing loses 1.6% (E013): 33 more Toffolis than the barrel, and the headroom it saves is not at the
  qubit peak. It would only pay if the word were produced bit by bit and never stored [M].
* What paid was a different idea they led to: the centered remainder (7 Booth digits, one bit narrower products,
  no borrow in `V_0`). The step-0 product is 16% cheaper [M].
* The 2^-24 gate is the binding constraint: (28,19,9) is the narrowest set that passes, `wy = 26` is a hard
  floor, and 0.8% per extra qubit means a perfect fit would gain only about 1.5% [M].
* Eight levers costed on paper (phase gradient register, operand-less rows, split carry chain, reload `V_2`,
  deferred carries, radix-8, degree 3, rounding) all came out wash or loss [I]. The prediction fix also
  corrected a 0.6% over-estimate in `predict.py`.
* The frontier has about 40 qubits above `x` against our 99 and only 205 controlled swaps; the next lever is
  to remove the stored phased word and barrel shifters together [I].

## Decision

Nothing touches `best/`. Next: a phase adder that streams the last accumulation (tried in
`2026-11-12-invsqrt-phase-adder`).

## Reproduce

The note gives the parameter columns (`--a 7 --frac 28,19,9 --guard 2 --centered --polish`) but no full command
for this study; the generator CLI is in `docs/experiments/invsqrt-generator.md`.

## Links

PRs 54, 57; E012 to E016 (E007 is the baseline row); `docs/experiments/invsqrt-bitserial.md`.
