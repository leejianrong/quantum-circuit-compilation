# ADR-0007: Start from public circuits, then spend effort where others have not

- Status: Accepted (supersedes the ordering in ADR-0003; the promotion rules in ADR-0001 and the never-partial rule in ADR-0003 stand)
- Date: 2026-11-10
- Deciders: Jian

## Context

The baseline scores 1.0. Public notebooks (2026-11-09) report about 25.15 on the leaderboard, with
per-benchmark ratios of roughly 22x (invsqrt), 65x (dqi) and 11x (dfthcsos). These come from earlier
competitors' circuits, shared publicly under mixed or unstated licences. The rules allow sharing and
reuse among participants (docs/COMPETITION_RULES.md, C.5.d) but require our own work to be original
and any winning submission to be licensable under Apache 2.0 (C.14.a, B.5.a, B.7.b).

Public findings also show where headroom is thin and where it is not. invsqrt is reported to be near
its optimum (62 qubits, about 1.5% left per qubit). Reported open leads: dfthcsos at 7-bit angle words
(a cost-model cliff worth about 2x that nobody has made pass the accuracy gates), the DQI Forney sweep
(about 56% of Toffolis) and Berlekamp-Massey pass (about 25%), and DQI qubit count (counted twice in
the cost). These are unverified claims from notebooks; our first job is to check them.

## Decision

1. Day-one target: a verified submission built from the best public circuits, to score about 25.
   Every circuit used is logged in `docs/PROVENANCE.md` (author, source, licence as stated, sha256,
   per-benchmark cost, date fetched). Nothing is used without a provenance row.
2. We do not copy blindly. For each public design we write our own parameterised generator where
   that is feasible and credit the idea. Verbatim use of someone else's circuit file is a stopgap
   that must be replaced, or have its licence confirmed compatible with Apache 2.0, before we pick
   Final Submissions.
3. New effort goes to directions with evidence of headroom, ordered by expected gain per effort:
   dfthcsos (lowest current ratio, open 7-bit cliff), then DQI (largest cost, most levers),
   then invsqrt (reproduce and audit, expect small gains).
4. Public circuits are fetched by script (Kaggle datasets) and hashed. They are committed to the
   repo only if their licence permits; otherwise `best/` holds hashes and fetch instructions.
5. Post a forum link when we publish the repo or notebook (rules C.5.d).

## Alternatives considered

| Option | Why not |
|--------|---------|
| Stay on the baseline path (ADR-0003 as written) | Leaves us at about 1.0 against a field at about 25 for no gain |
| Submit public circuits unchanged to the end | Not competitive, and licence/originality risk for any prize |
| Reimplement everything before submitting | Delays a scored entry past the 11/20 milestone for no benefit |

## Consequences

Fast entry to the leaderboard. We inherit the failure modes of other people's circuits (for example
DQI circuits that pass at the default salt but fail under another), so ADR-0001's multi-salt promotion
gate becomes more important, not less. Prize eligibility depends on licence hygiene, which the
provenance log makes auditable. Our edge now has to come from verification discipline and from the
unclaimed directions, not from a head start.
