# Qubits, amplitudes, gates and measurement

By the end of this page you will have simulated a Bell state in about ten lines of numpy, and you
will know what each line means. The whole model is vectors, matrices and a random draw.

## From bits to qubits

A bit is 0 or 1. A qubit holds a pair of complex numbers, called **amplitudes**, one for each of
the two values. Write them as a length-2 vector:

```python
import numpy as np

ket0 = np.array([1, 0], dtype=complex)  # the qubit is definitely 0
ket1 = np.array([0, 1], dtype=complex)  # the qubit is definitely 1
psi = (ket0 + 1j * ket1) / np.sqrt(2)  # a mix of both
print(psi)
```

```text
[0.70710678+0.j         0.        +0.70710678j]
```

The names `ket0` and `ket1` come from the notation `|0>` and `|1>` (read "ket zero"). Physicists use
it everywhere, so you will see it in papers. For us, `|0>` is just the vector `[1, 0]`.

A state like `psi` is called a **superposition**: both amplitudes are nonzero. That is all the word
means. Nothing is "in two places at once"; the state is a vector with two nonzero entries.

The amplitudes are not probabilities. They can be negative or complex. The rule that connects them to
something you can observe is: **the probability of reading value `k` is the squared magnitude of
amplitude `k`**. The squared magnitudes must add up to 1, so every valid state is a unit vector.

```python
print(np.abs(psi) ** 2)
print(round(np.sum(np.abs(psi) ** 2), 6))
```

```text
[0.5 0.5]
1.0
```

Here a 50/50 coin. Notice that the factor `1j` did not change the probabilities. We come back to why
that still matters.

## Gates are unitary matrices

A **gate** changes a state. Every gate is a matrix, and applying it is a matrix-vector product. The
matrix must be **unitary**: `U† U = I`, where `U†` is the conjugate transpose. Unitary matrices
preserve length, so a unit vector stays a unit vector and the probabilities keep adding up to 1.
Three gates matter on this page.

```python
X = np.array([[0, 1], [1, 0]], dtype=complex)  # NOT: swaps the two amplitudes
Z = np.array([[1, 0], [0, -1]], dtype=complex)  # flips the sign of the |1> amplitude
H = np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2)  # Hadamard: makes superpositions


def show(v):
    """Print a vector with rounding, so tiny float errors do not clutter the output."""
    print(np.round(v, 3) + 0)


show(X @ ket0)
show(H @ ket0)
print(np.allclose(H.conj().T @ H, np.eye(2)))  # unitary check
```

```text
[0.+0.j 1.+0.j]
[0.707+0.j 0.707+0.j]
True
```

`X` is the quantum NOT: it turns `|0>` into `|1>`. `H` (the Hadamard gate) turns a definite value into
an equal superposition. `Z` does nothing to `|0>` and negates the amplitude of `|1>`. On a definite
value that looks harmless, which is the next point.

## Interference

Apply `H` to `|0>` and you get amplitudes `[0.707, 0.707]`. Apply `H` again and the state returns to
`|0>` exactly:

```python
show(H @ H @ ket0)
```

```text
[1.+0.j 0.+0.j]
```

The second `H` sends the `|1>` amplitude back towards both outcomes, and the contributions to `|1>`
cancel (`0.707 * 0.707 - 0.707 * 0.707 = 0`) while those to `|0>` add up. This cancellation is
**interference**, and it is the one thing amplitudes can do that probabilities cannot. Probabilities
are never negative, so they never cancel.

Now put a `Z` in between:

```python
plus = H @ ket0
show(H @ (Z @ plus))
```

```text
[0.+0.j 1.+0.j]
```

`Z` only changed a sign, and it moved the whole outcome from `|0>` to `|1>`. A sign on an amplitude is
called a **phase**. A phase is invisible if you measure immediately, and decisive if you let the
amplitudes interfere again afterwards. Circuits in this competition use phases heavily, and
[the next page](reversible-logic.md) returns to them.

## Measurement

**Measuring** a qubit gives you one ordinary bit. The probability of each bit is the squared
magnitude of its amplitude, and afterwards the state is the one you read (it collapses to `|0>` or
`|1>`). You cannot look at the amplitudes themselves, only sample from them. To estimate a
probability you repeat the whole experiment many times; each repeat is a **shot**.

```python
rng = np.random.default_rng(0)
probs = np.abs(plus) ** 2
shots = rng.choice(2, size=1000, p=probs)
print(np.bincount(shots))
```

```text
[473 527]
```

Roughly 500 each, with the usual sampling noise. The verifier in this competition works in terms of
shots too: it runs a circuit on many random inputs and compares what comes out.

## Two qubits

