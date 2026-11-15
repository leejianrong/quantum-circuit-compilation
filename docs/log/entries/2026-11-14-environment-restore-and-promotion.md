---
id: 2026-11-14-environment-restore-and-promotion
date: 2026-11-14
title: "New machine restored; own DQI fixed.kmb promoted into best/ (65.8x); public invsqrt and dfthcsos re-verified"
type: run
benchmark: infra
methods: [environment, verify, promotion]
status: done
outcome: positive
commit: bfd9e43
prs: []
rows: [c6519219, c48c4e7d, 37d8047d]
studies: [docs/HANDOFF.md]
backfilled: true
licence_touched: true
---

## Question

Can the project be rebuilt from git and the recorded sources on a second machine, and do the circuits in
`best/` still verify there?

## Setup

Second machine (WSL2, RTX 3080 Ti, 20 cores, 31 GB RAM) following `docs/HANDOFF.md`, "First hour on a
new machine": `make install`, `make fetch-data`, `scripts/fetch_public.sh`. Official verifier, full shots.
Reconstructed from the ledger rows and `docs/HANDOFF.md` after the fact; the commands were not logged
as a single session. Third-party public circuits were fetched into `public/` (not committed).

## Results

### Quantitative

| Run | Circuit | Salts | Result | Ratio |
|---|---|---:|---|---:|
| invsqrt, public 62-qubit | `c6519219` | 3 | PASS, 94,600 | 21.95 [M] |
| dfthcsos, public frontier submission | `c48c4e7d` | 3 | PASS, 299,614,422 | 11.20 [M] |
| dqi, own `fixed.kmb` | `37d8047d` | 10 | promoted into `best/` | 65.77 [M] |

### Qualitative

* `make check` passed on CPython 3.14 although `requires-python` is `>=3.12`.
* With torch installed, the pre-push hook runs the torch parity test for the first time and the CUDA
  initialisation segfaults (torch 2.15+cu132, WSL2), so pushes use `CUDA_VISIBLE_DEVICES=`.
* The competition's `kickmix.so` still needs a newer libstdc++ than the host has; the pip wheel is used.
* `bench kaggle fetch` of `qcc-dqi-gen` is 346 MB and holds `fixed.kmb` only, not `rs.kmb` or `thiele.kmb`.

## Decision

Keep verifying on this machine, one heavy verify at a time. The DQI promotion is the owner's decision
and was made (`ledger/promotions.jsonl`, 2026-11-14T11:56Z).

## Reproduce

```
make install && make hooks && make check
make fetch-data && bash scripts/fetch_public.sh
QCC_DATA=$PWD/data uv run bench verify invsqrt <circuit> --salts 3
uv run bench promote dqi <fixed.kmb> --dry-run
```

## Links

`docs/HANDOFF.md`, `docs/PROVENANCE.md`, `ledger/promotions.jsonl`, `ledger/results.jsonl` rows above.
