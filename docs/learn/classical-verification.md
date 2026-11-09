# Why a classical fuzz test verifies kickmix circuits

The submissions are quantum circuits, yet the verifier is an ordinary program running on a CPU. It
checks circuits with hundreds of millions of gates in minutes. This page explains why that is
legitimate, what a pass actually proves, and how the seeds are chosen so nobody can tune a circuit
to the test set.

Read [qubits and gates](qubits-and-gates.md) and [costs and MBUC](costs-and-mbuc.md) first. The
statements about guarantees follow Section II of the companion paper (Khattar et al.,
arXiv:2610.23832); the benchmark details come from the verifier sources.

## Why one bit per wire is enough

A general quantum circuit needs a vector of `2^n` amplitudes, which is hopeless beyond about 50
qubits. A kickmix circuit is restricted to four kinds of instruction:

1. Reversible classical gates (`X`, `CX`, `CCX`, `SWAP`). They permute basis states.
2. Diagonal phase gates (`Z`, `CZ`, `CCZ`, `Z_POW`, `NEG`). They multiply a basis state by a phase.
3. Measurement-and-reset (`HMR`, `R`), used for [MBUC](costs-and-mbuc.md).
4. Classical bit operations.

None of these creates a superposition. Give the circuit a basis state `|x>` (a definite bit on every
wire) and it returns a single basis state times a phase. So the simulator stores one bit per wire,
one bit per classical register, and one running phase, and each gate just updates them. Cost is
linear in the number of gates. The paper reports simulating at about `6e10` instructions per second
per core, which is why 102,400 shots of an 86-million-gate decoder take minutes.

The sampled bit-plus-phase run is one *branch*. `HMR` outcomes are random, so the same input can
give different phases on different runs if the circuit is wrong, and the simulator draws those
outcomes at random, as the real device would.

## Linearity turns basis checks into superposition guarantees

The real algorithm feeds the circuit a superposition, not a basis state. Fix the string `r` of all
`HMR` and `R` outcomes. Then the circuit is a fixed linear map `V_r` that sends each basis state to
one basis state times a phase. Linear maps are determined by their action on basis states, so if
`V_r` agrees with the intended unitary `U` on most basis inputs, it agrees on most of the
amplitude of any superposition.

Quantify it. Say the input is `sum_x alpha_x |x>`, a test draws `x` with probability `|alpha_x|^2`
and a uniformly random `r`, and a test fails with probability `eps`. Writing `eps_r` for the weight
of the failing inputs under record `r`, `eps` is the average of `eps_r` over `r`. The paper shows
that, provided each `V_r` maps distinct inputs to distinct outputs (true when `HMR` acts on a qubit
that is a function of the others, as in MBUC), the error of each branch is at most `2 sqrt(eps_r)`.
The records are orthogonal, so the branch errors add in quadrature:

```text
|| W psi - (U psi) (x) |+>^m ||^2  <=  4 eps
```

Two unit vectors at Euclidean distance `d` overlap by at least `1 - d^2/2`, and that gives a
fidelity of at least `(1 - 2 eps)^2`. After discarding the measurement record, the output is within
trace distance `sqrt(1 - (1 - 2 eps)^2) <= 2 sqrt(eps)` of the ideal output. Trace distance also
bounds the change in the outcome probabilities of any later measurement. This is the
`2 sqrt(eps)` in the DQI score, where `eps` is the decoder failure rate: a decoder with failure
rate `eps` has per-run success probability at least `1/2 - 2 sqrt(eps)`.

Here is the bound on the smallest interesting example: the AND-with-MBUC circuit from the previous
page with the CZ fix left out, acting on a uniform superposition of `(a, b)`.

