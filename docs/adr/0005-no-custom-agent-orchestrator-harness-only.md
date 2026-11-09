# ADR-0005: No custom agent orchestrator; invest in the verification harness only

- Status: Accepted
- Date: 2026-11-10
- Deciders: Jian (F4), Claude

## Context

F4 asked why an "agent harness" is part of this challenge. It is not a requirement. The competition
rewards a closed loop: generate a candidate circuit, check it with the verifier, read the cost, try
again. A coding agent (Claude Code) is the generator. What the loop needs is a cheap, trustworthy,
uniform way to run a candidate and compare it to previous ones, which is the `bench` CLI and ledger
(ADR-0001), not an orchestration framework.

## Decision

No LLM API orchestration, scheduler or multi-agent framework. Claude Code sessions (optionally one per
benchmark in its own git worktree) call `bench`. Conventions live in `CLAUDE.md`.

## Alternatives considered

| Option | Why not |
|--------|---------|
| API-driven autonomous search loop with budget caps | Adds spend and a system to maintain before the harness has proven the verifier loop works. Revisit only if the interactive loop is the bottleneck |

## Consequences

Cheaper and simpler; throughput is limited by human-attended sessions, mitigated by the harness
running long optimisation scripts unattended.
