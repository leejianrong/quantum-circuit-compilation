---
id: 2026-11-13-invsqrt-stage2
date: 2026-11-13
title: "invsqrt stage 2: the 62-qubit frontier uses our mathematics, and its advantage is lookup, normalisation, conditional execution and qubit count"
type: reading
benchmark: invsqrt
methods: [source-decode, cost-breakdown, uncompute]
status: done
outcome: negative
prs: [94, 96]
studies: [docs/experiments/invsqrt-stage2.md]
backfilled: true
licence_touched: true
---

## Question

What is the public 62-qubit invsqrt circuit (cost 94,599.6) made of, stage by stage, and which of its
mechanisms can we implement to get past our best (E023, 93 qubits, 168,237.4, ratio 12.34)?

## Setup

This entry was backfilled from the study note and git history on 2026-11-15. ADR-0009 stage 2. The circuit was dumped to text with kickmix into a scratch
directory (nothing under `public/` touched or committed); then gates were counted per stage and qubit lifetime,
prefixes were simulated on chosen inputs, and algebraic degrees were computed. No gate list, table or constant is
reproduced here. Commit and machine: not recorded. The follow-up costing is dated 2026-11-13 and built no circuit.

## Results

### Quantitative

| Stage | Frontier static (executed) | Ours (E023) |
|---|---:|---:|
| normalise | 67 | 105 |
| lookup | 166 | 254 |
| lookup erase | 0 | 25 |
| coarse phase | 82 (76) | 107 |
| arithmetic and fine phase | 959 (about 750) | 908 |
| un-normalise | 118 (74) | 101 (90) |
| total | 1,393 (1,234) | 1,498 (1,487) |

Peak 62 qubits = 22 `x` + 40. Conditional execution removes 155 Toffolis (ours 11) [M]. Blocked Reed-Muller
lookup costs 169 Toffolis at 37 outputs but needs 57 extra qubits, about 1,080 Toffoli-equivalents against a saving of 43 to 70 [I].

### Qualitative

* The frontier uses the same mathematics: coarse plus fine word, degree-2 piecewise polynomial, 256 entries,
  error about 2^-24.4 (ours 2^-24.16). The gap is engineering, not approximation [M].
* Its arithmetic stage is not cheaper than ours (959 against 908), and its table is generic (algebraic degree 7 to 8),
  not co-designed to low degree. The research-note idea that it was co-designed is refuted [M].
* The advantage is lookup (-113), normalisation (-38), coarse phase (-25), conditional execution (-150) and 33% fewer qubits [M].
* Mechanisms understood: lookup by CX-and-AND networks, thermometer-chain normalisation, one working qubit for all
  rotations, conditional blocks as erased-AND fix-ups. Reading was partial: the post-fine arithmetic roles were not reconstructed [I].
* This note says the frontier has "no mirror of the Horner stage"; that reading was later refuted in `2026-11-13-invsqrt-onepass` (it is a forward pass plus an unwind).
* Costing the levers against our generator: conditional execution gains 0 in our layout, thermometer normalisation 7 of 40 hoped,
  blocked Reed-Muller lookup is negative. Conclusion: dead end as a patch of the Horner generator.

## Decision

No generator variant written; stage-2 milestones in `bench exp` not opened. The frontier needs a rebuilt architecture.

## Reproduce

Scripts were in the agent scratchpad and are not committed. The note describes: dump with `km.Circuit.from_file(...).to_file(out, format='kmx')`;
prefix simulation with `km.Simulator`, `write_across_shots`, `do`, `read_across_shots`, `read_shot_phase`; degree by Moebius transform.

## Links

PRs 94, 96; `docs/experiments/invsqrt-stage2.md`; `docs/PROVENANCE.md`.

> Corrected in part by [2026-11-13-invsqrt-onepass](2026-11-13-invsqrt-onepass.md): the frontier does have a Horner unwind, and about 10 scratch qubits, not a Reed-Muller layout with 57 extra.
