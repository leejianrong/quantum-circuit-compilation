# Primer: dfthcsos

Benchmark III is about chemistry. The target is FeMoCo, the iron-molybdenum cluster in the enzyme
that fixes nitrogen, with 76 spatial orbitals and 113 electrons. Unlike the other two benchmarks,
part of the work here is classical: you choose a compressed description of the molecule, and its
accuracy feeds into the score alongside the circuit cost.

Prerequisites: [costs and MBUC](costs-and-mbuc.md) and
[classical verification](classical-verification.md). Terms are in the [glossary](glossary.md).

## The Hamiltonian in one paragraph

A Hamiltonian is the operator whose lowest eigenvalue is the ground-state energy of the molecule.
For electrons in `N` orbitals it is written with two sets of numbers: an `N x N` matrix `h1` for
single-electron terms and an `N x N x N x N` tensor `h2` for pairs of electrons interacting. With
`N = 76` the tensor has `76^4`, about 33 million entries (the integrals file for this benchmark is
128 MB). A quantum computer finds the lowest eigenvalue with quantum phase estimation, which applies
the Hamiltonian over and over. Each application is built from a circuit that *encodes* `h1` and `h2`,
so the cost of loading those numbers is the cost of the algorithm. Everything below is about making
that loading cheap.

## Block encoding and the normalisation

A common way to build that circuit is a linear combination of unitaries (LCU): write
`H = sum_i w_i U_i` with positive weights `w_i` and simple unitary operators `U_i`. The
normalisation `Lambda = sum_i w_i` measures how big the sum is. The standard result (background
knowledge, not checked in the verifier sources) is that phase estimation needs a number of repeats
proportional to `Lambda` divided by the target precision, so a smaller `Lambda` means fewer
applications. The circuit has three parts (standard background, not from the verifier):

- `PREPARE` loads the weights as amplitudes over an index register.
- `SELECT` applies the operator `U_i` named by the index.
- `PREPARE` is then undone, which is why the benchmark charges for forward and reverse passes.

Three more pieces in the benchmark's picture are priced by formulas, not circuits we submit: the
outer and inner state preparations, and the Givens rotations. What we submit are the `ANGLE_k`
circuits, which load the rotation angles.

## Tensor factorization and the SVD intuition

A matrix with a few large singular values is nearly low rank. The singular value decomposition (SVD)
writes `A = sum_k s_k u_k v_k^T`, and keeping the top `r` terms gives the best rank-`r` approximation.
The error in Frobenius norm (square root of the sum of squared entries) equals
`sqrt(sum of the dropped s_k^2)`. The block shows it on a 76 x 76 matrix that is five strong
components plus noise.

```python
import numpy as np

rng = np.random.default_rng(0)
n = 76

# A symmetric "integral-like" matrix: a few strong components plus small noise.
strengths = [50.0, 20.0, 8.0, 3.0, 1.0]
vecs = rng.standard_normal((n, len(strengths)))
a = sum(s * np.outer(v, v) for s, v in zip(strengths, vecs.T)) / n
a += 0.01 * rng.standard_normal((n, n))
a = (a + a.T) / 2

u, s, vt = np.linalg.svd(a)
print("largest singular values:", np.round(s[:8], 3))
for rank in (1, 2, 3, 5, 8):
    approx = (u[:, :rank] * s[:rank]) @ vt[:rank]
    err = np.linalg.norm(a - approx)  # Frobenius norm
    predicted = np.sqrt((s[rank:] ** 2).sum())  # Eckart-Young: error of the best rank-r fit
    print(f"rank {rank}: Frobenius error {err:.4f}   sqrt(sum of dropped s^2) {predicted:.4f}")

# Storage: n*n numbers versus rank*(2n+1) numbers.
print("numbers stored:", n * n, "vs rank 5:", 5 * (2 * n + 1))
```

The same idea, applied to the tensor `h2`, is what "factorization" means here. The benchmark fixes
the form (called DFTHC in the paper and DF-THC in the verifier README; neither spells it out, so we read it as
double-factorized tensor hypercontraction, which fits the structure but is our reading). Each of `R`
components has `B` unit vectors `u_b` of length `N`. For each of `C` coefficient copies of a
component there is a matrix `X = sum_b w_b u_b u_b^T` with its own weights, and the two-body tensor
is the sum over components and copies of products `X (x) X`. You choose `R`, `B` and `C`, the
vectors and the weights. The baseline uses
`R, B, C = 65, 60, 60`. The number of unit vectors the circuits must load is then
`N + R * B = 76 + 3900 = 3976`: the 76 one-body vectors plus 3900 two-body ones.

Two costs come out of that choice. Fewer vectors means a smaller lookup table. And the weights set
`Lambda`, so a different factorization changes the number of times the whole block encoding repeats.
But a rougher factorization is a worse description of the molecule, and the verifier measures that
against the real integrals (`error_1` and `error_2`, both required to be at most 20 mHa, a unit of
energy).

