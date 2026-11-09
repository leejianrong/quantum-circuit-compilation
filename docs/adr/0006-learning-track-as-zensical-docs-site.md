# ADR-0006: A learning track delivered as markdown plus a Zensical site, in the same repo

- Status: Accepted
- Date: 2026-11-10
- Deciders: Jian

## Context

The owner and likely future readers know Python and undergrad engineering maths (complex numbers) but
no quantum computing. Competition-specific knowledge (kickmix, MBUC, the three benchmarks' maths) is
not covered by generic quantum courses.

## Decision

Write the curriculum as plain markdown under `docs/learn/` (readable on GitHub), built as a Zensical
site (`dev-playbook` docs-as-code) and deployed through CI. Code snippets in it are real and run in CI.
Content scope: qubits and amplitudes, reversible logic and Toffoli, ancillas and uncomputation, phase
gates, MBUC, why classical simulation works for kickmix, Toffoli/qubit cost, the kickmix format and API,
then one primer each for invsqrt, DQI and dfthcsos. Exercises end with building and verifying a tiny
kickmix circuit.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Link to existing courses | None cover kickmix or this competition's targeted maths |
| Notebook-only | Harder to diff and review |

## Consequences

Costs writing time, but doubles as the "documentation" requirement for prizes and removes the
knowledge bottleneck for Track A. Runs in parallel to Track A.
