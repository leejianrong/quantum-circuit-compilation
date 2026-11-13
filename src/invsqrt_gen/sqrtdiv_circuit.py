"""The full square-root-and-division circuit (QCC-13): forward program, phase section, mirror."""

from dataclasses import dataclass
from typing import Any

import kickmix as km  # type: ignore[import-not-found,unused-ignore]
import numpy as np

from invsqrt_gen.rec import Binding, Rec, inverse, replay
from invsqrt_gen.split import barrel_phase
from invsqrt_gen.sqrtdiv import SdTables, reachable_n
from invsqrt_gen.sqrtdiv_build import nr_model
from invsqrt_gen.sqrtdiv_stages import (
    divide_rows,
    finish_root,
    load_table,
    normalise_even,
    numerator_inplace,
    numerator_window,
    product,
    product_pm1,
    refine_d,
    sqrt_root,
)

F_BITS = 37


@dataclass
class Program:
    ops: list[tuple[Any, ...]]
    flags: list[int]
    q: list[int]
    gs: list[int]


def forward_program(
    tab: SdTables,
    digits: int = 27,
    release_table: bool = True,
    inplace: bool = True,
    pm1: bool = True,
    trace: list[tuple[str, int, int, int]] | None = None,
) -> Program:
    _, _, widths = nr_model(reachable_n())
    r = Rec(22)
    x = list(range(22))

    def mark(name: str) -> None:
        if trace is not None:
            trace.append((name, r.live, r.peak, len(r.ops)))

    flags = normalise_even(r, x)
    mark("normalise")
    q, w, zeros = sqrt_root(r, x, widths)
    mark("root")
    t = finish_root(r, q, w, zeros)
    mark("finish")
    d_bits = int(tab.d0.max()).bit_length()
    e_bits = int(tab.e.max()).bit_length()
    words = [int(a) | (int(b) << d_bits) for a, b in zip(tab.d0, tab.e, strict=True)]
    dw, ew = load_table(r, q, words, d_bits, e_bits)
    mark("lookup")
    a0 = len(r.ops)
    refine_d(r, q, dw, ew)
    a1 = len(r.ops)
    mark("refine")
    p = product_pm1(r, t, dw, 17) if pm1 else product(r, t, dw, 17, tab.fd - tab.fp, init_minus_one=inplace)
    if (
        release_table
    ):  # D and E are not needed while dividing: undo the refinement, clear the lookup by measurement
        r.ops.extend(inverse(r.ops[a0:a1]))
        r.lookup(words, q[5:12], dw + ew, inverse=True)
        r.free(dw + ew)
    mark("product")
    wn = numerator_inplace(r, q, p, tab.fp) if inplace else numerator_window(r, q, p, tab.fp)
    mark("numerator")
    gs, _ = divide_rows(r, q, wn, tab.fp, digits)
    mark("divide")
    return Program(r.ops, flags, q, gs)


def build_circuit(
    tab: SdTables, digits: int = 27, release_table: bool = True, inplace: bool = True, pm1: bool = True
) -> km.Circuit:
    prog = forward_program(tab, digits, release_table, inplace, pm1)
    b = km.CircuitBuilder()
    xr = b.create_quantum_register(22, name="x")
    bind = Binding({i: xr[i] for i in range(22)})
    replay(b, prog.ops, bind)
    shift = km.array([bind[f] for f in prog.flags])  # k bits: flag j shifts by 2^j
    word = [bind[g] for g in reversed(prog.gs)] + [bind[prog.q[12]]]  # b_27 .. b_2, b_1 at positions 1 .. 27
    width = len(word)
    head = b.alloc_qubits(10)
    barrel_phase(b, km.array(word + list(head)), shift, width, 1, F_BITS, 1)
    b.free(head)
    for base, sign in ((F_BITS - 10, -1), (0, 1)):  # the constants -2^(k-10) and +2^(k-10-digits)
        c = b.alloc_qubits(1)
        b.x(c)
        head = b.alloc_qubits(10)
        barrel_phase(b, km.array(list(c) + list(head)), shift, 1, base, F_BITS, sign)
        b.free(head)
        b.x(c)
        b.free(c)
    mirror = Binding(bind)
    mirror.store = bind.store
    replay(b, inverse(prog.ops), mirror)
    return b.finish_circuit()


def expected_half_turns(x: np.ndarray) -> np.ndarray:
    k = np.array([(22 - int(v).bit_length()) // 2 for v in x])
    return np.asarray(2.0 * (2.0 ** (k - 10)) / np.sqrt((x << (2 * k)) / 2.0**20), dtype=np.float64)


def executed_toffolis(c: km.Circuit) -> float:
    """Expected executed Toffoli-like gates (under `d` nested conditions a gate runs on `2^-d` of shots)."""
    total = 0.0
    depth = 0
    for line in repr(c).splitlines():
        parts = line.split()
        op = parts[0] if parts else ""
        if op == "PUSH_CONDITION":
            depth += 1
        elif op == "POP_CONDITION":
            depth -= 1
        elif op in ("CCX", "CCZ", "CSWAP"):
            total += 0.5**depth
    return total
