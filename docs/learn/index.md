# The learning track

This track teaches you enough quantum computing to work on the Verifiable Quantum Circuit
Compilation competition. You need Python and undergraduate engineering maths (complex numbers,
matrices). You do not need physics.

Every code block on these pages is run by the test suite, so the output you see is the output you get.
Blocks marked `no-run` are the only exception. Each page ends with a few exercises; the solutions are
folded away at the bottom.

## Reading order

1. [Qubits and gates](qubits-and-gates.md): amplitudes, gates as matrices, measurement, and a Bell state
   simulated in numpy.
2. [Reversible logic](reversible-logic.md): NOT, CNOT and Toffoli, scratch qubits, phase gates and
   phase kickback.
3. [Costs and measurement-based uncomputation](costs-and-mbuc.md): why Toffolis and qubit counts are what we minimise.
4. [Classical verification](classical-verification.md): why a classical computer can check these circuits.
5. One primer per benchmark: [invsqrt](primer-invsqrt.md), [dqi](primer-dqi.md), [dfthcsos](primer-dfthcsos.md).
6. [Hands-on kickmix](kickmix-hands-on.md): the instruction set, file formats, and a 4-bit adder you build and verify.

The [glossary](glossary.md) defines every term used on the pages, and the
[competition overview](../COMPETITION.md) says what is being scored.

## Running the snippets yourself

From the repository root:

```
make install
uv run python
```

Then paste a block, or run the whole check with `make test`.
