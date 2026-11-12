"""Unary-iteration loaders for the dfthcsos angle words (stage 1: from the literature).

Circuit ``k`` of the family is the XOR oracle ``|a>|z> -> |a>|z ^ delta[k, a]>`` on the ``selection``
register ``a`` and ``J`` word registers of ``brot`` qubits (the verifier's contract, see
``data/verifiers/dfthcsos/SCORING_README.md``). The lookup is the unary iteration of Babbush et al.
(arXiv:1805.03662): a binary tree over the address bits whose node controls are temporary ANDs
(one Toffoli each, uncomputed by measurement), with the table words fanned out by CNOTs at the
leaves. Two data-dependent prunings: a subtree whose rows all agree loads once at its root
(Qualtran's break-early), and a subtree whose rows are all zero costs nothing.

The number of Toffolis per circuit is therefore at most ``A - 2`` whatever the word width, so the
lever the model exposes is ``J``: more words per circuit means fewer circuits. ``J`` is capped by
the 128-qubit limit: ``ceil(log2 A) + J * brot + (ceil(log2 A) - 1) <= 128``.

kickmix is imported lazily (it lives in the competition data folder, not on the default path).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np

QUBIT_CAP = 128


def _km() -> Any:
    import kickmix  # type: ignore[import-not-found,unused-ignore]

    return kickmix


def clog2(n: int) -> int:
    return max(1, (n - 1).bit_length())


def max_words_per_circuit(num_addresses: int, brot: int, cap: int = QUBIT_CAP) -> int:
    """Largest ``J`` whose unary loader fits the qubit cap."""
    n = clog2(num_addresses)
    return (cap - n - (n - 1)) // brot


def angle_deltas(words: np.ndarray, J: int) -> np.ndarray:
    """``(K, A, J)`` XOR tables: batch ``k`` of every row, XORed with batch ``k - 1`` (``k > 0``)."""
    words = np.asarray(words, dtype=np.int64)
    a, n_words = words.shape
    k = max(1, math.ceil(n_words / J))
    padded = np.zeros((a, k * J), dtype=np.int64)
    padded[:, :n_words] = words
    batches = padded.reshape(a, k, J).transpose(1, 0, 2)
    out = batches.copy()
    out[1:] ^= batches[:-1]
    return out


def _tree(flat: np.ndarray, n: int, and_node: Any, load: Any, root: Any) -> None:
    """Walk the unary-iteration tree once; the counter and the builder share it.

    ``and_node(level, control)`` is called at each internal node that needs a fresh control and
    returns ``(lower_control, flip, close)``: the control of the lower child, a callable that
    turns it into the upper child's control, and a callable that uncomputes it.
    """
    rows = flat.shape[0]

    def node(control: Any, level: int, lo: int, hi: int) -> None:
        if lo >= rows:
            return
        if hi <= rows:
            seg = flat[lo:hi]
            if not seg.any():
                return
            if hi - lo == 1 or (seg == seg[0]).all():
                load(lo, control)
                return
        mid = (lo + hi) // 2
        if rows <= mid:
            node(control, level + 1, lo, mid)
            return
        child, flip, close = and_node(level, control)
        node(child, level + 1, lo, mid)
        flip()
        node(child, level + 1, mid, hi)
        close()

    half = 1 << (n - 1)
    lower, flip, close = root()
    node(lower, 1, 0, half)
    flip()
    node(lower, 1, half, 2 * half)
    close()


def unary_toffolis(delta: np.ndarray) -> int:
    """Static Toffoli count of ``build_unary_loader(delta, ...)``, without building it."""
    flat = delta.reshape(delta.shape[0], -1)
    count = 0

    def and_node(level: int, control: Any) -> tuple[Any, Any, Any]:
        nonlocal count
        count += 1
        return None, lambda: None, lambda: None

    noop = (None, lambda: None, lambda: None)
    _tree(flat, clog2(flat.shape[0]), and_node, lambda row, c: None, lambda: noop)
    return count


def build_unary_loader(delta: np.ndarray, brot: int) -> Any:
    """One ``ANGLE_k`` circuit: ``delta`` is ``(A, J)`` and every entry fits in ``brot`` bits."""
    km = _km()
    delta = np.asarray(delta, dtype=np.int64)
    rows, J = delta.shape
    if rows < 2:
        raise ValueError("need at least two addresses")
    if delta.min() < 0 or delta.max() >= 1 << brot:
        raise ValueError(f"words must lie in [0, 2**{brot})")
    n = clog2(rows)
    b = km.CircuitBuilder()
    sel = b.create_quantum_register(n, "selection")
    words = [b.create_quantum_register(brot, f"word_{j}") for j in range(J)]
    anc = b.alloc_qubits(n - 1) if n > 1 else []
    msb_first = [sel[i] for i in reversed(range(n))]

    def load(row: int, control: Any) -> None:
        for j in range(J):
            v = int(delta[row, j])
            for bit in range(brot):
                if (v >> bit) & 1:
                    b.cx(control, words[j][bit])

    def and_node(level: int, control: Any) -> tuple[Any, Any, Any]:
        bit, a = msb_first[level], anc[level - 1]
        b.x(bit)
        b.init_and(control, bit, a)  # a = control AND NOT bit
        b.x(bit)
        return a, lambda: b.cx(control, a), lambda: b.del_and(control, bit, a)  # a = control AND bit

    def root() -> tuple[Any, Any, Any]:
        top = msb_first[0]  # the top address bit controls each half directly
        b.x(top)
        return top, lambda: b.x(top), lambda: None

    _tree(delta.reshape(rows, -1), n, and_node, load, root)
    return b.finish_circuit()


def build_family(words: np.ndarray, brot: int, J: int | None = None) -> tuple[Any, ...]:
    """The ``ceil(75 / J)`` circuits for an ``(A, 75)`` word table; ``J`` defaults to the cap."""
    words = np.asarray(words, dtype=np.int64)
    J = J or max_words_per_circuit(words.shape[0], brot)
    return tuple(build_unary_loader(d, brot) for d in angle_deltas(words, J))


def family_stats(circuits: tuple[Any, ...]) -> dict[str, int]:
    """Toffolis (static, one pass) and qubits (max), as the cost model reads them."""
    return {
        "toffoli": sum(c.operation_statistics().num_toffoli_like for c in circuits),
        "qubits": max(c.num_qubits for c in circuits),
        "circuits": len(circuits),
    }


def write_family(circuits: tuple[Any, ...], directory: str | Path) -> list[Path]:
    """Write ``angle_k_<k>.kmb`` (binary: a text file named ``.kmb`` is rejected silently)."""
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    paths = [d / f"angle_k_{k}.kmb" for k in range(len(circuits))]
    for p, c in zip(paths, circuits, strict=True):
        c.to_file(p, format="kmb")
    return paths
