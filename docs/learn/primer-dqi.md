# Primer: DQI

Benchmark II is the decoder inside Decoded Quantum Interferometry (DQI), a quantum algorithm that
turns an optimisation problem into an error-decoding problem. We are not asked to build the whole
algorithm. We shrink one circuit: a reversible Reed-Solomon decoder that reads a syndrome and, by
measurement-based uncomputation, applies a sign that depends on the decoded error.

This page covers the finite fields, the code, the syndromes, the problem DQI targets, and how decoder
failures are priced. Prerequisites: [costs and MBUC](costs-and-mbuc.md) and
[classical verification](classical-verification.md). Terms are in the [glossary](glossary.md).

## Finite fields GF(2^m)

A field is a set where you can add, subtract, multiply and divide (except by 0). The rationals and
the reals are fields. `GF(2^m)` is a finite one with `2^m` elements. Write each element as an
`m`-bit number, read as a polynomial in `x` with 0/1 coefficients. Then:

- **Addition** is XOR. It is also subtraction, since every element is its own negative.
- **Multiplication** is polynomial multiplication, reduced modulo a fixed irreducible polynomial of
  degree `m` (one that has no factors, like a prime number). The reduction is what keeps the answer
  within `m` bits.
- Every nonzero element has an inverse. There is also a primitive element `alpha` whose powers
  `alpha^0 ... alpha^(2^m - 2)` run through all nonzero elements, so multiplication can become
  addition of exponents (a "log table").

In the benchmark `m = 12`, so the field has 4,096 elements and `4095 = 2^12 - 1` nonzero ones. Field
addition on quantum registers is a row of CNOTs, which is cheap and Toffoli-free. Multiplication is
where Toffolis go: the paper's reference uses a 63-Toffoli Karatsuba multiplier for GF(2^12).

The block below implements the field and checks the facts above.

```python
def gf_mul(a, b, poly, degree):
    """Multiply in GF(2^degree): carry-less multiply, reducing by `poly` as we go."""
    result = 0
    while b:
        if b & 1:
            result ^= a  # adding in GF(2^m) is XOR
        b >>= 1
        a <<= 1
        if a >> degree:  # degree overflow: subtract (XOR) the modulus
            a ^= poly
    return result


# GF(2^4) with x^4 + x + 1: add is XOR, multiply is shift-and-reduce.
print("GF(16): 7 + 9 =", 7 ^ 9, "  7 * 9 =", gf_mul(7, 9, 0b10011, 4))

# GF(2^12) with x^12 + x^6 + x^4 + x + 1, the field used by the benchmark (m = 4095 = 2^12 - 1).
# Any irreducible polynomial gives an equivalent field; which one kickmix uses is not checked here.
POLY, DEG = 0x1053, 12
antilog = [1]
for _ in range(4094):
    antilog.append(gf_mul(antilog[-1], 2, POLY, DEG))  # powers of alpha = x
assert gf_mul(antilog[-1], 2, POLY, DEG) == 1  # alpha^4095 = 1
assert len(set(antilog)) == 4095  # alpha is primitive: it hits every nonzero element
log = {v: k for k, v in enumerate(antilog)}


def inverse(a):
    return antilog[(-log[a]) % 4095]


a, b = 0x5A3, 0xC7E
print("a*b =", hex(gf_mul(a, b, POLY, DEG)), " a * a^-1 =", gf_mul(a, inverse(a), POLY, DEG))
```

## Reed-Solomon codes and syndromes

A Reed-Solomon code adds redundancy to a list of field elements so that a few corrupted entries can
be found and fixed. In the textbook view used here, a word `c` of length `m = 4095` is a polynomial
`c(z) = sum_j c_j z^j`, and it is a valid codeword when `c(z)` is zero at `alpha^1, ..., alpha^n`.
Those `n = 70` conditions leave `4095 - 70 = 4025` free symbols, which is the "RS(4095, 4025)" of
[COMPETITION.md](../COMPETITION.md). Any two different codewords differ in at least `n + 1 = 71`
places. The paper reaches the same code from the evaluation side: it is the dual of the
code formed by evaluating low-degree polynomials, which is what the OPI problem below is about.

Suppose a few codeword symbols get corrupted. The corruption is an error vector `e` of length `m`
that is zero except at a few positions. A **syndrome** is a short summary of `e` that is zero for a valid
codeword, so it depends only on the corruption, not on the message. The verifier defines it as

```text
S_i = sum over j of  e_j * alpha^((i+1) j)        for i = 0 .. n-1
```

so `n = 70` field elements of 12 bits each, 840 bits. **Decoding** means recovering `e` from
`S_0 ... S_{n-1}`. With `n` syndromes you can correct up to `n // 2` errors, 35 here, because the
dual code has minimum distance `n + 1`.

