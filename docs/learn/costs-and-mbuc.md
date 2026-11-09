# Costs and measurement-based uncomputation

The score in this competition is a cost, so the first question is what the cost counts. This page
explains the two quantities every benchmark charges for (Toffoli gates and logical qubits), then
shows the one trick that most of the cheap circuits lean on: measurement-based uncomputation (MBUC),
which lets you clean up a scratch qubit without paying a second Toffoli.

You will want [qubits and gates](qubits-and-gates.md) and [reversible logic](reversible-logic.md)
first. New terms are in the [glossary](glossary.md).

## What the cost counts

A quantum computer big enough to run these algorithms has to be error-corrected. Every logical
operation is built out of many physical operations, and the operations differ a lot in price.
Flipping a bit (NOT), controlled-NOT (CNOT) and the sign-flip gates Z and CZ are cheap. The
Toffoli gate (flip a target bit if two control bits are both 1) is not: it needs a non-Clifford
resource, prepared in dedicated "magic state" factories, and it dominates both runtime and machine
size. That is the standard picture in the fault-tolerance literature. The verifiers here do not
simulate any of it, they just price gates:

- A Toffoli-like gate (`CCX`, `CCZ`, `CSWAP`) costs 1.
- A `Z_POW` rotation at a Clifford angle is free, at a T angle costs 1 T gate, and at any other
  angle costs `0.56 log2(1/eps) + 5.3` T gates for synthesis error `eps`.
- Four T gates are priced as one Toffoli, so `C = Toffolis + T/4` (invsqrt verifier source).
- `Q` is the circuit's logical qubit count, `circuit.num_qubits`. Scratch qubits that are freed get
  reused, so careful allocation keeps it down.

Toffoli count `T` sets how long the machine runs. Qubit count `Q` sets how big it must be. A single
number needs a combination, and each benchmark picks its own:

| Benchmark | Score | Source |
|---|---|---|
| invsqrt | `Q * C` | `verify_submission_invsqrt.py` |
| dqi | `R(eps) * Q^2 * T` | `verify_submission_dqi.py` |
| dfthcsos | `lambda_eff * T_total * Q_total` | `SCORING_README.md` |

The squared `Q` in dqi means a 1% cut in qubits is worth a 2% cut in Toffolis. The paper's
reference invsqrt circuit has `Q = 260`, 7,735 Toffolis, 1 T gate and 37 non-Clifford rotations,
so `C = 7,988` and `Q * C = 2.08e6`. The leaderboard then takes each benchmark's
`baseline_cost / cost` and combines the three by geometric mean (see
[COMPETITION.md](../COMPETITION.md)).

## Why the AND gate is the unit of work

Arithmetic in these circuits is mostly bitwise AND. To compute `a AND b` reversibly you take a fresh
scratch qubit (an ancilla) holding 0 and apply a Toffoli with controls `a` and `b`. The ancilla now
holds `a AND b` and the inputs are unchanged. One Toffoli.

The scratch qubit is not free to leave dirty. In a real superposition it stays entangled with `a`
and `b`, which wrecks interference later. The rule is that every ancilla must end at 0. The obvious
way to clean `a AND b` is to apply the same Toffoli again, which is its own inverse. That is a
second Toffoli, so each AND costs two.

MBUC removes the second one.

## MBUC on a worked AND example

Rather than undo the computation, measure the ancilla in a basis that destroys the information about
`a AND b` and then repair the damage classically. The kickmix instruction is `HMR` (pronounced
"hammer"): apply a Hadamard gate to the qubit, measure it, and reset it to 0. The Hadamard gate sends

- `|0>` to `(|0> + |1>) / sqrt(2)`
- `|1>` to `(|0> - |1>) / sqrt(2)`

Say the ancilla holds `f = a AND b`. After the Hadamard its amplitude for measuring outcome `m` is
`(-1)^(m*f) / sqrt(2)`. The check below prints exactly that.

```python
import numpy as np

H = np.array([[1, 1], [1, -1]]) / np.sqrt(2)
for f in (0, 1):
    ancilla = np.eye(2)[f]  # the ancilla holds |f>
    after = H @ ancilla  # Hadamard, then we measure
    for m in (0, 1):
        print(f"f={f} outcome={m} amplitude*sqrt2 = {after[m] * np.sqrt(2):+.0f}")
```

Only the case `f = 1, m = 1` has a minus sign. Two facts follow:

1. The outcome `m` is 0 or 1 with probability 1/2 each, whatever `f` was. The measurement tells us
   nothing about the data. That is what makes it safe.
2. The ancilla is back at 0, but the whole state has picked up a sign `(-1)^(m * a * b)`.

When `m = 0` the sign is `+1` and we are finished. When `m = 1` the state carries the sign
`(-1)^(a*b)`, and the CZ gate on `a` and `b` is exactly that sign. So the repair is: if the outcome
bit is 1, apply CZ to `a` and `b`. CZ is Clifford, so it is cheap, and no Toffoli is spent.

