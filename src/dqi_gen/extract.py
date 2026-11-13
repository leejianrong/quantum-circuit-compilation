"""The extract stage of the 889-qubit architecture, wired from the vendored kernels (QCC-19, E041).

`third_party/syed_dqi` (Apache-2.0, syed3000; verbatim) holds the deferred-mask arithmetic and the raw-query
extractor. This module puts those directories on `sys.path` and exposes the stage with our conventions:

* input: 35 words of 24 bits, word `i` the value `Y_i = P(alpha_i)` in `K` (bits 0..11 the constant part,
  bits 12..23 the `theta` part), `alpha_i = theta + 2 i`, and a 24-bit carry the caller has set to 1;
* after `forward`: word `i < w` holds the head `P_i = h0 + h1 z` as the pair `(h0, h1)` (low, high half), the
  carry holds `1 / n_last`, words from `w` on are zero; checked against `thiele.extract` for weights 19 to 35
  (`tests/unit/test_dqi_extract.py`). Weights below `J_MIN = 15` are outside the supported domain;
* `backward` is the exact return: it restores words and carry and repays the deferred phases.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

_ROOT = pathlib.Path(__file__).resolve().parents[2] / "third_party" / "syed_dqi" / "controller_work"
for _d in ("night_c27/arithmetic", "night_c27/controller", "night_schedule"):
    _p = str(_ROOT / _d)
    if _p not in sys.path:
        sys.path.insert(0, _p)

J_MIN = 15
NODES = 35


def forward(builder: Any, words: list[list[Any]], carry: list[Any]) -> Any:
    """Run the extraction prefix in place; returns the record needed by `backward`."""
    import raw_query_extractor as rq  # type: ignore[import-not-found]

    return rq.emit_prefix(builder, words, carry, j_min=J_MIN, stop_index=NODES)


def backward(builder: Any, words: list[list[Any]], carry: list[Any], record: Any) -> None:
    """Undo `forward` exactly (the tail controller's spare flag is released and re-allocated first)."""
    import raw_query_extractor as rq

    record.tail.release_spare()
    record.tail.resume_return()
    rq.emit_closing(builder, words, carry, record)
