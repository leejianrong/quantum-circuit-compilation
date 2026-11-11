# Hands-on kickmix

Every circuit in this competition is a kickmix circuit, and every score comes from running one
through the kickmix simulator. This page is the practical bridge: what the instructions are, how
circuits are stored, how to build one in Python, and how to check one. At the end you build a 4-bit
adder, prove it correct on all 256 inputs, and then break it three ways to see what a failed
verification looks like.

You need [reversible logic](reversible-logic.md) and
[costs and MBUC](costs-and-mbuc.md) first, and it helps to have skimmed
[classical verification](classical-verification.md). The `kickmix` package is a dependency of this
repository, so `make install` has already put it in your environment. The repository requires
`kickmix>=1.0.0`; the Python module reports its own version as `0.1`, so do not be surprised by the
printout below.

```python
import kickmix as km

print(km.__version__)
```

## The instruction set

A kickmix circuit is a list of instructions. Every instruction sends a computational basis state
(one definite bit string) to another basis state, times a phase. Nothing ever creates a
superposition, which is why a classical computer can run these circuits. The instructions fall into
four classes:

| Class | Instructions | What it does |
|---|---|---|
| Reversible classical | `X`, `CX`, `CCX`, `SWAP`, `CSWAP` | Permute the qubit bits. `CCX` is the Toffoli; `CCX` and `CSWAP` cost 1 each |
| Diagonal phase | `Z`, `CZ`, `CCZ`, `Z_POW`, `NEG` | Leave the bits alone, multiply the phase when all controls are 1. `NEG` flips the global sign |
| Measure and reset | `HMR`, `R` | `HMR` measures a qubit in the X basis into a classical bit and resets it to 0. `R` resets to 0 |
| Classical bits | `BIT_STORE0`, `BIT_STORE1`, `BIT_INVERT` | Set or invert classical bits |

Qubits are written `q0`, `q1`, and so on. Classical bits are `b0`, `b1`, and so on. Any instruction
can be made conditional on a classical bit with a trailing `if b3`, or for a whole block with
`PUSH_CONDITION if b3` ... `POP_CONDITION`. The remaining instructions carry no computation:
`INFO_TAG` attaches a label (used for charts), `DEBUG_PRINT` prints a value while simulating, and
`REGISTER` with `APPEND_TO_REGISTER` gives a group of qubits a name.

`Z_POW q0 0.25` multiplies the phase by `e^(i*pi*0.25)` when `q0` is 1. That is a T gate. Angles that
are multiples of 0.5 are Clifford and free, and the cost rules on the
[costs page](costs-and-mbuc.md) say what the other angles cost.

`HMR` is the instruction behind measurement-based uncomputation. When it runs, the simulator picks
the measurement bit at random. If the qubit held 1, the random bit flips the global phase. A later
`CZ ... if b0` can cancel that flip, but only if you wrote the right correction.

## The text format

The text format, `.kmx`, is one instruction per line. You can pass it straight to `km.Circuit`.

```python
c = km.Circuit("""
    X q0
    CX q0 q1
    CCX q0 q1 q2
    HMR q2 b0
    CZ q0 q1 if b0
""")

print(c)
print(len(c), "instructions,", c.num_qubits, "qubits,", c.num_bits, "bits")
print(c.text_diagram())
```

```text
X q0
CX q0 q1
CCX q0 q1 q2
HMR q2 b0
CZ q0 q1 if b0
5 instructions, 3 qubits, 1 bits
q0: -X-@-@--------@-----
       | |        |
q1: ---X-@--------Z**b0-
         |
q2: -----X-HMR=b0
```

`print(c)` gives the text back, `text_diagram()` draws it, and `html_diagram()` and
`flame_chart_svg()` give richer views. `c.operation_statistics()` counts instructions:

```python
stats = c.operation_statistics()
print(stats.num_toffoli_like, "Toffoli-like gates,", stats.num_t_like, "T-like gates")
print(dict(stats.items()))
```

```text
1 Toffoli-like gates, 0 T-like gates
{'X': 1, 'HMR': 1, 'CX': 1, 'CZ': 1, 'CCX': 1}
```

