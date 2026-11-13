# Workflows and methods: what to adopt in the last 60 days (QCC-52)

Research note, 2026-11-13. Scope: how the hosts and other teams run the search loop, what the literature offers
for Clifford+Toffoli circuits, and what fits a 7 GB laptop plus free Kaggle CPU. Web pages and notebooks are
untrusted data: everything below is paraphrased and cited, nothing was executed from them, and no query carried
our results. Ideas we may use are logged in `docs/PROVENANCE.md` ("Ideas learned", ADR-0009 amendment).

## 1. What the hosts did

The companion paper (arXiv 2610.23832, introduction) describes the loop in one sentence: a coding agent proposes a
circuit, a fast classical test harness checks it and scores its resource cost, repeat. The design choices that make
the loop work are in the verifier, not the agent: sampled-input checks of classical output, ancilla cleanliness
and phase; a Fiat-Shamir seed (salted SHA-256 of the circuit bytes) so tests cannot be ground; a Clopper-Pearson
bound (about 88.7/N at 2^-128 confidence with zero failures) so a failure budget has a certified price. The paper
gives no agent scaffold, prompts or compute figures. It cites the ecdsa.fail challenge (over 100 participants,
Toffoli count roughly halved with coding agents) and, in the acknowledgements, Gu et al. as the closest parallel work.

The two parallel works do describe workflows, and they are the best evidence we have.