How is that done in practice? The usual route, which the reference circuit follows, is: build a
syndrome polynomial, run the extended Euclidean algorithm (EEA) on it to get an error locator `sigma`
(its roots mark the corrupted positions) and an error evaluator `omega`, then use a Chien search
(try every position) and Forney's formula (a division) to get each error value. In the reference,
the EEA is run for `3 (n + 1) + 9 = 222` iterations, in a "synchronised" form where each iteration
does a fixed amount of work regardless of the data. I have not re-derived the algebra of the key
equation here, so treat that outline as the shape of the algorithm, not a proof.

The next block uses a tiny code over GF(16), with 15 positions and 4 syndromes, to show that a
syndrome really does determine the error for up to 2 errors, and that three errors break the
guarantee.

```python
import itertools

# A toy Reed-Solomon setting over GF(16): m = 15 positions, n = 4 syndromes, so up to
# n // 2 = 2 symbol errors are correctable. (The benchmark: m = 4095, n = 70, 35 errors.)
DEG, POLY, M, N = 4, 0b10011, 15, 4
ALPHA_POW = [1]
for _ in range(M - 1):
    a = ALPHA_POW[-1] << 1
    ALPHA_POW.append(a ^ POLY if a >> DEG else a)
LOG = {v: k for k, v in enumerate(ALPHA_POW)}


def mul(a, b):
    return 0 if 0 in (a, b) else ALPHA_POW[(LOG[a] + LOG[b]) % M]


def syndromes(error):
    """S_i = sum_j e_j alpha^((i+1) j) for i = 0..n-1, as in the verifier's docstring."""
    out = []
    for i in range(N):
        s = 0
        for pos, val in error.items():
            s ^= mul(val, ALPHA_POW[((i + 1) * pos) % M])
        out.append(s)
    return tuple(out)


# Every error pattern with at most 2 nonzero symbols, and its syndrome.
table = {}
for k in range(3):
    for positions in itertools.combinations(range(M), k):
        for values in itertools.product(range(1, 16), repeat=k):
            error = dict(zip(positions, values))
            table[syndromes(error)] = error

n_patterns = 1 + M * 15 + (M * (M - 1) // 2) * 15 * 15
print("error patterns:", n_patterns, " distinct syndromes:", len(table))
assert len(table) == n_patterns  # a syndrome pins down the error uniquely

# "Decoding" is the inverse lookup. At this size a table is fine; at 4095 positions it is not.
hidden = {5: 9, 11: 3}
s = syndromes(hidden)
print("syndrome", s, "decodes to", table[s], "correct:", table[s] == hidden)

# With 3 errors the guarantee ends: some 3-error pattern collides with a smaller one.
three = {1: 1, 2: 1, 3: 1}
print("3 errors decode to", table.get(syndromes(three)), "(wrong or missing)")
```

A lookup table works at 15 positions. At 4095 positions with up to 35 errors the table would have
more entries than atoms, which is why a real decoder (the EEA route) is needed, and why a reversible
version is expensive.

## The OPI problem

DQI's showcase problem is Optimal Polynomial Intersection (OPI). At each of the `m = q - 1` nonzero
field points `alpha_i` you get a set `F_i` of allowed values, each of size `r` (here `r = 2016`).
You choose a polynomial `Q` of degree below `n` to maximise how many points `i` satisfy
`Q(alpha_i) in F_i`. Checking an answer is easy: evaluate and count. Finding a good one is hard for
the classical algorithms known, which makes OPI a candidate for verifiable quantum advantage. DQI
prepares a superposition over candidate polynomials, weighted so that high-scoring ones are likely.
The step that does the work is decoding the Reed-Solomon syndrome of the dual code. Decoding up to
`l = n // 2` errors lets DQI use a degree-`l` weighting function, and correcting more errors
improves the answers.

Inside the benchmark the decoder gets the syndrome registers `S0 ... S69` (12 qubits each, 840
qubits) and 4095 classical registers `E0 ... E4094` holding measurement bits `M_j`. It must restore
the syndromes, return all scratch to 0, and multiply the phase by `(-1)` to the power of the XOR over
all `j` of `popcount(e_j & M_j)`, where `e` is the decoded error. The verifier tests this on 102,400
random shots, with error weight `k` drawn from the weight distribution DQI would produce (average
about 31, at most 35).

## Where the reference spends its Toffolis

