"""Synthesis stage: the polynomials `(N, D)` from the extracted heads, in place (QCC-19, E041).

The recurrence is `(N, D) <- (D, q_i N + P_i D)` for `i = 34 .. 0` (`thiele.synthesize`), run with the fused
CRT step of the vendored kernel `fused_crt_synthesis` (syed3000, Apache-2.0, verbatim): the head words `P_i`
become the two top coefficient words of the new `D`, so only one extra 12-bit word is needed.

Padding for weights below 35 (`35 - w` zero heads at the top): each zero head is a "padded" step, which
swaps the
roles of `N` and `D`. With `f = (35 - w) mod 2`, the state after the first step (`i = 34`) is `(1,
P_34)` for
`f = 0`; for `f = 1` the correct state is `(0, x)` (a ratio-0 pair times `x`, harmless because `x` has
no root among
the scanned nonzero positions), which is the `f`-controlled swap of the constant word of `N` and the `x`
coefficient of `D`. `f` is the tail controller's flag from the extract stage (`extract.forward`'s record).

Result: `N` has 35 words (degree at most 34), `D` has 36 words (degree at most 35), coefficients low to
high; the
rational function `N / D` equals the true one up to a common polynomial factor with no root in GF(2^12)^* ;
the error value at a root `a` of `D` is `N(a) / (a M(a) D'(a))` (`thiele.amplitude`).
"""

from __future__ import annotations

from typing import Any

from dqi_gen import extract  # noqa: F401  (puts the vendored kernels on sys.path)

NODES = 35


def forward(
    builder: Any, heads: list[list[Any]], flag: Any
) -> tuple[list[list[Any]], list[list[Any]], list[Any], list[Any]]:
    """Consume `heads` (35 words of 24 qubits, head `i` in `heads[i]`) into `(N, D)`.

    Returns `(N, D, records, one)`; `records` and `one` are what `backward` needs. `flag` is the padding
    parity bit.
    """
    import c27_paths  # type: ignore[import-not-found]  # noqa: F401
    import fused_crt_synthesis as fs  # type: ignore[import-not-found]

    one = list(builder.alloc_qubits(12))
    builder.x(one[0])
    n_list: list[list[Any]] = [one]
    d_list: list[list[Any]] = [list(heads[NODES - 1][:12]), list(heads[NODES - 1][12:])]
    for q_one, q_x in zip(one, d_list[1], strict=True):
        builder.cswap(flag, q_one, q_x)
    records = []
    for i in range(NODES - 2, -1, -1):
        p = [list(heads[i][:12]), list(heads[i][12:])]
        rec = fs.emit_prefix(builder, n_list, d_list, p, i)
        records.append((i, n_list, d_list, p, rec))
        n_list, d_list = d_list, n_list + p
    return n_list, d_list, records, one


def backward(builder: Any, flag: Any, heads: list[list[Any]], records: list[Any], one: list[Any]) -> None:
    """Undo `forward` (records in reverse), restoring the heads and freeing the extra word."""
    import fused_crt_synthesis as fs

    for _i, n_list, d_list, p, rec in reversed(records):
        fs.emit_closing(builder, n_list, d_list, p, rec)
    for q_one, q_x in zip(one, list(heads[NODES - 1][12:]), strict=True):
        builder.cswap(flag, q_one, q_x)
    builder.x(one[0])
    builder.free(one)
