# Reversible logic, Toffoli, ancillas and phase

The circuits you will shrink in this competition are built from a small set of gates: NOT, CNOT,
Toffoli, and phase gates, plus a trick for cleaning up scratch qubits. This page introduces each one,
with code. It assumes you have read [qubits and gates](qubits-and-gates.md).

## Why logic has to be reversible

Every gate is a unitary matrix, and a unitary matrix can be undone: multiply by the conjugate
transpose and you are back where you started. For a gate that maps bit strings to bit strings, that
means it must be a bijection. Different inputs may not produce the same output.

Ordinary AND is not a bijection. Four input pairs go in, two output values come out, and from the
output `0` you cannot tell which of three inputs you had. So a quantum computer cannot have an AND gate
that overwrites its inputs. It needs gates that keep enough information to run backwards.

## NOT, CNOT and Toffoli as truth tables

Each of the three gates below flips one bit, and the flip is controlled by zero, one or two other bits.

```python
import itertools

import numpy as np


def NOT(a):
    return (1 - a,)


def CNOT(a, b):  # flip b if a is 1
    return a, b ^ a


def TOFFOLI(a, b, c):  # flip c if a and b are both 1
    return a, b, c ^ (a & b)


print("a b c -> a b c'")
for a, b, c in itertools.product([0, 1], repeat=3):
    print(a, b, c, "->", *TOFFOLI(a, b, c))
```

```text
a b c -> a b c'
0 0 0 -> 0 0 0
0 0 1 -> 0 0 1
0 1 0 -> 0 1 0
0 1 1 -> 0 1 1
1 0 0 -> 1 0 0
1 0 1 -> 1 0 1
1 1 0 -> 1 1 1
1 1 1 -> 1 1 0
```

Only the last two rows differ from the input. The **Toffoli** gate (also called CCNOT, controlled-
controlled-NOT) swaps the states `110` and `111`. The two bits `a` and `b` pass through unchanged, so
the gate is its own inverse: apply it twice and nothing has happened.

Set the target `c` to 0 and the gate computes AND:

```python
for a, b in itertools.product([0, 1], repeat=2):
    print(a, b, "AND =", TOFFOLI(a, b, 0)[2])
```

```text
0 0 AND = 0
0 1 AND = 0
1 0 AND = 0
1 1 AND = 1
```

Together with NOT, Toffoli can build any classical logic circuit. That is why it is the workhorse, and
why [its count dominates the cost](costs-and-mbuc.md) of the circuits in this competition.

As a quantum gate it is an 8x8 permutation matrix. Each column has a single 1, in the row of the
output string. Build it from the truth table and check that it is unitary:

```python
def permutation_matrix(gate, n):
    M = np.zeros((2**n, 2**n))
    for i in range(2**n):
        bits = tuple((i >> (n - 1 - q)) & 1 for q in range(n))
        out = gate(*bits)
        j = sum(b << (n - 1 - q) for q, b in enumerate(out))
        M[j, i] = 1
    return M


T = permutation_matrix(TOFFOLI, 3)
print(T.astype(int)[4:])  # the bottom half, where the action is
print(np.allclose(T.T @ T, np.eye(8)))
```

```text
[[0 0 0 0 1 0 0 0]
 [0 0 0 0 0 1 0 0]
 [0 0 0 0 0 0 0 1]
 [0 0 0 0 0 0 1 0]]
True
```

The last two rows are crossed, which is the swap of `110` and `111`. The `True` confirms `T†T = I`.

## Ancillas and uncomputation

Computing something with reversible gates usually needs scratch space. An **ancilla** is a qubit you
borrow for that: it starts at 0, holds an intermediate result, and has to be at 0 again when you hand
it back. To compute `a AND b AND c` you need the AND of `a` and `b` stored somewhere before you can
combine it with `c`.

```python
def and3(a, b, c):
    anc = 0
    a, b, anc = TOFFOLI(a, b, anc)  # anc = a AND b
    anc, c, out = TOFFOLI(anc, c, 0)  # out = (a AND b) AND c
    a, b, anc = TOFFOLI(a, b, anc)  # uncompute: anc back to 0
    return anc, out


for bits in itertools.product([0, 1], repeat=3):
    print(bits, "-> ancilla, out =", and3(*bits))
```

```text
(0, 0, 0) -> ancilla, out = (0, 0)
(0, 0, 1) -> ancilla, out = (0, 0)
(0, 1, 0) -> ancilla, out = (0, 0)
(0, 1, 1) -> ancilla, out = (0, 0)
(1, 0, 0) -> ancilla, out = (0, 0)
(1, 0, 1) -> ancilla, out = (0, 0)
(1, 1, 0) -> ancilla, out = (0, 0)
(1, 1, 1) -> ancilla, out = (0, 1)
```

The third Toffoli repeats the first. Since Toffoli undoes itself, the ancilla returns to 0 for every
input. This step is **uncomputation**, and it costs a Toffoli. Remember that, because the competition's
trick (measurement-based uncomputation, covered on [the costs page](costs-and-mbuc.md)) is a cheaper
way to do the same cleanup.

Why not just leave the ancilla alone and ignore it? Because a leftover value is a copy of information
about the input, and a copy ruins interference. Here is the smallest case. Qubit 0 goes through `H`,
a CNOT copies it into qubit 1 as "garbage", and a final `H` should undo the first one, as it did on
the previous page.

