"""The extract stage of the newer lineage of syed3000's builder, wired by us (QCC-19).

`extract.py` runs `raw_query_extractor` (the older lineage). This module runs the three-pivot adapter
`first3_retained_norm_adapter` and the return arithmetic it needs (nested-norm GF(2^24) arithmetic, the closed
inverse with a retained norm, the final-return retained child), all vendored verbatim in
`third_party/syed_dqi`.
The source builder binds them into its pipeline by assigning module attributes
(`v7_pipeline.configure`); we do the same assignments here, in the same order, and nowhere else.
Same interface as `extract.py`: `forward` and `backward` take 35 words, a carry set to 1, and
return/consume the record.
"""

from __future__ import annotations

import pathlib
import sys
from collections.abc import Callable
from typing import Any

_ROOT = pathlib.Path(__file__).resolve().parents[2] / "third_party" / "syed_dqi" / "controller_work"
_DIRS = (
    "night_c27/arithmetic",
    "night_c27/controller",
    "night_c27/synthesis",
    "night_schedule",
    "night_root",
    "after_c5/arithmetic_t",
    "after_c5/extractor_width",
    "after_v3/k24",
    "after_v3/audit/retained_child",
    "after_v3/blocks/v5",
    "after_v3/blocks/v6",
)
J_MIN = 15
NODES = 35
_bound: Any = None


def bind() -> Any:
    """Assign the module attributes the source pipeline assigns for its extractor; returns the adapter."""
    global _bound
    if _bound is not None:
        return _bound
    for d in reversed(_DIRS):
        p = str(_ROOT / d)
        if p not in sys.path:
            sys.path.insert(0, p)
    import direct_carry_arithmetic as direct_arith  # type: ignore[import-not-found]
    import direct_carry_extractor as direct  # type: ignore[import-not-found]
    import direct_carry_first2 as first2  # type: ignore[import-not-found]
    import gf24_nested_norm as nested  # type: ignore[import-not-found]
    import last_return_retained_norm as last  # type: ignore[import-not-found]
    import nested_norm_inverse  # type: ignore[import-not-found]
    import quotient_phase84_mask_guard as phase  # type: ignore[import-not-found]

    assert phase.Arithmetic is last.A is nested
    direct_arith.Prior = nested_norm_inverse
    direct_arith.A = nested
    for ext in (direct, first2):
        ext.A = nested
        ext.Arithmetic = direct_arith
    nested.inverse_closed = phase.inverse_closed
    # the last-return provider replaces the direct-carry arithmetic of both extractors (after the lines above)
    direct.Arithmetic = last
    first2.Arithmetic = last
    import first3_retained_norm_adapter as first3  # type: ignore[import-not-found]
    import inverse_retained_norm_deferred as retained  # type: ignore[import-not-found]

    assert first3.Base is first3.Third.Base is first2
    assert first3.Phase is first3.Third.Norm is retained
    assert first3.Arithmetic is last and first3.A is retained.Arithmetic is nested
    _bound = first3
    return first3


def forward(
    builder: Any, words: list[list[Any]], carry: list[Any], stage: Callable[[str], None] | None = None
) -> Any:
    """Run the extraction prefix in place; returns the record needed by `backward`."""
    return bind().emit_prefix(
        builder, words, carry, j_min=J_MIN, stop_index=NODES, stage=stage or (lambda _: None)
    )


def closing(
    builder: Any,
    words: list[list[Any]],
    carry: list[Any],
    record: Any,
    stage: Callable[[str], None] | None = None,
) -> None:
    """The adapter's return pass alone; the tail must already be resumed (`fixed.py` does it)."""
    bind().emit_closing(builder, words, carry, record, stage=stage or (lambda _: None))


def backward(
    builder: Any,
    words: list[list[Any]],
    carry: list[Any],
    record: Any,
    stage: Callable[[str], None] | None = None,
) -> None:
    """Undo `forward` exactly; the tail's spare flag is released and re-allocated first, as in `extract`."""
    record.tail.release_spare()
    record.tail.resume_return()
    closing(builder, words, carry, record, stage=stage)