A misspelled instruction raises `ValueError: Failed to parse kmx line (unknown operation name)`.

### Registers

The verifiers find your qubits by register name. A circuit that scores must name its registers the
way the benchmark expects, and the text format does that with two instruction kinds:

```python
named = km.Circuit("""
    REGISTER r0 "data"
    APPEND_TO_REGISTER q0 r0
    APPEND_TO_REGISTER q1 r0
    CX q0 q1
""")
print(named.register_data)
```

```text
{'data': km.array([km.q(0), km.q(1)])}
```

You rarely write these by hand. The builder, below, creates them.

## The binary format

Large circuits do not fit comfortably as text. The `dqi` baseline has about 86 million instructions
and is 886 MB even in binary. The binary format, `.kmb`, stores the instruction arrays as raw blocks.
You choose the format when you write:

```python
import pathlib
import tempfile

workdir = pathlib.Path(tempfile.mkdtemp())

c.to_file(workdir / "a.kmx")  # text
c.to_file(workdir / "b.kmb", format="kmb")  # binary

print((workdir / "a.kmx").read_bytes()[:12])
print((workdir / "b.kmb").read_bytes()[:12] != b"X q0\nCX q0 q")
print(km.Circuit.from_file(workdir / "b.kmb") == c)
```

```text
b'X q0\nCX q0 q1'
True
True
```

(For a tiny circuit the binary file is not smaller. The saving appears at scale, and so does the load
speed.) The competition also reads `.kmx` files, so either format is a valid submission.

### The pitfall

`Circuit.to_file(path)` writes text unless you pass `format="kmb"`. Naming the file `x.kmb` does not
change that. The file below is text with a binary extension:

```python
fake = workdir / "oops.kmb"
c.to_file(fake)  # no format=, so this is text

print(km.Circuit.from_file(fake) == c)  # format='auto' sniffs it and loads fine
try:
    km.Circuit.from_file(fake, format="kmb")
except ValueError as e:
    print(e)
```

```text
True
File didn't start with the magic bytes identifying a kickmix binary format file.
```

Locally this looks fine, because `from_file` detects the real format by default. The competition notes
say the metric rejects such a file without a useful message. So whenever you write a file you plan to
submit, pass `format="kmb"` and read it back with `format="kmb"`, which fails loudly if you got it
wrong. `bench pack` does not check this; the verifier does.

## The builder API

Writing instructions by hand does not scale. `km.CircuitBuilder` is a Python object you call methods
on, and it returns the finished circuit. The calls fall into five groups.

**Wires.** `create_quantum_register(n, name)` makes `n` named qubits and returns them as a
`km.array`. `alloc_qubits(n)` makes anonymous scratch qubits, and `free(...)` hands them back so a
later allocation can reuse them. The circuit's qubit count is the high-water mark, so freeing early
is how you keep `Q` down. `alloc_bits` and `create_classical_register` do the same for classical
bits.

**Gates.** `x`, `cx`, `ccx`, `cz`, `ccz`, `swap`, `cswap`, `z`, `z_pow`, `reset`, and `hmr`. They
broadcast like numpy: pass one array and one qubit, or two arrays of equal length, and you get one
instruction per element. Pass a plain `True` for a control and the builder drops it, so
`builder.ccx(True, a, t)` becomes a `CX`.

**Compute and uncompute pairs.** `init_and(a, b, t)` resets `t` and computes `a AND b` into it with
one Toffoli. `del_and(a, b, t)` clears it again with `HMR` and a corrected `CZ`, which is the
[MBUC trick](costs-and-mbuc.md) packaged as a call. It costs no Toffoli. The same pairing exists for
lookups (`init_lookup` / `del_lookup`) and finite-field arithmetic (`init_gf2_mul` / `del_gf2_mul`,
and others).

**Library routines.** `iadd` and `isub` for addition, `flip_if_less_than` and friends for
comparison, `init_lookup` for table reads, `unary_iteration`, `gf2_*` for finite-field arithmetic.
Each emits a tested instruction sequence, usually with its own scratch qubits.