```python
import numpy as np

# Data state: uniform superposition over the four values of (a, b).
psi = np.full(4, 0.5)

# Fix the measurement record m. With the CZ fix, V_m is the identity.
# Without it, V_1 flips the sign of the |a=1, b=1> amplitude.
V = {0: np.eye(4), 1: np.diag([1, 1, 1, -1])}
U = np.eye(4)  # the ideal operation on the data

# Failure rate for basis inputs: a test fails when m = 1 and a = b = 1.
eps = 0.5 * 0.25

# Output state of the data once the record is thrown away (a mixture over m).
rho = sum(0.5 * np.outer(V[m] @ psi, V[m] @ psi) for m in (0, 1))
ideal = np.outer(U @ psi, U @ psi)
trace_distance = 0.5 * np.abs(np.linalg.eigvalsh(rho - ideal)).sum()

print(f"epsilon                 = {eps}")
print(f"trace distance          = {trace_distance:.3f}")
print(f"bound 2*sqrt(epsilon)   = {2 * np.sqrt(eps):.3f}")
assert trace_distance <= 2 * np.sqrt(eps)
```

The true distance is 0.433 and the bound says 0.707. The bound is loose here but it never fails,
and it is cheap to evaluate from a count of failed shots.

One caveat: the guarantee only holds if the tests are drawn from `|alpha_x|^2`, the weights the
algorithm really uses. That is why each verifier fixes its own input distribution. The DQI verifier
draws an error weight `k` with probability `w_k^2` from the principal eigenvector of a small
matrix, then uniform positions and values. The invsqrt verifier sweeps every `x` in `[1, 3,133,452]`
64 times each, so every input is covered. The dfthcsos verifier runs every address 64 times.

## From tests to a failure-rate bound

Suppose the circuit fails on `k` of `N` independent shots. If its true failure rate were `eps_plus`
or larger, the chance of seeing at most `k` failures is a binomial tail. Setting that tail equal to a
target `delta` and solving for `eps_plus` gives the one-sided Clopper-Pearson upper bound. The
verifiers use `delta = 2^-128`. With zero failures it reduces to `(1 - eps_plus)^N = delta`, so
`eps_plus` is about `ln(1/delta)/N = 88.7/N`. In the paper's examples, 10,240 clean shots certify
a failure rate under 1%, and 102,400 clean shots certify under 0.1%.

How the number is used depends on the benchmark:

- invsqrt and dfthcsos need zero failures. Any bad shot rejects the submission.
- dqi allows failures, computes `eps_plus` from them, and rejects it only if `eps_plus >= 1/16`.
  Otherwise `eps_plus` feeds the repetition factor `R` in the score (see the
  [DQI primer](primer-dqi.md)).

## Fiat-Shamir seeding

If the test inputs were fixed, a submission could hard-code correct answers for them. The
verifier removes that by deriving the random seed from the submission itself:
`seed = SHA-256(circuit bytes)`, merged with a secret salt (the salt is a string that the grader
keeps private until submissions are closed). Change one byte of the file and you get a
different seed, so a different set of tests. The salt stops *seed grinding*: without it you could
add harmless no-op instructions until the seed happened to give easy tests. With a secret salt the
tests cannot be predicted at all.

The `HMR` outcomes in the simulator are seeded from the same hash, so the whole run is
reproducible once the salt is known. The next block is a toy of this scheme: a three-wire circuit
that should apply the phase `(-1)^(a AND b AND c)`, a correct version, a version missing the MBUC
fix, and a seed that depends on the circuit and the salt.