The state of two qubits is a vector with 4 amplitudes, one per bit string `00`, `01`, `10`, `11`.
We use the convention that the **leftmost bit is qubit 0**. To combine two separate qubits you take
the Kronecker product (`np.kron`) of their vectors:

```python
show(np.kron(ket0, ket1))  # qubit 0 is 0, qubit 1 is 1: the string "01"
state = np.kron(H @ ket0, ket0)  # qubit 0 in superposition, qubit 1 is 0
show(state)
```

```text
[0.+0.j 1.+0.j 0.+0.j 0.+0.j]
[0.707+0.j 0.   +0.j 0.707+0.j 0.   +0.j]
```

The second vector has amplitude on `00` and `10`: qubit 0 is 0 or 1, qubit 1 is 0.

A gate on two qubits is a 4x4 matrix. The one you need is **CNOT** (controlled-NOT): flip qubit 1 if
qubit 0 is 1, otherwise do nothing. It swaps the amplitudes of `10` and `11`.

```python
CNOT = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]], dtype=complex)

bell = CNOT @ state
show(bell)
print(np.round(np.abs(bell) ** 2, 3))
```

```text
[0.707+0.j 0.   +0.j 0.   +0.j 0.707+0.j]
[0.5 0.  0.  0.5]
```

That is the **Bell state**, `(|00> + |11>) / sqrt(2)`. Measuring it gives `00` half the time and
`11` half the time, never `01` or `10`. The two bits are random but always equal. Neither qubit has
a state of its own any more: the pair has one, and you cannot write it as a `np.kron` of two
single-qubit vectors. This is **entanglement**. For this competition you can treat it as the reason
multi-qubit states need the full vector, not one small vector per qubit.

## Three qubits and the cost of the vector

For `n` qubits the vector has `2**n` entries. A helper that applies a one-qubit gate to qubit `k`, and
a CNOT between any two qubits, makes larger circuits short to write:

```python
def on(gate, k, n):
    """The 2**n x 2**n matrix that applies a one-qubit gate to qubit k."""
    mats = [gate if i == k else np.eye(2) for i in range(n)]
    out = mats[0]
    for m in mats[1:]:
        out = np.kron(out, m)
    return out


def cnot(control, target, n):
    """The 2**n x 2**n CNOT, built by permuting basis states."""
    out = np.zeros((2**n, 2**n), dtype=complex)
    for i in range(2**n):
        bits = [(i >> (n - 1 - q)) & 1 for q in range(n)]
        if bits[control]:
            bits[target] ^= 1
        j = sum(b << (n - 1 - q) for q, b in enumerate(bits))
        out[j, i] = 1
    return out


n = 3
ghz = np.zeros(2**n, dtype=complex)
ghz[0] = 1  # start in |000>
ghz = on(H, 0, n) @ ghz
ghz = cnot(0, 1, n) @ ghz
ghz = cnot(0, 2, n) @ ghz
for i, a in enumerate(ghz):
    if abs(a) > 1e-9:
        print(format(i, f"0{n}b"), np.round(a, 3))
```

```text
000 (0.707+0j)
111 (0.707+0j)
```

This is the three-qubit cousin of the Bell state: all three bits agree. The matrices here are
`8 x 8`. At 30 qubits the vector would hold a billion amplitudes, and at 100 qubits more than any
computer could store. That blow-up is why quantum computers are interesting, and why simulating
a general circuit classically is hopeless. The circuits in this competition are a restricted kind that
a classical computer can still check cheaply, which is the subject of
[classical verification](classical-verification.md). First we need the restricted gates.

## Exercises

1. Predict the output of `H`, then `Z`, then `H` applied to `|0>`, then check it in numpy. Which
   page section already contains the answer, and why does it work?
2. Build the state `(|01> + |10>) / sqrt(2)` starting from `|00>`. You may use `X`, `H`, `CNOT` and
   the `on` and `cnot` helpers.
3. Sample 1000 shots from the three-qubit state `ghz` above. Check that you only ever see the strings
   `000` and `111`.

??? note "Solutions"

    **1.** The sign flip from `Z` turns the interference around, so the result is `|1>`. The
    "Interference" section already shows it: `H Z H = X`.

    ```python
    show(H @ Z @ H @ ket0)
    print(np.allclose(H @ Z @ H, X))
    ```

    **2.** Make a Bell state, then apply `X` to qubit 1 so `00` becomes `01` and `11` becomes `10`.

    ```python
    s = np.array([1, 0, 0, 0], dtype=complex)
    s = cnot(0, 1, 2) @ (on(H, 0, 2) @ s)
    s = on(X, 1, 2) @ s
    show(s)
    ```

    **3.** `rng.choice` draws indices with the given probabilities.

    ```python
    draws = rng.choice(2**n, size=1000, p=np.abs(ghz) ** 2)
    print({format(int(i), f"0{n}b") for i in draws})
    ```