**Bookkeeping.** `with builder.mark("name"):` wraps a block in `INFO_TAG` labels, which
`flame_chart_svg()` turns into a picture of where the Toffolis and qubits go.
`set_max_qubits(n)` makes any allocation past `n` raise an error, which is a cheap way to hold a
qubit budget.

Here is the library adder on two 4-bit registers:

```python
builder = km.CircuitBuilder()
a = builder.create_quantum_register(4, "a")
b = builder.create_quantum_register(4, "b")
builder.iadd(a, target=b)  # b += a, modulo 16
library_adder = builder.finish_circuit()

stats = library_adder.operation_statistics()
print(library_adder.num_qubits, "qubits,", stats.num_toffoli_like, "Toffolis")
```

```text
10 qubits, 3 Toffolis
```

Eight qubits for the registers and two scratch qubits for carries. Three Toffolis for four bits: a
ripple-carry adder needs one AND per bit except the last.

## Simulating a circuit

`km.Simulator(batch_size=n)` runs `n` independent shots at once. Each shot has its own value for
every qubit and bit and its own phase. You write inputs, run the circuit, and read results back.

```python
import numpy as np

sim = km.Simulator(batch_size=2, seed=0)
sim.write_across_shots(km.q(0), 0b01)  # q0 is 1 in shot 0 and 0 in shot 1
sim.do(km.Circuit("CX q0 q1"))
print(sim.read_across_shots(km.q(1)))
```

```text
[ True False]
```

`write_across_shots(index, value)` takes either an int (bit `k` is the value in shot `k`) or a boolean
numpy array. For a register of `n` qubits, pass an array of shape `(n, batch_size)`. Registers can be
addressed by name after `sim.use_same_registers_as(circuit)`. `read_phase_flipped_across_shots()`
returns, per shot, whether the global phase ended up negated, and `seed=` makes the `HMR` and `R`
coin flips repeatable. The official verifiers seed them from a hash of the circuit, so you cannot pick
a lucky seed.

## Build and verify a 4-bit adder

The task: a circuit that, given 4-bit registers `a` and `b`, leaves `a` unchanged and replaces `b`
with `(a + b) mod 16`, using exactly 3 Toffolis and returning every scratch qubit to 0.

This is the Gidney ripple-carry adder. Each bit position `i` except the last computes a carry
`c[i]` with one `init_and`, and the carries are cleared on the way back with `del_and`. Write
`a'` and `b'` for `a[i]` and `b[i]` after XORing the previous carry into both. Then the carry out is

```text
c[i] = (a[i] ^ c[i-1]) & (b[i] ^ c[i-1])  ^  c[i-1]
```

which is a single AND plus two XORs, and XORs are free CX gates.

```python
def adder(n=4):
    bd = km.CircuitBuilder()
    a = bd.create_quantum_register(n, "a")
    b = bd.create_quantum_register(n, "b")
    c = bd.alloc_qubits(n - 1)  # carries

    for i in range(n - 1):  # forward pass: compute carries
        if i:
            bd.cx(c[i - 1], a[i])
            bd.cx(c[i - 1], b[i])
        bd.init_and(a[i], b[i], c[i])
        if i:
            bd.cx(c[i - 1], c[i])

    bd.cx(a[n - 1], b[n - 1])  # top bit of the sum
    bd.cx(c[n - 2], b[n - 1])

    for i in reversed(range(n - 1)):  # backward pass: clear carries, finish sum bits
        if i:
            bd.cx(c[i - 1], c[i])
        bd.del_and(a[i], b[i], c[i])  # HMR plus a CZ fix, no Toffoli
        if i:
            bd.cx(c[i - 1], a[i])  # restore a[i]
        bd.cx(a[i], b[i])  # b[i] now holds a ^ b ^ carry-in
    return bd.finish_circuit()


circuit = adder()
stats = circuit.operation_statistics()
print(circuit.num_qubits, "qubits,", stats.num_toffoli_like, "Toffolis")
```

```text
11 qubits, 3 Toffolis
```

Run `print(circuit.text_diagram())` and read it left to right. The three `|0>` rows at the bottom are
the carry qubits. Each is set by a Toffoli on the way out, and each ends in an `HMR=b0` box with a
`Z**b0` (a controlled phase fix) on the way back.

