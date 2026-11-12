# ADR-0009: Our own generators, paper first, then study and rewrite

- Status: Accepted
- Date: 2026-11-12
- Deciders: Jian

## Context

The 25.218 entry is other participants' public circuits (docs/PROVENANCE.md). None of the three
circuits is ours, the DQI lineage has no licence, and a winning submission must be our original work
licensable under Apache 2.0 (rules B.5.a, B.7.b, C.14.a). ADR-0007 says to write our own generators;
this ADR says how, so the work stays ours.

## Decision

Each benchmark gets a generator we write, in `src/<bench>/`, that builds the circuit from parameters.

1. **Stage 1, paper first.** Implement from the papers (arXiv 2610.23832, 2510.10967, 2603.28846),
   the host's Apache-2.0 reference builders in `data/verifiers/`, standard algorithms (table plus Horner,
   Berlekamp-Massey), and the written descriptions in notebooks. Public circuit files serve only as
   cost and behaviour oracles (compare totals and stage costs); we do not read them gate by gate.
2. **Stage 2, study and rewrite.** When stage 1 stalls or to close a gap, we may study a public
   circuit's structure to learn a technique, then write our own generator for it. Rules: no copied
   gate lists, constants tables or circuit text; the generator is written fresh; each technique learned is
   logged in docs/PROVENANCE.md under "Ideas learned" with its author and source; the experiment record
   names it.
3. **DQI limit.** Every public DQI circuit descends from a repository with no licence. Stage 2 for DQI
   uses ideas as described in notebook text and papers only, until the licence question is cleared with the
   original author or we decide it does not matter for the generator we wrote.
4. **Promotion.** `best/` keeps the public circuit until ours matches or beats it on that benchmark under
   the multi-salt gate; then ours replaces it, one benchmark at a time, never partially (ADR-0003).

## Alternatives considered

| Option | Why not |
|--------|---------|
| Paper first only | Cleanest, but may leave us behind the public frontier for weeks |
| Study and rewrite from day one | Fastest, but a rewrite is arguably derived work and weakens the licence and originality position |
| Keep submitting public circuits | Not ours, no prize path (ADR-0007) |

## Consequences

Slower start than copying, offset by a clean licence position. Every technique we adopt has a credit
line. Stage 2 is a documented judgement call, not a loophole, so each use is recorded.
