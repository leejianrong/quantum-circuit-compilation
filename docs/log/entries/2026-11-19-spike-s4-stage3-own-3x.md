---
id: 2026-11-19-spike-s4-stage3-own-3x
date: 2026-11-19
title: "S4 stage 3: our own dfthcsos goes from 2.50x to 3.28x (verified); 8 and 10 bits still fail the gate"
type: run
benchmark: dfthcsos
methods: [qat, rounding, verify]
status: done
outcome: positive
commit: d8f5d80
prs: []
experiments: []
rows: [09324acd]
studies: [docs/experiments/spike-s4-lambda.md]
backfilled: false
licence_touched: false
---

## Question

Do the `Lambda`-penalised words survive rounding to 8 to 11 bits inside the `error_2` gate, and what does the full circuit score?

## Setup

`mu` = 3e-5 fit (stage 2). `dfthcsos_qat.py --half` at 8, 10 and 11 bits; `dfthcsos_post.py --brot 11 --half --loader anf
--rotate-restarts 4 --joint-rotate 2`; official verifier, 3 salts.

## Results

### Quantitative

All-rounded `error_2`: 8 bits 0.0994, 10 bits 0.0299, 11 bits 0.01883 [M]. 11-bit circuit: `Lambda` 284.9, `lambda_eff` 48.09,
10,875 Toffolis, 120 qubits; official cost 1,022,615,598.11, ratio 3.28, 0 failures in 3 salts (row `09324acd`) [M], equal to the
model prediction. Own best before: 2.50 (E040).

### Qualitative

The penalty fixes `Lambda`, not the bit requirement: 8 and 10 bits fail as for every earlier fit. `lambda_eff` is within 2.4% of the
public table, so the remaining 3.5x gap is loader and width (`T_total * Q_total`), which needs 8-bit words and the public loader structure.

## Decision

Keep 3.28 as our own best (not promoted: the public 11.38x is in `best/`). Next on dfthcsos: an 8-bit rounding method (the public
table's polish) and the loader port (QCC-69).

## Reproduce

See `docs/experiments/spike-s4-lambda.md`, stage 3.

## Links

QCC-62, QCC-69, ledger row `09324acd`.