Eleven qubits is the two registers plus three carries. The library `iadd` above uses 10 for the same
Toffoli count. That one-qubit gap is the shape of a real optimisation in this competition, and
exercise 2 closes it.

### Verify it

There are only 256 inputs, so we can test all of them in one batch of 256 shots. Shot `s` gets
`a = s % 16` and `b = s // 16`. For a circuit to pass, four things must hold in every shot:

1. `a` is unchanged.
2. `b` equals `(a + b) mod 16`.
3. Every scratch qubit is 0.
4. The phase did not flip.

```python
def to_bits(values, width):
    """Shape (width, shots) boolean array, least significant bit first."""
    return ((values[None, :] >> np.arange(width)[:, None]) & 1).astype(bool)


def to_ints(bit_rows):
    return (bit_rows * (1 << np.arange(len(bit_rows)))[:, None]).sum(axis=0)


def check_adder(circuit, n=4, seed=1):
    shots = np.arange(4**n)  # every (a, b) pair once
    a_in, b_in = shots % 2**n, shots // 2**n

    sim = km.Simulator(batch_size=len(shots), seed=seed)
    sim.use_same_registers_as(circuit)
    sim.write_across_shots("a", to_bits(a_in, n))
    sim.write_across_shots("b", to_bits(b_in, n))
    sim.do(circuit)

    a_out = to_ints(sim.read_across_shots("a"))
    b_out = to_ints(sim.read_across_shots("b"))
    scratch = km.array([km.q(k) for k in range(2 * n, circuit.num_qubits)])
    dirty = sim.read_across_shots(scratch).any(axis=0)
    return {
        "a changed": int((a_out != a_in).sum()),
        "wrong sums": int((b_out != (a_in + b_in) % 2**n).sum()),
        "dirty scratch": int(dirty.sum()),
        "phase flips": int(sim.read_phase_flipped_across_shots().sum()),
    }


result = check_adder(circuit)
print(result)
assert not any(result.values())
```

```text
{'a changed': 0, 'wrong sums': 0, 'dirty scratch': 0, 'phase flips': 0}
```

The adder is exactly correct. Because the input space is small, this is a proof, not a sample. The
real verifiers cannot enumerate `2^50` inputs, so they sample, which is what
[classical verification](classical-verification.md) is about.

A passing circuit also matches the library one. The two have the same Toffoli count:

```python
print(library_adder.operation_statistics().num_toffoli_like == stats.num_toffoli_like)
```

## Break it and watch it fail

A verifier is only useful if it fails when it should. We break the adder three ways. In each case we
edit the circuit text, which is also how you would try a hand optimisation on a circuit someone else
built.

```python
def without(circuit, drop):
    """Rebuild a circuit with the instruction lines that satisfy `drop` removed."""
    lines = [ln.strip() for ln in str(circuit).splitlines()]
    return km.Circuit("\n".join(ln for ln in lines if not drop(ln)))
```

**Break 1: forget the phase correction.** Remove every `CZ ... if b0` that `del_and` emitted. The
carry qubits still go back to 0 and the sums are right, but the `HMR` coin flips are no longer
cancelled.

```python
no_fix = without(circuit, lambda ln: ln.startswith("CZ"))
result = check_adder(no_fix)
print(result)
assert result["phase flips"] > 0 and result["wrong sums"] == 0
```

```text
{'a changed': 0, 'wrong sums': 0, 'dirty scratch': 0, 'phase flips': 63}
```

The register contents are perfect and the circuit still fails: about a quarter of the shots flip
phase. A coherent run would have the wrong sign on those branches, which ruins any interference that
follows. This is the failure the official verifiers catch and the main way an MBUC-based
optimisation goes wrong. (The exact count depends on the seed. It is always nonzero for this circuit
because there are carries that really are 1 in some shots.)

**Break 2: remove a carry XOR.** Delete one `CX` on the carry chain. Now the carry into a later bit is
wrong.

```python
broken_carry = without(circuit, lambda ln: ln == "CX q8 q9")
result = check_adder(broken_carry)
print(result)
assert result["wrong sums"] > 0
```