## Givens rotations

A Givens rotation mixes two coordinates with an angle: `(p, c)` becomes
`(cos t * p - sin t * c, sin t * p + cos t * c)`. It preserves length. Any unit vector in `N`
dimensions can be built from `e_0` by `N - 1` such rotations along the edges of a tree over the
orbitals, so each vector is stored as `N - 1 = 75` angles. In the submission, each angle is a
`brot`-bit integer word `w`, meaning the angle `pi * w / 2^(brot-1)`; the baseline has `brot = 12`.

The block follows the decoding loop printed in `SCORING_README.md` on a path tree over 8 orbitals,
with the matching encoder, and shows that rounding the angles to 12 bits perturbs the vector by about
`1e-3`.

```python
import numpy as np

N, BROT = 8, 12  # the benchmark has N = 76 orbitals and brot = 12 in the baseline
tree_edges = [(t, t + 1) for t in range(N - 1)]  # a path tree rooted at orbital 0


def decode(words):
    """The verifier's decoding loop from SCORING_README: angle words to a unit vector."""
    v = np.zeros(N)
    v[0] = 1.0
    for (p, c), w in zip(tree_edges, words):
        theta = np.pi * w / 2 ** (BROT - 1)
        v[p], v[c] = (
            np.cos(theta) * v[p] - np.sin(theta) * v[c],
            np.sin(theta) * v[p] + np.cos(theta) * v[c],
        )
    return v


def encode(u):
    """Find the angles that rebuild unit vector u on the path tree, quantised to BROT bits."""
    tail = np.sqrt(np.cumsum((u**2)[::-1])[::-1])  # tail[t] = norm of u[t:]
    thetas = [np.arctan2(tail[t + 1], u[t]) for t in range(N - 2)]
    thetas.append(np.arctan2(u[N - 1], u[N - 2]))  # last angle carries the sign of u[N-1]
    return [int(round(th / np.pi * 2 ** (BROT - 1))) % 2**BROT for th in thetas]


rng = np.random.default_rng(1)
u = rng.standard_normal(N)
u /= np.linalg.norm(u)
words = encode(u)
v = decode(words)
print("words (12-bit):", words)
print("norm of decoded vector:", np.linalg.norm(v))  # rotations preserve length
print("max entry error from quantising angles:", np.abs(u - v).max())
print("angle step pi/2^11 =", np.pi / 2**11)
```

The tree travels in `submission.npz` as 75 `(parent, child)` pairs. The README asks for a spanning
tree rooted at orbital 0 that lists parents before children, and says the verifier checks only its
shape. The circuits do not depend on the tree, since they only load words. The Givens cost enters the score only through the formula
`2 (N - 1) (2 brot - 1)`.

## QROM: the circuit we write

A QROM (quantum read-only memory) is a lookup table. Given an address in a register, it XORs the
stored data word for that address into an output register. Done on a superposition of addresses it
loads all the rows at once. Here, address `a` selects a vector, and the data are its angle words.
The 75 words are split into `K = ceil(75 / J)` batches of `J` words, and circuit `ANGLE_k` loads
batch `k` (stored XORed with batch `k - 1`, so running them in order streams the batches through the
same registers).

The reference builds each circuit as a unary iteration over the address bits: a binary tree where
each internal node costs one Toffoli (an AND of the parent's flag and an address bit, cleared by
measurement), and at the leaves the data are written with CNOTs. The source docstring gives the cost
as at most `N + R*B - 2` Toffolis, so the **Toffoli count depends on the number of addresses and
not on the data**. It also uses `ceil(log2(A)) - 1` scratch qubits for `A` addresses. One saving is
already in the reference: a node whose rows all hold the same value is written directly and not
expanded further.

For the baseline that gives `K = 10` circuits of 3,974 Toffolis each, which the README confirms.

## The score and the gates

```text
score = lambda_eff * T_total * Q_total        (lower is better)
lambda_eff = sqrt(E_gap * (2 Lambda - E_gap))
T_total = ANGLES Toffolis (forward and reverse) + state-prep formulas + 2 (N-1) (2 brot - 1)
Q_total = persistent state-prep qubits + J * brot + max(outer, inner, angles temporaries)
```