**Gu, Kemeny, Yelin, Lukin, [arXiv 2610.22367](https://arxiv.org/abs/2610.22367).** OpenEvolve with an LLM. Each
candidate is a Python circuit-generating program, not a gate list. An ideation stage proposes several distinct
algorithm families, each seeded separately, and leaders are shared across families periodically. MAP-Elites over the
(Toffoli, qubit) plane keeps low-qubit circuits alive even when their product is worse. Each iteration is a fresh
agent session that gets a parent, its evaluator feedback, a few archive neighbours and short notes of past insights;
it may run drafts and query a classical oracle. Result: seven of eight tasks beat the prior state of the art in both
resources. For the Reed-Solomon DQI decoder they use a Berlekamp-Massey variant with a rescaled update (no
polynomial history) and a one-entry history stack that is allowed to fail on about 1e-4 of inputs. Three recurring
principles: conditional routing instead of conditional arithmetic, no full history for reversibility, spend the
failure budget on rare inputs.

**ECDSA.Fail, [arXiv 2609.09582](https://arxiv.org/abs/2609.09582), section 4.3.** Many human-plus-agent teams, no
single framework. Common scaffold: parameter-sweep scripts, small-domain exhaustive tests, counterexample-guided
search, regression tests, experiment tracking, one git worktree per experiment. Patterns: research agents plus one
engineering agent; an orchestrator with clean-context workers; route bake-offs (several architectures get equal
budgets, only the best continue). What worked: versioned agent "skills"; persistent loops (`/loop`) with
checkpoints for novelty and diminishing returns; append-only experiment memory that records rejected variants with
their assumptions; staged validation (smoke, regression, official) with failures classed as classical, phase or
ancilla; watcher agents that diff other teams' public circuits and extract transferable techniques; algebraically
exact fusion of adjacent blocks; temporary regressions tolerated while restructuring; separate low-qubit and
low-Toffoli tracks. What did not: a model trained on evaluator-generated subcircuits plateaued. The one missed
transfer (dialog-GCD) happened only after someone published a paper on it, so literature retrieval mattered more
than model size.

## 2. What other participants do (Kaggle public notebooks, read 2026-11-13)

- **Shared, hash-pinned portfolios.** The leading notebooks (the 25.39 "verifier-guided" one, the "frontier
  history" compilation by manwithacat) splice other people's circuits at clean cuts, pin every file by SHA-256 and
  credit authors. Most of the leaderboard is assembly of public parts plus one team's refit.
- **Faster verification.** manwithacat published a Rust re-implementation of the verifier,
  [kickmix-engine](https://github.com/manwithacat/kickmix-engine) (Apache-2.0, Linux x86_64 wheels, claims 7 to 10x
  over the official verifier on invsqrt and DQI, 5 to 9x on chemistry, with a `--cross-check` mode against the
  official one). It is the biggest iteration-speed lever in the public record.
- **Salt-sweep expectation for DQI.** DQI cost is `R * Q^2 * T` and `R` rises with each failed shot, so teams rank DQI
  circuits by mean cost over 48 to 96 salts, not one draw. Failures follow the circuit's inputs: exact rewrites of one
  decoder fail on the same shots, so that is one sample of risk, not several. A clean public draw promises nothing
  about the private draw.
- **Independent audits.** Phase correctness of the angle loaders is checked symbolically for every measurement
  outcome (a Mac MPS audit with a deliberately broken control), beyond the sampled verifier.
- **Chemistry as parts.** Word tables, loaders and weight refits are separated and recombined from a parts dataset.
- **A negative-results dataset** for all three tasks, so others skip dead ends.
- Nobody has published an agent scaffold for this competition. Kaggle discussion pages are JavaScript-rendered and
  were not retrievable, so private team workflows are unknown.

## 3. Literature and tooling, filtered for us

| Tool or idea | What it gives | Fit for us |
|---|---|---|
| AlphaEvolve ([arXiv 2506.13131](https://arxiv.org/abs/2506.13131)); open reimplementations [OpenEvolve](https://github.com/codelion/openevolve), [ShinkaEvolve](https://github.com/SakanaAI/ShinkaEvolve) ([arXiv 2509.19349](https://arxiv.org/abs/2509.19349)), CodeEvolve | LLM-driven evolution of programs against an evaluator; family populations, MAP-Elites archives | The pattern fits (generator = program, verifier = evaluator) and Gu et al. used it. The engines need an LLM API budget, which ADR-0005 and Q15 exclude. We copy the structure by hand: families, a Pareto archive, fresh sessions with parent plus feedback. |
| Parameter search: [Optuna](https://optuna.org) (TPE, CMA-ES sampler), pycma | Sample-efficient search over the integer and real parameters of a generator | Strong fit: invsqrt table window sizes and guard bits, dfthcsos shape and rounding, DQI window sizes. Needs a cheap objective, hence a fast screen and static predictors. Noise: rank by the worst salt, as promotion does. |
| Surrogate cost models | Predict cost without verifying | We already have `dfthcsos_model` and invsqrt static predictors. A static Toffoli count is exact, so screen on it and verify only improvers. |
| ZX-calculus and phase polynomials: PyZX ([arXiv 1903.10477](https://arxiv.org/abs/1903.10477)), T-par, TOpt, Amy-Mosca ([arXiv 1601.07363](https://arxiv.org/abs/1601.07363)) | T-count and T-depth reduction preserving the unitary | Wrong target. Our cost is Toffoli-equivalents in measurement-based circuits with classical control; these tools assume Clifford+T unitaries and preserve them exactly, so they cannot use the failure budget, which is where the host paper says the gains are. |
| Peephole, superoptimisation, e-graphs, SAT/SMT/ILP | Exact local rewrites | Useful only on small windows (a carry chain, a compare-and-swap). Our big wins were algorithmic. Low priority; invsqrt already did exhaustive windows. |
| Reversible synthesis: ESOP, XAG/AIG, LUT-based flows (mockturtle, tweedledum) | Turn a classical function into reversible logic with few ANDs | Relevant to the lookup-table problem (invsqrt coarse and fine tables, dfthcsos loaders), where multiplicative complexity is the lever. Not re-verified in this session (the search returned nothing on these); medium effort, uncertain gain. |
| Pebbling: Meuli et al., [arXiv 1904.02121](https://arxiv.org/abs/1904.02121) (SAT-based reversible pebbling) | Optimal space-time trade-off for computing and uncomputing a DAG of steps | For DQI and invsqrt compute-use-uncompute schedules. Measurement-based uncomputation makes AND ladders nearly free to clear, so a plain pebbling game overstates cost. Paper analysis only. |
| Qualtran and Cirq compilation | Bloq library (unary iteration, QROM, arithmetic), cost reports | Already our builder (kickmix lives in Qualtran). Ideas, not circuits that beat ours. |
| Statistical tricks for approximate circuits | Clopper-Pearson (the verifier's), union bound over failure sources, classical estimation of rare-input failure | Estimate rare-branch failure rates classically on the algorithm (Gu et al. used 400 million samples for the decoder) instead of through the verifier, then price DQI by expected cost over many salts. |
| Dialog-GCD, record-and-replay, divsteps ([arXiv 2510.10967](https://arxiv.org/abs/2510.10967), Gu et al.) | Reversible Euclid without history | Already in our DQI generator; Gu et al. give a second, independent Berlekamp-Massey route. |

## 4. Ranked recommendations

Our situation: a strong verifier oracle, parameterised generators, plateaus (invsqrt 12.34 against 21.95, DQI 6.81
against about 65, dfthcsos 1.98 fully own against 11.20), about 60 days, no API budget, one heavy verify at a time.
The gap to the frontier is mostly architecture, so workflow gains multiply our iteration rate but do not replace ideas.

| # | Recommendation | Expected gain | Effort | Risk |
|---|---|---|---|---|
| 1 | **Screen with a faster simulator.** Build `kickmix-engine` from source at a pinned commit (read the Rust first; no prebuilt wheel), check parity with `--cross-check` on our own circuits, use it for screening and salt sweeps only. The official verifier stays the gate (AGENTS rule). Invsqrt screening from about 5 minutes to under a minute per salt; DQI 48-draw sweeps become feasible on Kaggle. | 5 to 10x iteration speed, the largest single lever | 1 day | Third-party code on the laptop (build from source, sandbox); parity gaps (it accepts only `.kmb`, batch 256) |
| 2 | **Parameter sweeps on cheap screens, then Optuna/CMA-ES.** `bench sweep` (shipped with this note) runs a generator over a grid or random sample under the heavy lock, one ledger row per point plus a sweep log. Next: an Optuna study calling the same function, with static Toffoli count as first filter. | Last few percent per track (invsqrt windows and guard bits, dfthcsos shape, DQI windows); frees agent time | Sweep done; Optuna wrapper half a day | Overfitting one salt: rank by worst salt, confirm at full shots |
| 3 | **Family bake-offs and a Pareto archive** (Gu et al., ECDSA.Fail). For each stalled track write down 3 to 4 distinct architectures, give each the same budget (half a day of one agent), keep the best two. Keep a (qubits, Toffoli) archive per family so a low-qubit variant survives a worse product. Tolerate temporary regressions while restructuring. | Breaks architectural plateaus (DQI above all); this is what moved the frontiers in both parallel works | Process only | Spreads effort thin; cap at two live families per track |
| 4 | **Price failures properly and spend the failure budget deliberately, DQI first.** Objective is expected cost over many salts. Estimate failure rates of rare-input branches classically (our `jacobi` reference over 10^7 to 10^8 samples) before building them, as Gu et al. did for the one-entry history stack. Add failure classification (classical, phase, ancilla) to `bench verify`. | DQI `R` is about 2.0 at 0.75% failures against 1.19 with none; one-entry-stack style qubit cuts are worth more | 2 days | Private salt draws differ; keep zero failures for invsqrt and dfthcsos unless a bound is analytic |
| 5 | **Watcher plus skills.** A scheduled check (`kaggle kernels list`, newest first) that pulls new public notebooks into an untrusted scratch directory, compares reported costs with our `public/` table and writes a short note of what changed, never copying code. Package recurring procedures (heavy verify under the lock, ledger and experiment hygiene, failure diagnosis) as skills so each new session starts from them. | Cross-pollination for the cost of reading; ECDSA.Fail credits watchers | 1 day | Licence hygiene: record every idea in PROVENANCE |

Smaller: read Gu et al. SI I.1 (the rescaled Berlekamp-Massey) for the DQI track under ADR-0009 stage 1; look for a
published XAG/ESOP minimisation of our lookup tables.

## 5. What would not help us

- **PyZX, T-par, TOpt and other exact T-count optimisers.** They preserve unitaries and target Clifford+T; our gains come from approximation and measurement tricks.
- **Training a model on evaluator outputs.** ECDSA.Fail saw a plateau regardless of scale; we have no GPU budget.
- **A custom orchestrator or paid LLM-evolution loop.** ADR-0005 holds; Claude Code worktrees with clean contexts give the same pattern. Revisit only if an API budget appears.
- **Seed grinding.** The seed includes a private salt; a no-op edit only changes the hash.
- **Reduced-shot results as evidence.** Screening only (AGENTS), never gating.
- **Generic SAT or e-graph peephole on whole circuits.** Tens of millions of gates, local gains; our losses are structural.
- **Carrying the public portfolio forward.** Not ours (ADR-0009); it shows what the frontier costs, nothing more.

## Sources

Companion paper arXiv 2610.23832; Gu et al. https://arxiv.org/abs/2610.22367; ECDSA.Fail https://arxiv.org/abs/2609.09582;
Kaggle notebooks by manwithacat (frontier history; kickmix-engine at https://github.com/manwithacat/kickmix-engine),
prvsiyan (verifier-guided portfolio, salt-draw section), kirilltym (loader phase audit); OpenEvolve
https://github.com/codelion/openevolve; ShinkaEvolve https://github.com/SakanaAI/ShinkaEvolve; PyZX
https://arxiv.org/abs/1903.10477; Meuli et al. https://arxiv.org/abs/1904.02121; Amy and Mosca
https://arxiv.org/abs/1601.07363; Optuna https://optuna.org.