```python
H = np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2)
X = np.array([[0, 1], [1, 0]], dtype=complex)


def show(v):
    print(np.round(v, 3) + 0)


def on(gate, k, n):
    """Apply a one-qubit gate to qubit k of n (qubit 0 is the leftmost bit)."""
    mats = [gate if i == k else np.eye(2) for i in range(n)]
    out = mats[0]
    for m in mats[1:]:
        out = np.kron(out, m)
    return out


def cnot(control, target, n):
    out = np.zeros((2**n, 2**n), dtype=complex)
    for i in range(2**n):
        bits = [(i >> (n - 1 - q)) & 1 for q in range(n)]
        if bits[control]:
            bits[target] ^= 1
        j = sum(b << (n - 1 - q) for q, b in enumerate(bits))
        out[j, i] = 1
    return out


start = np.array([1, 0, 0, 0], dtype=complex)  # |00>
copied = cnot(0, 1, 2) @ (on(H, 0, 2) @ start)

print("garbage left in qubit 1:")
show(on(H, 0, 2) @ copied)
print("garbage uncomputed first:")
show(on(H, 0, 2) @ (cnot(0, 1, 2) @ copied))
```

```text
garbage left in qubit 1:
[ 0.5+0.j  0.5+0.j  0.5+0.j -0.5+0.j]
garbage uncomputed first:
[1.+0.j 0.+0.j 0.+0.j 0.+0.j]
```

With the copy left in place, the second `H` no longer cancels: the state is spread over all four
outcomes. With the copy removed, you get `|00>` back exactly. Algorithms that rely on interference
need their scratch qubits clean, which is why the competition's definition says an ancilla "must be
returned to 0".

## Phase gates

A **phase gate** multiplies the `|1>` amplitude by a unit-magnitude complex number
`e^(i*theta)` and leaves `|0>` alone: `diag(1, e^(i*theta))`. You have met one, `Z`, which is `theta = pi`
(multiply by -1). Two others have names: `S` is `theta = pi/2` (multiply by `i`) and `T` is
`theta = pi/4`.

```python
S = np.diag([1, 1j])
T_gate = np.diag([1, np.exp(1j * np.pi / 4)])
ket1 = np.array([0, 1], dtype=complex)

show(S @ S @ ket1)  # two S gates make a Z
show(T_gate @ ket1)  # e^(i*pi/4) = 0.707 + 0.707i
```

```text
[ 0.+0.j -1.+0.j]
[0.   +0.j    0.707+0.707j]
```

Phase gates change no probabilities. They matter once the amplitudes interfere afterwards, as with the
`H Z H` example on the previous page. A phase gate also acts on a state that is just a classical bit
string by multiplying the whole state by a number. Keep this in mind: NOT, CNOT, Toffoli and the phase
gates all send a classical bit string to another bit string, and the phases collect into one running
factor. That is the property classical verification uses.

## Phase kickback

The last idea is the strangest, and it explains how phases get attached to the right place. Take a
CNOT whose target qubit is in the state `|->`, which is `(|0> - |1>) / sqrt(2)`, and whose control is
in superposition. Flipping a `|->` gives `-|->`, a sign. So the target is unchanged, but the sign lands
on the control's `|1>` branch. The phase "kicks back" to the control.

```python
ket0 = np.array([1, 0], dtype=complex)
plus = H @ ket0
minus = H @ X @ ket0  # (|0> - |1>) / sqrt(2)

state = np.kron(plus, minus)  # control = |+>, target = |->
after = cnot(0, 1, 2) @ state
print(np.allclose(after, np.kron(minus, minus)))  # control is now |->, target untouched

show(on(H, 0, 2) @ after)  # undo the control's H: it reads 1, not 0
```

```text
True
[0.   +0.j 0.   +0.j 0.707+0.j -0.707+0.j]
```

The final state has the control qubit definitely 1 (the entries are on `10` and `11`), where without
the kickback it would have been 0. In effect a CNOT with a `|->` target behaves as a `Z` on the
control. This is how a sign gets attached to one branch of a superposition using only a bit-flip, with no
phase gate. You will meet the same pattern again in the later pages.

## Exercises

1. Build the CNOT truth table from the `CNOT` function and its 4x4 matrix with
   `permutation_matrix`, and check the matrix is unitary.
2. Write a reversible circuit out of `TOFFOLI`, `CNOT` and `NOT` that computes `a OR b` into a fresh
   target bit. Check all four inputs. Hint: `a OR b = NOT(NOT a AND NOT b)`.
3. Show that `T_gate` applied eight times is the identity, and that four applications equal `Z`.

??? note "Solutions"

    **1.**

    ```python
    C = permutation_matrix(CNOT, 2)
    print(C.astype(int))
    print(np.allclose(C.T @ C, np.eye(4)))
    ```

    **2.** Flip `a` and `b`, AND them into the target, then flip everything back and flip the target.

    ```python
    def or_gate(a, b):
        (a,) = NOT(a)
        (b,) = NOT(b)
        a, b, t = TOFFOLI(a, b, 0)
        (t,) = NOT(t)
        (a,) = NOT(a)
        (b,) = NOT(b)
        return t


    print([or_gate(a, b) for a, b in itertools.product([0, 1], repeat=2)])
    ```

    **3.** `T` multiplies the `|1>` amplitude by `e^(i*pi/4)`. Four of them multiply by `e^(i*pi) = -1`,
    which is `Z`. Eight multiply by `e^(2*i*pi) = 1`.

    ```python
    print(np.allclose(np.linalg.matrix_power(T_gate, 8), np.eye(2)))
    print(np.allclose(np.linalg.matrix_power(T_gate, 4), np.diag([1, -1])))
    ```
