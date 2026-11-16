"""The back half of the newer lineage of syed3000's builder, wired by us (QCC-19, stage 3).

Same order of operations as `v6_pipeline.emit` / `integrated_pipeline.emit` (read as reference): deferred
rolling tail, padded scalar seed, fused synthesis, the gauge-park outer that borrows the tail's gauge flag and
`carry[12:]`, the infinity-3 finish, the zero-mask scan and the finish/outer seam. Module attributes are
assigned the way his `configure()` assigns them; geometry and instance handling stay ours. Vendored verbatim
in `third_party/syed_dqi`. No syndrome-weight gauge here (as in `fixed.py`).
"""

from __future__ import annotations

import sys
import types
from collections.abc import Callable
from typing import Any

from dqi_gen import extract_v3

_DIRS = (
    "after_v3/blocks",
    "after_v3/k24",
    "after_v3/scan",
    "after_v3/k24/v5_transpose14",
    "after_v3/blocks/v5_cubic_phase20",
    "after_c5/arithmetic_t",
    "after_c5/converter_width",
    "after_c5/converter_width/tail_phase_defer",
    "after_c5/extractor_width",
)
_mods: types.SimpleNamespace | None = None


def bind() -> types.SimpleNamespace:
    """Import and cross-assign the back-half modules; returns them by role."""
    global _mods
    if _mods is not None:
        return _mods
    extract_v3.bind()
    for d in reversed(_DIRS):
        p = str(extract_v3._ROOT / d)
        if p not in sys.path:
            sys.path.insert(0, p)
    import finish_outer_seam as seam  # type: ignore[import-not-found]
    import gf24_nested_norm as nested  # type: ignore[import-not-found]
    import paired_phase62 as paired  # type: ignore[import-not-found]
    import projective_finish_infinity3 as finish  # type: ignore[import-not-found]
    import rolling_tail_deferred as tail  # type: ignore[import-not-found]
    import scalar_seed_padded as seed  # type: ignore[import-not-found]
    import transpose14_core as core  # type: ignore[import-not-found]
    import transpose14_window as window  # type: ignore[import-not-found]
    import transpose_handoff_outer as outer  # type: ignore[import-not-found]
    import window_transpose_handoff as transpose  # type: ignore[import-not-found]
    import zero_mask_scan as scan  # type: ignore[import-not-found]

    outer.core = core
    window.transpose_tensor = transpose
    core.paired_scale = outer.paired_scale = paired
    finish.Arithmetic = nested
    scan.Finish = finish
    seam.Outer = outer
    seam.Finish = finish
    assert window.C is core and outer.core is core
    _mods = types.SimpleNamespace(
        seam=seam, finish=finish, tail=tail, seed=seed, outer=outer, scan=scan, window=window
    )
    return _mods


def _quiet(stage: Callable[[str], None] | None) -> Callable[[Any], None]:
    """The source modules call `stage` with dicts as well as strings; only strings become tags."""

    def call(s: Any) -> None:
        if stage is not None and isinstance(s, str):
            stage(s)

    return call


def run(
    builder: Any,
    words: list[list[Any]],
    carry: list[Any],
    masks: list[Any],
    stage: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """The decoder body on the geometry words and a carry set to 1, forward through the scan and back."""
    import fused_crt_synthesis as fs  # type: ignore[import-not-found]

    m = bind()
    extract_v3.set_tail_deferred(True)
    extract_v3.set_synthesis_nested(True)
    sub = _quiet(stage)

    def mark(name: str) -> None:
        if stage is not None:
            stage(name)

    rec = extract_v3.forward(builder, words, carry, stage=sub)
    mark("extract_fwd")
    rec.tail.release_spare()
    gauge = m.tail.gauge_prefix(builder, carry)
    sd = m.seed.emit_prefix(builder, carry[:12], words[34])
    rec.tail.seed_prefix(carry[:12], words[34][12:])
    n_list: list[list[Any]] = [carry[:12]]
    d_list: list[list[Any]] = [words[34][:12], words[34][12:]]
    records = []
    for i in range(33, -1, -1):
        p = [words[i][:12], words[i][12:]]
        records.append((n_list, d_list, p, fs.emit_prefix(builder, n_list, d_list, p, i, guarded=False)))
        n_list, d_list = d_list, n_list + p
    mark("synthesis_fwd")
    out = m.outer.emit_prefix(
        builder, d_list, n_list, gauge_flag=gauge.flag, gauge_other=carry[12:], fused=False, stage=sub
    )
    mark("outer_fwd")
    fin = m.finish.emit_prefix(builder, d_list, n_list)
    mark("finish_fwd")
    padded = list(masks) + [None] * (4095 - len(masks))
    info = m.scan.emit(builder, d_list, n_list, padded, positions=len(masks))
    mark("scan")
    reciprocal = m.finish.emit_closing_keep_inverse(builder, d_list, n_list, fin)
    m.seam.outer_closing_with_inverse(out.lender, d_list, n_list, out, reciprocal, stage=sub)
    out.core.gauge_carrier.clean_boundary()
    mark("outer_return")
    for old_n, old_d, old_p, r in reversed(records):
        fs.emit_closing(builder, old_n, old_d, old_p, r)
    mark("synthesis_return")
    returning = m.seed.close_padded(builder, carry[:12], words[34], sd)
    rec.tail.seed_return(carry[:12], words[34][12:])
    m.seed.finish_after_swap(builder, carry[:12], words[34], rec.tail.current, returning)
    m.tail.gauge_return(builder, carry, gauge)
    rec.tail.resume_return()
    extract_v3.closing(builder, words, carry, rec, stage=sub)
    mark("extract_return")
    return dict(info)