| `a` | `b` | outcome `m` | sign after HMR | CZ applied? | final sign |
|---|---|---|---|---|---|
| 0 | any | 0 or 1 | `+1` | if `m=1`, no effect | `+1` |
| 1 | 0 | 0 or 1 | `+1` | if `m=1`, no effect | `+1` |
| 1 | 1 | 0 | `+1` | no | `+1` |
| 1 | 1 | 1 | `-1` | yes, flips it | `+1` |

Compute plus uncompute therefore costs 1 Toffoli instead of 2. That is the sense in which MBUC
halves the AND cost. The same idea scales to whole registers: the reference circuits compute a row of
ANDs, add it into a target, and clear the ANDs by measurement.

## Bit-plus-phase bookkeeping

The nice property is that none of this needs a quantum simulator. Every gate used here takes a
basis state `|bits>` to another basis state times a sign. So we can store one bit per wire plus one
sign, and measurement outcomes are just random bits. The next block does that for the AND example
and compares three ways of cleaning up: a second Toffoli, MBUC with the fix, and MBUC without it.

```python
import itertools
import random


class State:
    """One computational basis state: a bit per wire plus a sign."""

    def __init__(self, bits):
        self.bits = dict(bits)
        self.sign = 1
        self.toffolis = 0

    def ccx(self, c1, c2, target):
        self.bits[target] ^= self.bits[c1] & self.bits[c2]
        self.toffolis += 1

    def cz(self, a, b):
        if self.bits[a] and self.bits[b]:
            self.sign = -self.sign

    def hmr(self, wire, rng):
        """Measure in the X basis and reset to 0; returns the outcome."""
        outcome = rng.randint(0, 1)
        if outcome and self.bits[wire]:
            self.sign = -self.sign
        self.bits[wire] = 0
        return outcome


def run(a, b, how, rng):
    s = State({"a": a, "b": b, "anc": 0})
    s.ccx("a", "b", "anc")  # anc = a AND b
    if how == "toffoli":
        s.ccx("a", "b", "anc")  # uncompute with a second Toffoli
    else:
        m = s.hmr("anc", rng)
        if how == "mbuc" and m:
            s.cz("a", "b")  # fix the sign when the outcome is 1
    return s


rng = random.Random(1)
for how in ("toffoli", "mbuc", "no fix"):
    bad = total = 0
    for a, b in itertools.product((0, 1), repeat=2):
        for _ in range(2000):
            s = run(a, b, how, rng)
            ok = s.bits == {"a": a, "b": b, "anc": 0} and s.sign == 1
            bad += not ok
            total += 1
    print(f"{how:8s} toffolis={s.toffolis}  failure rate={bad / total:.3f}")
```

The output shows two Toffolis and no failures for the plain version, one Toffoli and no failures for
MBUC, and one Toffoli with a failure rate near 0.125 when the fix is left out. The 1/8 is the chance
that the inputs are `a = b = 1` (1/4) times the chance that the outcome is 1 (1/2).

That last number is the reason verification works. A forgotten fix does not corrupt every run, but it
corrupts a predictable fraction, so repeated random trials find it. The next page,
[classical verification](classical-verification.md), turns this into a proper test with a failure
bound.

## What MBUC does not do

It only works when the phase error is cheap to repair, as it was here (one CZ). The paper warns
that applying `HMR` to a junk qubit with no matching fix makes the simulated phase flip with
probability 1/2, so the circuit fails loudly. And `R` (reset without measurement) is only for
qubits already known to be 0.

## Where the savings show up in the benchmarks

In the reference invsqrt circuit, every row of partial products in a multiplier is built as ANDs,
added in place, and cleared by measurement (the source comments say "uncomputes the ANDs by
measurement"). In the dqi baseline the whole decoder runs forward and backward around a phase kick,
but the cleaning of AND wires inside is cheap in the same way. Measuring where Toffolis go is the
first step in every optimisation, and kickmix has tools for this (the `builder.mark` blocks you can
see in the reference sources feed its flame charts).

## Exercises

1. A circuit computes 100 ANDs and later clears each one. How many Toffolis does it spend with
   Toffoli-based cleanup and with MBUC cleanup?
2. In the dqi score `R * Q^2 * T`, a change reduces qubits by 3% and raises Toffolis by 5%. Does the
   score go up or down (ignore `R`)?
3. You drop the CZ fix on one AND, and the circuit is tested on uniformly random `a`, `b`. What is the
   chance a single test fails? How many independent tests do you need before the chance of missing the bug is
   below `2^-20`?

## Answers

1. 200 and 100.
2. `0.97^2 * 1.05 = 0.988`, so the score goes down by about 1.2%.
3. A test fails with probability 1/8. The miss probability after `N` tests is `(7/8)^N`. Solve
   `(7/8)^N < 2^-20`: `N > 20 * ln 2 / ln(8/7) = 103.8`, so 104 tests.
