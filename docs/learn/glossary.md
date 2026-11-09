# Glossary

Terms used in the learning track and in the [competition overview](../COMPETITION.md), in
alphabetical order. Each entry says what the term means here and points to where it is explained.

| Term | Meaning |
|---|---|
| Amplitude | A complex number attached to each basis value of a quantum state. The probability of reading that value is the amplitude's squared magnitude. See [qubits and gates](qubits-and-gates.md). |
| Ancilla | A scratch qubit that starts at 0 and must be returned to 0 before the circuit finishes. See [reversible logic](reversible-logic.md). |
| Basis state | A state with a single definite bit string, such as `\|01>`; a vector with one entry equal to 1 and the rest 0. Also called a computational basis state. |
| Bell state | The two-qubit state `(\|00> + \|11>) / sqrt(2)`. Measuring it gives two equal random bits. |
| Benchmark | One of the three competition targets: `invsqrt`, `dqi` or `dfthcsos`. |
| Bit | A 0 or 1. A basis state of `n` qubits is a string of `n` bits. |
| CNOT | Controlled-NOT: flips a target bit if a control bit is 1. A 4x4 permutation matrix. |
| Collapse | What measurement does to the state: afterwards it is the basis state you read. |
| Cost | The number the verifier returns for a circuit (lower is better), driven by Toffoli count and qubit count. |
| Entanglement | A multi-qubit state that cannot be written as a Kronecker product of single-qubit states, such as the Bell state. |
| Error correction | Encoding a logical qubit in many noisy physical qubits so computation survives errors. It is why each Toffoli is expensive. |
| GHZ state | The generalisation of the Bell state to three or more qubits: `(\|000> + \|111>) / sqrt(2)`. |
| Gate | An operation on qubits, represented by a unitary matrix. |
| Hadamard (`H`) | The one-qubit gate that turns `\|0>` into an equal superposition; `H H = I`. |
| Interference | Amplitudes adding or cancelling when paths recombine, which probabilities cannot do because they are never negative. |
| Kickmix circuit | A circuit of reversible classical gates, phase gates and measurement-based uncomputation, cheap to verify classically. |
| Ket | The notation `\|x>` for a state vector. `\|0>` is `[1, 0]` and `\|1>` is `[0, 1]`. |
| Logical qubit | A qubit as the algorithm sees it, after error correction. The competition counts these. |
| MBUC | Measurement-based uncomputation: measure a scratch qubit and cancel the resulting sign cheaply instead of reversing the computation. See [costs and MBUC](costs-and-mbuc.md). |
| Measurement | Reading a qubit as a classical bit, with probabilities given by the squared amplitudes. |
| NOT (`X`) | Flips a bit; swaps the two amplitudes of a qubit. |
| Phase | A complex factor `e^(i*theta)` on an amplitude; a sign when `theta = pi`. It changes no probabilities by itself but changes what happens under interference. |
| Phase gate | A gate that multiplies the `\|1>` amplitude by a phase. `Z`, `S` and `T` have `theta` of `pi`, `pi/2` and `pi/4`. |
| Phase kickback | A NOT controlled by one qubit, with the target in `\|->`, leaves the target alone and puts a sign on the control's `\|1>` branch. See [reversible logic](reversible-logic.md). |
| QROM | Quantum lookup table over a superposition of addresses. |
| Qubit | A two-level quantum system: a pair of complex amplitudes with squared magnitudes summing to 1. |
| Reversible | Describes a gate or circuit that can be undone, so its input-to-output map is a bijection. |
| Shot | One run of a circuit followed by a measurement. Probabilities are estimated from many shots. |
| Superposition | A state with more than one nonzero amplitude. |
| Toffoli | Controlled-controlled-NOT: flips a target bit if both control bits are 1. With the target at 0 it computes AND. The main expensive gate. |
| Unitary | A matrix with `U† U = I`. It preserves vector length, so probabilities keep summing to 1. |
| Uncomputation | Running a computation backwards to return scratch qubits to 0. |
