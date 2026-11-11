# Start here

This site has two jobs. It is the learning track for engineers who know Python but no quantum
computing, and it is the project documentation for our entry in the
[Verifiable Quantum Circuit Compilation](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation)
competition: shrink three kickmix circuits and have the official verifiers accept them.

## Reading order

1. [Competition overview](COMPETITION.md): what is being scored, the three benchmarks, the prizes.
2. [Qubits and gates](learn/qubits-and-gates.md) and [reversible logic](learn/reversible-logic.md):
   the quantum background, with numpy you can run.
3. [Costs and MBUC](learn/costs-and-mbuc.md) and
   [classical verification](learn/classical-verification.md): what the score counts and why a
   classical computer can check these circuits.
4. The benchmark primers: [invsqrt](learn/primer-invsqrt.md), [dqi](learn/primer-dqi.md),
   [dfthcsos](learn/primer-dfthcsos.md).
5. [Hands-on kickmix](learn/kickmix-hands-on.md): build a 4-bit adder and verify it.
6. [Glossary](learn/glossary.md) for any term you do not recognise.

If you already know quantum circuits, skip to step 3 or to the benchmark you care about. If you
only want to run something, jump to step 5.

## Project documents

- [Plan](PLAN.md), [slices](SLICES.md) and [open questions](QUESTIONS.md): what we are building and in what order.
- [Competition rules](COMPETITION_RULES.md) and [data provenance](PROVENANCE.md).
- Architecture decisions are in `docs/adr/` in the repository.

The code and these pages live at
[github.com/leejianrong/quantum-circuit-compilation](https://github.com/leejianrong/quantum-circuit-compilation).
Every code block in the learning track is run by the test suite.
