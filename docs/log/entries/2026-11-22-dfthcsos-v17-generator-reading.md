---
id: 2026-11-22-dfthcsos-v17-generator-reading
date: 2026-11-22
title: "v17 dfthcsos generator read: the public 8-bit table is a code-constrained, weight-refit table, and the field is tied at parts per million"
type: reading
benchmark: dfthcsos
methods: [source-study]
status: done
outcome: negative
commit: 80d4e00
prs: []
experiments: []
rows: [4c6e5963]
studies: [docs/experiments/dfthcsos-eight-bit.md, docs/experiments/dfthcsos-syed-decode.md]
backfilled: false
licence_touched: true
---

## Question

How does the public dfthcsos table reach 8-bit words inside the 0.02 error gate, so that our rounding work (QAT, 0.099 at 8 bits against the gate) can copy the method, and is there room above `best/` (294,762,513)? Static reading only; nothing was built or run.

## Setup

`public/syed3000__vqcc-own-circuit-portfolio-20261121/files/dfthcsos_generator/dfthcsos_generator/` (Apache-2.0 with NOTICE, untrusted data): README-level files (`COMPARISON.md`, `PROVENANCE.md`, `verification_summary.json`), `table_chain/README.md`, the two team briefs under `table_chain/research/` and the docstrings of the scripts in `chem_codes_20261113/codes_b3/scripts/`. 506 files, 40 MB.

## Results

### Quantitative

The package (`submission.npz` `07f81f5f`, "package48") scores 295,006,518.97: 14,718 Toffolis (T = 2 x 4,028 loader Toffolis per pass + 6,662), 427 qubits, lambda_eff 46.94128, Lambda 283.38 Ha, both errors at 19.999988 mHa [V]. It differs from the team's package38 by 28 word cells and is 0.083% worse than our `best/` entry (294,762,513, `4c6e5963`) [V, M]. Their briefs state a hard floor lambda_eff >= 46.786 for any accepted table at any shape, so the public table sits 0.33% above it [V, their derivation: K = E_upper - ecore + 113 beta_1 is fixed]; our `Lambda` of 490 to 560 is a different quantity from this lambda_eff and was never the whole story.

### Qualitative

The 8-bit words are not "rounded to 8 bits". They are constrained by parity codes and relations chosen to cut the loader cost: bit 0 of every word is a code, bit 7 xor bit 6 is a helper, and per (row, batch) the XOR of five words at bits 1 and 2 is fixed (`staged.py`, `impose_rel.py`; the cost of a code is cheap on late batches, 0 to +3 units, and dear on early ones, +28 to +37). Rounding is a staged re-rounding inside that code set (largest-impact words frozen first, small tuples completed by enumeration, L-BFGS-B on the free angles), followed by an exact weight refit that holds the one-body part fixed (`exact_refit.py`: scale to put E_gap on the floor, then minimise lambda subject to error_2 at the gate by an augmented Lagrangian). Their own plain 7-bit and plain 8-bit rounding attempts fail the same way ours did: realised noise 124 to 549 mHa^2 against a budget of about 200 to 240, and no variant (progressive, GNB, multi-pass, LLL, compensation vectors) closed it. A forum thread they cite, and their own nine failed architecture screens, put the 8 x 143 x 44 design at its limit: the public field is "crowded into ties a few parts per million wide".

## Decision

Our rounding plan (QCC-16: 8-bit words from a penalised fit, gate 0.02) is the route the public team closed by measurement; the one that works adds code constraints and a weight refit that we do not have, and what it reaches is the public table, which `best/` already holds (and slightly beats). Recommendation to the owner: park QCC-16 and QCC-69 for the submission, since neither can beat `best/` by more than parts per million with what is known, and keep the code-constrained rounding as learning-track material (this entry is the source). Not acted on without the owner's say-so; the board cards stay as they are.

## Reproduce

Read the files named under Setup.

## Links

QCC-16, QCC-69, [eight-bit](../../experiments/dfthcsos-eight-bit.md), [v17 refetch](2026-11-21-public-refetch-v17.md).
