# Assumptions

Defaults we took without proof. Each one is a place a wrong guess could hide. The decided questions are in the
[questions register](../QUESTIONS.md); this page lists only what is assumed.

| Assumption | Where it came from | What would show it wrong |
|---|---|---|
| All three benchmarks must be in every submission (the metric needs them) | register Q9, [ADR-0003](../adr/0003-hybrid-strategy-ratcheted-valid-submissions.md) | the rules or the first submission say otherwise |
| kickmix can run locally, through the pip wheel; the competition `kickmix.so` runs only on Kaggle on the older host | register Q10, `AGENTS.md` | a verify that differs between the wheel and the official verifier on the same circuit (the official verifier is the gate, so a difference would show up there) |
| A submission is a file upload | register Q12 | the first submission |
| The ledger is JSONL, append-only | register Q14 | a need for queries the format cannot support |
| No LLM API spend | register Q15, [ADR-0005](../adr/0005-no-custom-agent-orchestrator-harness-only.md) | a decision to pay for compute or inference |
| Optimised DQI circuits are smaller than the baseline | register Q16 | resolved by our own circuits (the baseline is beaten by a wide margin) |
| Python tooling is uv, CPython 3.12 or newer, pytest, ruff | register Q17 | a dependency that needs another version (3.14 has worked) |
| `R(eps)` in the DQI cost is close to 1.2 | measured at 1.19 to 1.22 on the plotted circuits | a circuit with a different synthesis error budget |

Items tagged **[I]** (inferred) or **[G]** (guess) in the studies are not results; the
[claims register](claims.md) marks the ones that matter as unverified.