From the paper, the reference decoder has 1,893 qubits and 5,725,461 Toffolis. It runs three stages
(the `mark` blocks in `dqi_reference_circuit.py`): the forward EEA, the Chien search with Forney and
MBUC phase, and the reverse EEA that restores the syndromes. The paper states that each position of
the Chien/Forney stage costs 351 Toffolis for one Itoh-Tsujii inversion (inverting by repeated
squaring and multiplication), so `4095 * 351 = 1,437,345`, about a quarter of the total. By
subtraction, about 4.29 million remain for the two EEA passes and the initial shifts. That is my
arithmetic, not a figure from the paper. The paper itself lists the explicit remainder storage,
pointer-driven EEA steps, polynomial-basis multiplication and per-position inversion as parts that
"can be improved."

## Decoding failure versus repetition overhead

A decoder need not be right on every input. A DQI candidate is checked classically, so a decoder
failure only lowers the chance of getting a good candidate. The paper shows that if the decoder
fails with probability `eps` (on inputs drawn from the DQI distribution) then each run succeeds with
probability at least `1/2 - 2 sqrt(eps)`, instead of `1/2`. This is the `2 sqrt(eps)` from the
[classical verification](classical-verification.md) page.

Lower per-run success means more repeated runs. To reach a given overall failure probability you need
`ln(delta') / ln(1 - p)` runs, so the ratio against the ideal case is

```text
R(eps) = ln 2 / ( - ln(1/2 + 2 sqrt(eps)) )
```

and the score is `S = R(eps_plus) * Q^2 * T`, with `eps_plus` the certified upper bound on `eps` from
the fuzz test, and the verifier rejects `eps_plus >= 1/16`. Even a perfect circuit pays: 102,400
clean shots only certify `eps_plus` of about `8.7e-4`, so every exact submission has `R` near 1.19.

```python
import math


def repetition_overhead(eps):
    """R(eps) = ln 2 / -ln(1/2 + 2 sqrt(eps)), valid for 0 <= eps < 1/16."""
    if eps == 0:
        return 1.0
    return math.log(2) / -math.log(0.5 + 2 * math.sqrt(eps))


def runs_needed(p, target=1e-6):
    """Independent runs, each succeeding with probability p, to fail overall with prob <= target."""
    return math.log(target) / math.log(1 - p)


for eps in (1e-5, 1e-4, 1e-3, 1e-2, 6e-2):
    p = 0.5 - 2 * math.sqrt(eps)  # guaranteed per-run success probability
    ratio = runs_needed(p) / runs_needed(0.5)
    print(f"eps={eps:g}: R={repetition_overhead(eps):.3f}  runs ratio={ratio:.3f}")

# Zero failures in N = 102,400 shots, confidence 1 - 2^-128: every exact circuit pays this.
n_shots = 102_400
eps_plus = 1 - 2.0 ** (-128 / n_shots)
print(f"eps_plus = {eps_plus:.2e}, R = {repetition_overhead(eps_plus):.3f}")

# Score of the paper's reference decoder IF it had zero failures: R * Q^2 * T.
q, t = 1893, 5_725_461
print(f"score about {repetition_overhead(eps_plus) * q**2 * t:.3e}")

# Break-even: a trick that saves a fraction f of the Toffolis and costs eps.
eps = 1e-3
print(f"eps={eps:g} needs more than {1 - 1 / repetition_overhead(eps):.1%} fewer Toffolis to pay off")
```

The table is steep: `R` is 1.02, 1.06, 1.21 and 1.94 at `eps` of `1e-5` to `1e-2`, as in the paper.
So approximation pays when it removes a large share of the work for a tiny failure rate, and not
otherwise. Also `Q` is squared, which makes workspace the heavier lever: the 840 syndrome qubits are
fixed, and everything else (1,053 in the reference) is a target. Two levers follow: a cheaper
decoding algorithm than the reference's (COMPETITION.md reports public notebooks using a
Berlekamp-Massey style one, which we have not verified), and trading a small `eps` for fewer
iterations.

## Exercises

1. A change saves 20% of the Toffolis but makes `eps_plus = 1e-2`. Does the score improve?
2. The reference has 1,893 qubits. How many are the syndrome registers, and how many are workspace?
3. In GF(16) with `x^4 + x + 1`, multiply `0b0110` by `0b0011` by hand, then check it with `gf_mul`.

## Answers

1. No. `R(1e-2) = 1.94` so the score is multiplied by about `1.94 * 0.8 = 1.55`, a loss. You would
   need more than `1 - 1/1.94 = 48%` fewer Toffolis.
2. `70 * 12 = 840` syndrome qubits, so `1893 - 840 = 1053` workspace qubits (Q counts every qubit).
3. `(x^2 + x)(x + 1) = x^3 + x^2 + x^2 + x = x^3 + x`, which is `0b1010 = 10`. Run
   `gf_mul(6, 3, 0b10011, 4)` to confirm.
