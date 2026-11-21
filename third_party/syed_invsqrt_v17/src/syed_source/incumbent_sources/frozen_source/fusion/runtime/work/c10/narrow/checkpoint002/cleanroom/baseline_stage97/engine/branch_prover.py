"""Independent exhaustive checker for small generated kickmix windows.

Copyright 2026 Syed Asad Ali (team syed3000)
Licensed under the Apache License, Version 2.0.

No compiled reference circuit is loaded here.  Pass the text emitted by our own
generator.  The checker assigns every input and every syntactic HMR outcome,
tracks exact rational phase in half turns, and checks the final state.  An R is
accepted only on a provably zero qubit, which makes every possible discarded
measurement outcome harmless.  This deliberate restriction catches accidental
use of reset as irreversible erasure.

For computational basis t, an HMR with outcome m contributes (-1)**(m*t)
before resetting t.  The checker implements this directly, independently of
kickmix.  Inactive conditional HMRs consume their reserved transcript bit but
do nothing; enumeration therefore covers every possible active transcript.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import io
import itertools
import math
import shlex
from typing import Callable, Mapping, Sequence


@dataclass(frozen=True)
class Operation:
    kind: str
    arguments: tuple[str, ...]
    condition: str | None = None
    half_turns: Fraction | None = None
    event: int | None = None


def generated_text(circuit) -> str:
    """Serialize a circuit produced by this task; never takes a reference path."""
    stream = io.StringIO()
    circuit.to_file(stream, format="kmx")
    return stream.getvalue()


class Program:
    """Exact bit/phase semantics for the small gate set used by our kernels."""

    def __init__(self, text: str):
        self.operations = []
        self.registers = {}
        register_ids = {}
        self.wires = set()
        self.measurements = 0
        denominators = [1]
        ignored = {"INFO_TAG", "DEBUG_PRINT"}
        arities = {"X": 1, "CX": 2, "CCX": 3, "SWAP": 2, "CSWAP": 3,
                   "Z": 1, "CZ": 2, "CCZ": 3, "NEG": 0, "HMR": 2, "R": 1,
                   "Z_POW": 2, "BIT_STORE0": 1, "BIT_STORE1": 1,
                   "BIT_INVERT": 1,
                   "PUSH_CONDITION": 0, "POP_CONDITION": 0}
        for number, line in enumerate(text.splitlines(), 1):
            tokens = shlex.split(line, comments=True)
            if not tokens:
                continue
            kind, *arguments = tokens
            if kind in ignored:
                continue
            if kind == "APPEND_TO_REGISTER":
                register_ids.setdefault(arguments[1], []).append(arguments[0])
                continue
            if kind == "REGISTER":
                self.registers[arguments[1]] = register_ids[arguments[0]]
                continue
            condition = None
            if "if" in arguments:
                index = arguments.index("if")
                if index != len(arguments) - 2:
                    raise ValueError(f"Unsupported condition on line {number}: {line}")
                condition = arguments[-1]
                arguments = arguments[:index]
                self.wires.add(condition)
            if kind not in arities or len(arguments) != arities[kind]:
                raise ValueError(f"Unsupported instruction on line {number}: {line}")
            angle = None
            if kind == "Z_POW":
                angle = Fraction(arguments[-1])
                arguments = arguments[:-1]
                denominators.append(angle.denominator)
            event = None
            if kind == "HMR":
                event = self.measurements
                self.measurements += 1
            self.wires.update(arguments)
            self.operations.append(Operation(kind, tuple(arguments), condition, angle, event))
        self.denominator = math.lcm(*denominators)
        self.modulus = 2 * self.denominator
        self.phase_steps = {
            i: int(op.half_turns * self.denominator)
            for i, op in enumerate(self.operations) if op.kind == "Z_POW"
        }

    @property
    def quantum_wires(self):
        return sorted((wire for wire in self.wires if wire.startswith("q")),
                      key=lambda item: int(item[1:]))

    def execute(self, initial: Mapping[str, int], transcript: int = 0):
        state = {wire: 0 for wire in self.wires}
        state.update(initial)
        state["0"], state["1"] = 0, 1
        state["False"], state["True"] = 0, 1
        phase = 0
        stack = [True]
        den = self.denominator
        for index, op in enumerate(self.operations):
            k, a = op.kind, op.arguments
            active = stack[-1] and (op.condition is None or bool(state[op.condition]))
            if k == "PUSH_CONDITION":
                stack.append(active)
                continue
            if k == "POP_CONDITION":
                if len(stack) == 1:
                    raise AssertionError("Unmatched POP_CONDITION")
                stack.pop()
                continue
            if not active:
                continue
            if k == "X":
                state[a[0]] ^= 1
            elif k == "CX":
                state[a[1]] ^= state[a[0]]
            elif k == "CCX":
                state[a[2]] ^= state[a[0]] & state[a[1]]
            elif k == "SWAP":
                state[a[0]], state[a[1]] = state[a[1]], state[a[0]]
            elif k == "CSWAP":
                if state[a[0]]:
                    state[a[1]], state[a[2]] = state[a[2]], state[a[1]]
            elif k in ("Z", "CZ", "CCZ", "NEG"):
                phase += den * math.prod(state[wire] for wire in a)
            elif k == "Z_POW":
                phase += self.phase_steps[index] * state[a[0]]
            elif k == "HMR":
                outcome = (transcript >> op.event) & 1
                phase += den * outcome * state[a[0]]
                state[a[0]] = 0
                state[a[1]] = outcome
            elif k == "R":
                if state[a[0]]:
                    raise AssertionError(
                        f"Reset would erase nonzero {a[0]} at instruction {index}; "
                        f"input={dict(initial)}, HMR transcript={transcript}")
            elif k == "BIT_STORE0":
                state[a[0]] = 0
            elif k == "BIT_STORE1":
                state[a[0]] = 1
            elif k == "BIT_INVERT":
                state[a[0]] ^= 1
            else:
                raise AssertionError(k)
        if len(stack) != 1:
            raise AssertionError("Unclosed condition stack")
        return state, Fraction(phase % self.modulus, den)

    def execute_symbolic_measurements(self, initial: Mapping[str, int]):
        """Prove all transcripts at once when quantum data is branch independent.

        Measurement-dependent phases are exact multilinear polynomials over
        integer coefficients modulo the phase period.  A monomial is indexed
        by a bit mask of measurement variables.  Multiplication uses Boolean
        idempotence m*m=m.  Vanishing of every coefficient is equivalent to
        vanishing on the complete Boolean cube, by the invertible Mobius
        transform.  This route needs no assumptions about how often any
        outcome occurs.  Measurement-conditioned data gates are rejected;
        `execute` plus exhaustive transcript enumeration handles those cases.
        """
        modulus, den = self.modulus, self.denominator

        def plus(left, right):
            result = dict(left)
            for monomial, coefficient in right.items():
                total = (result.get(monomial, 0) + coefficient) % modulus
                if total:
                    result[monomial] = total
                else:
                    result.pop(monomial, None)
            return result

        def multiply(left, right):
            result = {}
            for a, ca in left.items():
                for b, cb in right.items():
                    monomial = a | b
                    result[monomial] = (result.get(monomial, 0) + ca * cb) % modulus
            return {key: value for key, value in result.items() if value}

        def times(poly, factor):
            return {key: value * factor % modulus for key, value in poly.items()
                    if value * factor % modulus}

        state = {wire: 0 for wire in self.wires}
        state.update(initial)
        state.update({"0": 0, "1": 1, "False": 0, "True": 1})
        classical = {wire: ({0: int(value)} if value else {})
                     for wire, value in state.items() if wire.startswith("b")}
        phase = {}
        stack = [{0: 1}]
        for index, op in enumerate(self.operations):
            kind, args = op.kind, op.arguments
            condition = stack[-1]
            if op.condition is not None:
                condition = multiply(condition, classical[op.condition])
            if kind == "PUSH_CONDITION":
                stack.append(condition)
                continue
            if kind == "POP_CONDITION":
                if len(stack) == 1:
                    raise AssertionError("Unmatched POP_CONDITION")
                stack.pop()
                continue
            if not condition:
                continue
            if kind in ("Z", "CZ", "CCZ", "Z_POW", "NEG"):
                coefficient = self.phase_steps[index] if kind == "Z_POW" else den
                coefficient *= math.prod(state[wire] for wire in args)
                phase = plus(phase, times(condition, coefficient))
                continue
            if kind in ("BIT_STORE0", "BIT_STORE1"):
                previous = classical.get(args[0], {})
                # out=(1-condition)*previous+condition*new_bit.
                classical[args[0]] = plus(previous, times(multiply(condition, previous), -1))
                if kind == "BIT_STORE1":
                    classical[args[0]] = plus(classical[args[0]], condition)
                continue
            if kind == "BIT_INVERT":
                previous = classical.get(args[0], {})
                classical[args[0]] = plus(plus(previous, condition),
                                          times(multiply(previous, condition), -2))
                continue
            if condition != {0: 1}:
                raise ValueError(f"Quantum data depends on a measurement at operation {index}; "
                                 "use explicit exhaustive transcript enumeration")
            if kind == "X":
                state[args[0]] ^= 1
            elif kind == "CX":
                state[args[1]] ^= state[args[0]]
            elif kind == "CCX":
                state[args[2]] ^= state[args[0]] & state[args[1]]
            elif kind == "SWAP":
                state[args[0]], state[args[1]] = state[args[1]], state[args[0]]
            elif kind == "CSWAP":
                if state[args[0]]:
                    state[args[1]], state[args[2]] = state[args[2]], state[args[1]]
            elif kind == "R":
                if state[args[0]]:
                    raise AssertionError(f"Reset of dirty {args[0]} at operation {index}")
            elif kind == "HMR":
                outcome = {1 << op.event: 1}
                phase = plus(phase, times(outcome, den * state[args[0]]))
                state[args[0]] = 0
                classical[args[1]] = outcome
            else:
                raise AssertionError(kind)
        if len(stack) != 1:
            raise AssertionError("Unclosed condition stack")
        return state, {monomial: Fraction(coefficient, den)
                       for monomial, coefficient in phase.items()}


def exhaustively_check(program: Program, input_wires: Sequence[str],
                       expected: Callable[[Mapping[str, int]], tuple[Mapping[str, int], Fraction]],
                       *, initial_constants: Mapping[str, int] | None = None,
                       valid_input: Callable[[Mapping[str, int]], bool] | None = None,
                       max_cases: int = 1 << 22):
    """Check output bits, zero scratch, and exact phase for every HMR outcome.

    `expected` returns the complete nonzero-capable output wire mapping and the
    ideal phase in half turns. All quantum wires absent from the mapping must
    be zero. Classical bits are checked only if included explicitly.
    """
    total = 1 << (len(input_wires) + program.measurements)
    if total > max_cases:
        raise ValueError(f"Exhaustive request has {total:,} cases > {max_cases:,}")
    tested = 0
    accepted_inputs = 0
    for bits in itertools.product((0, 1), repeat=len(input_wires)):
        initial = dict(initial_constants or {})
        initial.update(zip(input_wires, bits))
        if valid_input is not None and not valid_input(initial):
            continue
        accepted_inputs += 1
        wanted, ideal_phase = expected(initial)
        ideal_phase %= 2
        for transcript in range(1 << program.measurements):
            final, phase = program.execute(initial, transcript)
            for wire in set(program.quantum_wires) | set(wanted):
                if final.get(wire, 0) != wanted.get(wire, 0):
                    raise AssertionError(
                        f"Output mismatch {wire}: got {final.get(wire, 0)}, "
                        f"expected {wanted.get(wire, 0)}; input={initial}, "
                        f"HMR transcript={transcript}")
            if phase != ideal_phase:
                raise AssertionError(
                    f"Phase mismatch: got {phase} half turns, expected {ideal_phase}; "
                    f"input={initial}, HMR transcript={transcript}")
            tested += 1
    return {"inputs": accepted_inputs, "hmr_events": program.measurements,
            "outcomes_per_input": 1 << program.measurements, "cases": tested,
            "status": "PROVED"}


def integer_of(state, wires):
    return sum(state.get(wire, 0) << bit for bit, wire in enumerate(wires))


def integer_bits(value, wires):
    return {wire: (value >> bit) & 1 for bit, wire in enumerate(wires)}


def symbolic_check(program, input_wires, expected, *, initial_constants=None,
                   valid_input=None):
    """Enumerate data inputs and symbolically prove every measurement outcome."""
    inputs = 0
    for bits in itertools.product((0, 1), repeat=len(input_wires)):
        initial = dict(initial_constants or {})
        initial.update(zip(input_wires, bits))
        if valid_input is not None and not valid_input(initial):
            continue
        inputs += 1
        wanted, ideal_phase = expected(initial)
        state, phase = program.execute_symbolic_measurements(initial)
        for wire in set(program.quantum_wires) | set(wanted):
            if state.get(wire, 0) != wanted.get(wire, 0):
                raise AssertionError(f"Output mismatch at {wire}; input={initial}")
        ideal_phase %= 2
        expected_poly = {0: ideal_phase} if ideal_phase else {}
        if phase != expected_poly:
            raise AssertionError(f"Nonzero phase polynomial {phase}, expected {expected_poly}; "
                                 f"input={initial}")
    return {"status": "PROVED", "inputs": inputs,
            "hmr_events": program.measurements, "outcomes_per_input": 1 << program.measurements,
            "symbolically_proved_cases": inputs * (1 << program.measurements)}