```python
import hashlib
import math
import random


def simulate(circuit, inputs, rng):
    """Run one shot. Returns (bits, sign). Wires: a, b, c (inputs) and t (scratch)."""
    bits = dict(inputs, t=0)
    sign, outcome = 1, 0
    for op, *args in circuit:
        if op == "ccx":
            c1, c2, target = args
            bits[target] ^= bits[c1] & bits[c2]
        elif op == "cz":
            if bits[args[0]] and bits[args[1]]:
                sign = -sign
        elif op == "hmr":
            outcome = rng.randint(0, 1)
            if outcome and bits[args[0]]:
                sign = -sign
            bits[args[0]] = 0
        elif op == "cz_if_outcome":
            if outcome and bits[args[0]] and bits[args[1]]:
                sign = -sign
    return bits, sign


def seed_from(circuit, salt):
    """Fiat-Shamir: the seed is a hash of the circuit text plus a salt."""
    return int(hashlib.sha256((repr(circuit) + salt).encode()).hexdigest(), 16)


def verify(circuit, salt, shots):
    rng = random.Random(seed_from(circuit, salt))
    failures = 0
    for _ in range(shots):
        inputs = {w: rng.randint(0, 1) for w in "abc"}
        bits, sign = simulate(circuit, inputs, rng)
        wanted = -1 if inputs["a"] & inputs["b"] & inputs["c"] else 1
        ok = all(bits[w] == inputs[w] for w in "abc") and bits["t"] == 0 and sign == wanted
        failures += not ok
    return failures


# Target: phase (-1)^(a AND b AND c), using one scratch wire t for a AND b.
good = [("ccx", "a", "b", "t"), ("cz", "t", "c"), ("hmr", "t"), ("cz_if_outcome", "a", "b")]
bad = good[:-1]  # forgot the MBUC fix

N = 10_000
for name, circuit in (("good", good), ("bad", bad)):
    print(name, "failures:", verify(circuit, salt="secret-1", shots=N), "of", N)

# Changing one byte of the circuit (or the salt) changes the seed.
print(seed_from(good, "x") == seed_from(good, "y"))

# After k = 0 failures in N shots, with confidence 1 - delta the true failure
# rate is below 1 - delta**(1/N), about ln(1/delta)/N.
delta = 2.0**-128
for n in (10_240, 102_400):
    print(n, "shots:", 1 - math.exp(math.log(delta) / n), math.log(1 / delta) / n)

# Chance a bug with failure rate p slips through N clean shots.
for p in (1 / 8, 1e-3, 1e-5):
    print(f"p={p:g}: miss probability over {N} shots = {(1 - p) ** N:.3g}")
```

The last loop is the honest summary of what fuzzing buys. A bug that fires on 1 in 8 runs does
not survive 10,000 tests. A bug that fires on 1 in 100,000 runs does survive them about 90% of the
time. But such a bug also barely moves `eps`, and by the bound above `eps` is what limits the
damage to the algorithm.

## What a pass does not prove

The dfthcsos `SCORING_README.md` is blunt about this and the points apply to every benchmark:

- A pass is evidence from sampled measurement branches, not a proof for every branch. A fault that
  is only reachable on a rare outcome can have an arbitrarily small `p`.
- Re-running with the same submission and salt repeats the same samples and adds no independent
  evidence.
- A public or empty salt makes the samples predictable, so it only helps with reproducibility. Our
  own self-checks use our own salts for that reason.
- A bound on the failure rate is not a bound on the physical error of the machine.

We also do not know the real salt, so a local pass with our own salt is a strong hint and not a
guarantee. More shots tighten the bound but do not remove these limits.

## Exercises

1. A circuit passes 20,000 shots with no failures. Using `ln(1/delta)/N` with `delta = 2^-128`, what
   is the largest failure rate you can rule out at this confidence?
2. A DQI decoder has `eps = 1e-4`. What is the guaranteed lower bound on its per-run success
   probability if the ideal run succeeds with probability 1/2?
3. In the toy verifier, append `("cz", "t", "t")` to `good`. The wire `t` is 0 at that point, so the
   instruction does nothing. Does the failure count change? Does the seed? Why does that matter
   for the secret salt?

## Answers

1. `88.7 / 20000 = 0.0044`, so failure rates above about 0.44% are ruled out.
2. `1/2 - 2 * sqrt(1e-4) = 0.5 - 0.02 = 0.48`.
3. The failure count stays 0 because the instruction is a no-op, but `repr(circuit)` changes, so the
   seed and the drawn tests change. Without a secret salt you could keep adding such instructions
   and keep the seed that draws the easiest tests. That is the grinding attack the salt prevents.