```text
{'a changed': 0, 'wrong sums': 64, 'dirty scratch': 0, 'phase flips': 0}
```

A quarter of the inputs give the wrong sum. Reading the failure tells you where to look: wrong sums
with clean scratch qubits means the logic is wrong, not the cleanup.

**Break 3: leave a carry qubit dirty.** Remove the `HMR` and `CZ` pairs, so the carries are never
cleared.

```python
dirty_circuit = without(circuit, lambda ln: ln.startswith(("HMR", "CZ")))
result = check_adder(dirty_circuit)
print(result)
assert result["dirty scratch"] > 0 and result["wrong sums"] == 0
```

```text
{'a changed': 0, 'wrong sums': 0, 'dirty scratch': 148, 'phase flips': 0}
```

The answer is right and the circuit would still be rejected, because scratch qubits must end at 0.
The competition verifiers also fail a circuit that leaves junk behind, and a stray `R` on a qubit
holding 1 flips the phase at random, so even a rough attempt to hide junk is caught.

## Exercises

1. Generalise: build `adder(6)` and check it with `check_adder(circuit, n=6)`. How many Toffolis and
   qubits does it use, and how many shots does the check run?
2. The library adder uses one carry qubit fewer than ours. Look at the last `CCX` in
   `print(library_adder)`: its target is a bit of `b`, not a carry qubit. Rewrite the last position
   of `adder` so the top sum bit takes the final AND directly, and verify the result with
   `check_adder`. What is the new qubit count?
3. Run the three breaks in a single loop over `(name, drop_predicate)` pairs and print one row each.
   Then invent a fourth break (for example, drop the `CX` that restores `a[i]`) and predict which of
   the four columns goes nonzero before you run it.
4. Wrap the adder body in `with bd.mark("adder"):`, write `circuit.flame_chart_svg()` to a file and
   open it in a browser. What does it show you?

??? note "Solutions"

    **1.** One AND per bit except the last, so 5 Toffolis, 6 + 6 + 5 = 17 qubits, and
    `4**6 = 4096` shots.

    ```python
    big = adder(6)
    print(big.num_qubits, big.operation_statistics().num_toffoli_like)
    print(check_adder(big, n=6))
    ```

    **2.** Position `n - 2` needs the carry out only to flip the top sum bit, so a plain `ccx` into
    `b[n - 1]` does the job and the last carry qubit disappears. Everything else is unchanged.

    ```python
    def short_adder(n=4):
        bd = km.CircuitBuilder()
        a = bd.create_quantum_register(n, "a")
        b = bd.create_quantum_register(n, "b")
        c = bd.alloc_qubits(n - 2)
        for i in range(n - 2):
            if i:
                bd.cx(c[i - 1], a[i])
                bd.cx(c[i - 1], b[i])
            bd.init_and(a[i], b[i], c[i])
            if i:
                bd.cx(c[i - 1], c[i])
        k = n - 2
        bd.cx(c[k - 1], a[k])
        bd.cx(c[k - 1], b[k])
        bd.ccx(a[k], b[k], b[n - 1])  # last carry goes straight into the top sum bit
        bd.cx(c[k - 1], a[k])  # restore a[k]
        bd.cx(a[k], b[k])  # sum bit k
        bd.cx(c[k - 1], b[n - 1])
        bd.cx(a[n - 1], b[n - 1])
        for i in reversed(range(n - 2)):
            if i:
                bd.cx(c[i - 1], c[i])
            bd.del_and(a[i], b[i], c[i])
            if i:
                bd.cx(c[i - 1], a[i])
            bd.cx(a[i], b[i])
        return bd.finish_circuit()


    short = short_adder()
    print(short.num_qubits, short.operation_statistics().num_toffoli_like)
    print(check_adder(short))
    ```

    That is 10 qubits and 3 Toffolis, matching the library adder.

    **3.** Dropping the restoring `CX` leaves `a` changed in some shots, so `a changed` goes nonzero.
    Dropping the last `cx(a[i], b[i])` of one bit gives wrong sums and nothing else.

    **4.** With a single marked block you get one bar, which tells you little. Marks pay off when
    you nest them, one per subroutine, as the reference circuits do.
