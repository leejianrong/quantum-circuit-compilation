---
id: 2026-11-28-best-cheap-cuts-negative
date: 2026-11-28
title: "No cheap cuts in the public invsqrt and DQI circuits in best/: no constant-control Toffolis, no cancelling pairs, qubit peak is a plateau"
type: experiment
benchmark: infra
methods: [constant-propagation, peephole, firing-counts]
status: done
outcome: negative
commit: 2769762
prs: []
experiments: []
rows: [bb676b95, 141f02ac]
studies: []
corrects: []
backfilled: false
licence_touched: true
---

## Question

Can `best/invsqrt` (`bb676b95`, 37 qubits) or `best/dqi` (`141f02ac`, 900 qubits) be made cheaper by deleting gates that do nothing, with no change of design? The classes tried: Toffoli-class gates with a control that is constant when the gate runs, gates on a branch that never runs, identical self-inverse pairs with nothing between them, adjacent rotations on one qubit, and a lower qubit peak.

## Setup

Read-only analysis of the circuits as text (`Circuit.to_file`), nothing verified or promoted. invsqrt: the whole domain (3,133,452 inputs, one random HMR outcome each), recording the control values at every CCX and CCZ when it executes (`scripts/invsqrt_control_values.py`); the sampled width profile with 4,096 inputs. DQI: static abstract interpretation with qubits and bits in {0, 1, unknown} over all 69.8M instructions (`scripts/kmx_constprop.py`; input qubits are the 840 in the `S` registers, the rest start at 0) and a pair search (`scripts/kmx_cancel_pairs.py`). DQI was not simulated, per ADR-0002.

## Results

### Quantitative

| Check | invsqrt `bb676b95` [M] | DQI `141f02ac` [M] |
|---|---|---|
| CCX/CCZ with a control constant 0 or 1, or equal controls, when executed | 0 of 1,511 | 0 (static) |
| Toffoli-class gates on a branch that never runs | 2 (CCZ, expected cost 0 already) | 22 (static, condition bit known 0) |
| identical CCX/CCZ pairs with nothing between | 0 | 0 |
| cancelling Clifford pairs (CX, X, Z, SWAP) | 145 | 66,547 (cost nothing) |
| non-Clifford `Z_POW` mergeable | 0 of 43 | not present |
| peak width | 37, reached in 17,159 of 56,247 steps (30%), 36 in another 25% | 900 from module M2 to the end, 840 inputs in the first block |

### Qualitative

The 166 never-firing Toffolis of the public notebook are gone from `bb676b95` and nothing of that kind remains in either circuit. Both peaks are plateaus, so a one-qubit cut means redesigning stages (2.3% on invsqrt, 0.23% on DQI), not trimming. The unknown-valued domain is crude (a flipped qubit under a condition becomes unknown); a symbolic domain over the condition bits could find more, but a compiler that already folded constants this far is unlikely to leave much.

## Decision

Task closed as a negative result. The scripts stay for use on new public files. Gains on DQI must come from the architecture (the 17% T gap to `fixed4`), not from this pass.

## Reproduce

`uv run bench index --exact best/invsqrt/invsqrt.kmb`, then `uv run python scripts/invsqrt_control_values.py 0 out.json`; for DQI write the text with `kickmix.Circuit.from_file(...).to_file(...)` and run `python scripts/kmx_constprop.py TEXT out.json` and `python scripts/kmx_cancel_pairs.py TEXT out.json` (about 3 minutes each).

## Links

QCC-61, QCC-63, [public refetch](2026-11-28-public-refetch-1126-checked.md), [explorer](2026-11-25-explorer-dqi-dfthcsos.md).
