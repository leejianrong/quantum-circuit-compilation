# ruff: noqa: E501
"""A tiny recorder with automatic inverse (QCC-13), so every stage is written once.

`Rec` has the builder methods our gadgets call (`x`, `cx`, `ccx`, `cswap`, `init_and`, `del_and`, `z`, `cz`,
`alloc_qubits`, `free`) on virtual qubits (plain ints; arrays are lists). `replay` runs a recorded program on a real
`km.CircuitBuilder`; `inverse` reverses a program and inverts each op: `init_and` and `del_and` swap (a measured
clean-up is the inverse of the compute and the other way round, at the same Toffoli cost), `alloc` and `free` swap,
`lookup` and `del_lookup` swap, and a macro carries its own inverse (the deferred-phase adder pair, the phase section).

Programs are lists of tuples, so they are easy to count and to test.
"""

from collections.abc import Callable
from typing import Any

import kickmix as km  # type: ignore[import-not-found,unused-ignore]

Op = tuple[Any, ...]


class Rec:
    """Records builder calls on virtual qubits."""

    def __init__(self, n_fixed: int = 0) -> None:
        self.ops: list[Op] = []
        self.n = n_fixed  # virtual ids 0 .. n_fixed - 1 are bound to existing qubits by the caller
        self.live = n_fixed
        self.peak = n_fixed

    # -- allocation
    def alloc_qubits(self, k: int) -> list[int]:
        qs = list(range(self.n, self.n + k))
        self.n += k
        self.live += k
        self.peak = max(self.peak, self.live)
        self.ops.extend(("alloc", q) for q in qs)
        return qs

    def free(self, qs: Any) -> None:
        qs = [qs] if isinstance(qs, int) else list(qs)
        self.live -= len(qs)
        self.ops.extend(("free", q) for q in qs)

    # -- gates (arrays broadcast over the target)
    def x(self, t: Any) -> None:
        self.ops.extend(("x", q) for q in ([t] if isinstance(t, int) else list(t)))

    def cx(self, c: int, t: Any) -> None:
        self.ops.extend(("cx", c, q) for q in ([t] if isinstance(t, int) else list(t)))

    def ccx(self, a: int, b: int, t: int) -> None:
        self.ops.append(("ccx", a, b, t))

    def cswap(self, c: int, a: int, b: int) -> None:
        self.ops.append(("cswap", c, a, b))

    def init_and(self, a: int, b: int, out: int) -> None:
        self.ops.append(("init_and", a, b, out))

    def del_and(self, a: int, b: int, out: int) -> None:
        self.ops.append(("del_and", a, b, out))

    def z(self, q: int) -> None:
        self.ops.append(("z", q))

    def cz(self, a: int, b: int) -> None:
        self.ops.append(("cz", a, b))

    # -- high-level
    def lookup(self, table: list[int], address: list[int], target: list[int], inverse: bool = False) -> None:
        self.ops.append(("del_lookup" if inverse else "lookup", table, list(address), list(target)))

    def macro(self, fwd: Callable[..., Any], inv: Callable[..., Any], *args: Any) -> None:
        """`fwd(b, binding, *real_args)` and its inverse `inv(...)`; the args are qubit ids or lists of ids."""
        self.ops.append(("macro", fwd, inv, args))


_SELF = {"x", "cx", "ccx", "cswap", "z", "cz"}
_SWAP = {
    "init_and": "del_and",
    "del_and": "init_and",
    "alloc": "free",
    "free": "alloc",
    "lookup": "del_lookup",
    "del_lookup": "lookup",
}


def inverse(ops: list[Op]) -> list[Op]:
    out: list[Op] = []
    for op in reversed(ops):
        k = op[0]
        if k in _SELF:
            out.append(op)
        elif k == "macro":
            out.append(("macro", op[2], op[1], op[3]))
        else:
            out.append((_SWAP[k], *op[1:]))
    return out


class Binding(dict[int, Any]):
    """Virtual id to real qubit, plus a scratch store for macros (classical bits of deferred adders)."""

    def __init__(self, *a: Any, **k: Any) -> None:
        super().__init__(*a, **k)
        self.store: dict[Any, Any] = {}


def _real(bind: Binding, a: Any) -> Any:
    if isinstance(a, int):
        return bind[a]
    if isinstance(a, list):
        return [_real(bind, v) for v in a]
    return a


def replay(b: km.CircuitBuilder, ops: list[Op], bind: Binding) -> Binding:
    """Run `ops` on the real builder; qubits allocated here are added to `bind`."""
    for op in ops:
        k = op[0]
        if k == "alloc":
            bind[op[1]] = b.alloc_qubits(1)[0]
        elif k == "free":
            b.free(km.array([bind.pop(op[1])]))
        elif k == "x":
            b.x(bind[op[1]])
        elif k == "cx":
            b.cx(bind[op[1]], bind[op[2]])
        elif k == "ccx":
            b.ccx(bind[op[1]], bind[op[2]], bind[op[3]])
        elif k == "cswap":
            b.cswap(bind[op[1]], bind[op[2]], bind[op[3]])
        elif k == "init_and":
            b.init_and(bind[op[1]], bind[op[2]], bind[op[3]])
        elif k == "del_and":
            b.del_and(bind[op[1]], bind[op[2]], bind[op[3]])
        elif k == "z":
            b.z(bind[op[1]])
        elif k == "cz":
            b.cz(bind[op[1]], bind[op[2]])
        elif k == "lookup":
            b.init_lookup(
                table=op[1], address=km.array(_real(bind, op[2])), target=km.array(_real(bind, op[3]))
            )
        elif k == "del_lookup":
            b.del_lookup(
                table=op[1], address=km.array(_real(bind, op[2])), target=km.array(_real(bind, op[3]))
            )
        elif k == "macro":
            op[1](b, bind, *[_real(bind, a) for a in op[3]])
        else:
            raise ValueError(k)
    return bind