`E_gap` is a fixed upper bound on the ground-state energy minus an energy computed from the
submitted factorization (the README calls it the SOS energy; the paper defines it as the "sum-of-squares energy shift", a
lower bound on the Hamiltonian's spectrum, so `E_gap` measures how far the true ground state sits above it). A submission is rejected if any of these fail:

| Check | Rule |
|---|---|
| `error_1`, `error_2` | at most 20 mHa |
| Raw normalisation `Lambda` | strictly greater than 49.0 |
| Gap `E_gap` | strictly greater than 3.914898 Ha |
| `0 < E_gap < 2 Lambda` | required |
| Each `ANGLE_k` circuit | at most 128 qubits, no `Z_POW`, workspace returned to 0, no residual phase |

The floors on `Lambda` and `E_gap` exist so you cannot shrink `lambda_eff` by cheating either
quantity. At the thresholds `lambda_eff` would be 19.19. The baseline sits at `Lambda = 308.46`,
`E_gap = 3.965`, which gives `lambda_eff = 49.30`.

This block reproduces the baseline's arithmetic from the README numbers.

```python
import math

# Baseline numbers quoted in SCORING_README.md (R, B, C = 65, 60, 60; N = 76; brot = 12; J = 8).
N, R, B, BROT, J = 76, 65, 60, 12, 8
LAMBDA, E_GAP = 308.4559397330944, 3.965477244291833  # raw normalisation and SOS gap

addresses = N + R * B  # one-body vectors plus two-body vectors
k_circuits = math.ceil((N - 1) / J)  # ANGLE_k circuits
selection_qubits = math.ceil(math.log2(addresses))
qrom_toffolis = addresses - 2  # unary iteration, upper bound per circuit
print("addresses", addresses, " circuits", k_circuits, " selection qubits", selection_qubits)
print("Toffolis per ANGLE circuit <=", qrom_toffolis, "(README reports 3974)")

angles = 2 * k_circuits * 3974  # forward and reverse passes
givens = 2 * (N - 1) * (2 * BROT - 1)
state_prep = 846 + 9461  # the two state preparations, taken from the README
heuristic = state_prep + givens
t_total = angles + heuristic
print("ANGLES Toffolis", angles, " Givens", givens, " heuristic total", heuristic)
q_total = 90 + J * BROT + 544  # persistent prep qubits + angle words + shared temporaries
lam_eff = math.sqrt(E_GAP * (2 * LAMBDA - E_GAP))
print(f"lambda_eff {lam_eff:.6f}  T_total {t_total}  Q_total {q_total}")
print(f"score {lam_eff * t_total * q_total:.6e}   (README: 3355599588.3155365 with unrounded inputs)")

# The accuracy gates and what they imply at their thresholds.
print("lambda_eff at the thresholds:", math.sqrt(3.914898 * (2 * 49.0 - 3.914898)))
```

## Where the cost goes

For the baseline: `T_total = 93,237` is 79,480 Toffolis in the angle circuits (85%) plus 13,757 from
formulas. `Q_total = 730` is 186 persistent qubits (90 for state preparation, 96 for the `J * brot`
angle words) plus 544 of shared temporary space. The Toffolis are dominated by the lookup, which we write. The 544 temporary qubits cannot
come from the angle circuits (their cap is 128 qubits, and 12 selection plus 96 word qubits leave at
most 20), so by elimination they come from the state-preparation formulas, which we do not build.
The README's formula says the same thing: the shared workspace is
`max(outer_temp, inner_temp, angles_temp)`. `lambda_eff` is 49.3
and moves with the factorization.

Levers that follow from the formula, without going beyond it:

- Fewer addresses (`R * B`) shrink every `ANGLE_k` and the state preparations, but change `Lambda`
  and the 20 mHa errors. Refitting the factorization is classical work and is where the largest
  swings can come from. [COMPETITION.md](../COMPETITION.md) says public notebooks report smaller refit
  factorizations; we have not verified that.
- A lookup whose rows share values is cheaper, because nodes of identical rows stop early. How much
  depends on the data, so the word encoding (`brot`, the tree choice, which rows are neighbours) matters.
- `brot` enters `Q_total` through `J * brot` and the Givens term, and enters accuracy through the
  angle rounding.

## Exercises

1. A 76 x 76 matrix has singular values 35.5, 19.2, 6.8, 3.3, 1.3 and then values near 0.1. What is
   the Frobenius error of the best rank-3 approximation (use only the values given, plus a tail of
   0.1 for the other 71)?
2. If `R * B` were reduced from 3,900 to 2,000, what would the per-circuit QROM Toffoli bound and
   the number of selection qubits be?
3. Using the README's `Lambda = 308.46` and `E_gap = 3.965`, what happens to `lambda_eff` if
   `Lambda` were halved at fixed `E_gap`? Would the verifier accept `Lambda = 154`?

## Answers

1. `sqrt(3.3^2 + 1.3^2 + 71 * 0.1^2) = sqrt(10.89 + 1.69 + 0.71) = sqrt(13.29) = 3.65`.
2. Addresses `76 + 2000 = 2076`, so at most 2,074 Toffolis, and `ceil(log2(2076)) = 12` selection
   qubits (2^11 = 2048 is below 2076).
3. `lambda_eff = sqrt(3.965 * (308 - 3.965)) = 34.7`, a fall of about 30%. The verifier would accept
   it on the `Lambda > 49.0` gate, though the factorization would still have to pass the 20 mHa
   error checks, which a `Lambda` that low may not allow.
