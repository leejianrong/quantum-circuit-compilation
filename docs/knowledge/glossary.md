# Project glossary

Terms we use for how the project works: the ledger, verification, the log book and the studies. The physics and
circuit terms (Toffoli, ancilla, MBUC, amplitude and so on) are in the [learning glossary](../learn/glossary.md).

| Term | Meaning |
|---|---|
| Backfilled entry | A [log](../log/index.md) entry written after the fact from a study note, git history and the ledgers. It says so under Setup and carries `backfilled: true`. |
| `best/` | The folder of circuits that `bench pack` submits. Only `bench promote` writes to it, and only with the owner's say-so. Never committed. |
| `brot` | Bits per angle word in the dfthcsos loaders; `J` is the number of word registers per circuit ([cost model](../log/entries/2026-11-12-dfthcsos-cost-model.md)). |
| Claim | A statement the work relies on, kept in the [claims register](claims.md) with a status and the log entry that is its evidence. |
| Correction entry | A log entry that says an earlier claim was wrong. The old entry is not rewritten; it gets a pointer to the correction. |
| `E_gap`, `Lambda`, `lambda_eff` | The dfthcsos accuracy numbers: `lambda_eff = sqrt(E_gap (2 Lambda - E_gap))` multiplies the cost, and `Lambda` and `E_gap` have floors the verifier enforces ([primer](../learn/primer-dfthcsos.md)). |
| Experiment id (`E001`...) | A record in `ledger/experiments.jsonl`: a hypothesis, the benchmark, the parent circuit and the outcome. Some study notes use ids that do not match the ledger; see [open questions](open-questions.md). |
| Gauge | A freedom in how something is represented that changes no result, so it can be chosen to make the circuit cheaper. |
| Kind | The ledger's label for a run: `full`, `screen`, `leaderboard` or `public-reference`. Only `full` runs by the official verifier can gate promotion. |
| Ledger | The append-only JSONL files in `ledger/`: verification runs (`results.jsonl`), experiments, promotions. Old lines are never rewritten. |
| Mirror and unwind | Erasing a stage's result by running the stage backwards (a mirror), or by a second pass with measurement and conditional fix-ups (an unwind). |
| Official verifier | The competition's own scorer. It is the oracle and the only gate; everything else is screening. |
| Promotion | Moving a verified circuit into `best/` with `bench promote` (dry-run first). Needs several salts with zero failures. |
| Public reference | A circuit from another participant that we verified ourselves. It is a measuring stick, not our work; its licence is in [PROVENANCE](../PROVENANCE.md). |
| QAT | Quantisation-aware training: progressively rounding a fitted dfthcsos table to a fixed number of bits. |
| Ratio | `baseline_cost / cost`; the benchmark score is the geometric mean of the three ratios. |
| Salt | A seed variation of the official verification. Promotion ranks on the worst salt, and one salt-dependent failure rejects a whole submission. |
| Screening | Quick runs that never gate anything: reduced shots (`--shots-divisor`) and the third-party `kickmix-engine`. Rows carry `kind=screen`. |
| Stage marks, stage ledger | Tags emitted while a circuit is built, so the Toffolis between two tags can be counted per stage ([stage ledgers](../log/entries/2026-11-15-dqi-stage-ledgers.md)). |
| Static Toffoli count | The `toffolis` field in the ledger: gates counted in the file. It is not the official cost, which also counts T gates and rotations and is measured per salt. |
| Study | A long note in `docs/experiments/`. A log entry summarises one and links it. |
