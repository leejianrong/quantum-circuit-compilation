"""The decoder with the convert stage and the 11-Toffoli scan (QCC-19, E041).

Same front half as `thiele_decoder` (geometry, extract, synthesis); then the vendored kernels of syed3000
(Apache-2.0, verbatim, `third_party/syed_dqi`): `night_outer` (the half-degree Euclid preimage, history free),
`projective_finish` (the polynomial `K` with `K(a) = M(a) H(D) X(a)` at the roots of `D`) and
`additive_fft_phase_scan` (the root test of `D` and the phase linear in `K` at every position, 11 Toffolis).
We run them as Python in the kickmix simulator and wire them ourselves; the classical model is `convert`.
The scan is run without the syndrome-weight gauge (no position is skipped).
"""

from __future__ import annotations

import pathlib
import sys
import types
from typing import Any

import kickmix as km  # type: ignore[import-not-found,unused-ignore]

from dqi_gen import extract, synth, thiele_decoder

_ROOT = pathlib.Path(__file__).resolve().parents[2] / "third_party" / "syed_dqi" / "controller_work"
for _d in (
    "night_converter",
    "night_c27/mask_gauge",
    "work/round2/milestone152/source",
):
    _p = str(_ROOT / _d)
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _seeded_forward(builder: Any, words: list[list[Any]], carry: list[Any], rec: Any) -> tuple[Any, ...]:
    """Seed the synthesis from the carry word (no extra word): chart bit, scalar seed, rolling-tail seam."""
    import fused_crt_synthesis as fs  # type: ignore[import-not-found]
    import rolling_tail as tail  # type: ignore[import-not-found]
    import scalar_seed as seed  # type: ignore[import-not-found]

    rec.tail.release_spare()
    gauge = tail.gauge_prefix(builder, carry)
    sd = seed.emit_prefix(builder, carry[:12], words[34])
    rec.tail.seed_prefix(carry[:12], words[34][12:])
    n_list: list[list[Any]] = [carry[:12]]
    d_list: list[list[Any]] = [words[34][:12], words[34][12:]]
    records = []
    for i in range(33, -1, -1):
        p = [words[i][:12], words[i][12:]]
        records.append((n_list, d_list, p, fs.emit_prefix(builder, n_list, d_list, p, i)))
        n_list, d_list = d_list, n_list + p
    return n_list, d_list, (gauge, sd, records)


def _seeded_backward(builder: Any, words: list[list[Any]], carry: list[Any], rec: Any, state: Any) -> None:
    import fused_crt_synthesis as fs
    import rolling_tail as tail
    import scalar_seed as seed

    gauge, sd, records = state
    for n_list, d_list, p, r in reversed(records):
        fs.emit_closing(builder, n_list, d_list, p, r)
    rec.tail.seed_return(carry[:12], words[34][12:])
    seed.emit_closing(builder, carry[:12], words[34], sd)
    tail.gauge_return(builder, carry, gauge)
    rec.tail.resume_return()


def build_decoder(
    builder: Any, syndromes: list[Any], masks: list[Any], seeded: bool = True
) -> dict[str, Any]:
    """Append the decoder to `builder`; returns static numbers of the scan."""
    import additive_fft_phase_scan as scan  # type: ignore[import-not-found]
    import night_outer as outer  # type: ignore[import-not-found]
    import projective_finish as finish  # type: ignore[import-not-found]

    scan.syndrome_gauge_plan = lambda: types.SimpleNamespace(selected=())
    from dqi_gen.tower import apply_matrix_inplace

    flat = [q for reg in syndromes for q in reg]
    fwd, inv = thiele_decoder.geometry_columns()
    apply_matrix_inplace(builder, flat, fwd)
    words = [list(flat[24 * i : 24 * i + 24]) for i in range(35)]
    carry = list(builder.alloc_qubits(24))
    builder.x(carry[0])
    rec = extract.forward(builder, words, carry)
    if seeded:
        n_list, d_list, state = _seeded_forward(builder, words, carry, rec)
    else:
        flag = rec.tail.current
        n_list, d_list, records, one = synth.forward(builder, words, flag)
    out = outer.emit_prefix(builder, d_list, n_list, fused=False)
    fin = finish.emit_prefix(builder, d_list, n_list)
    padded = list(masks) + [None] * (4095 - len(masks))
    info = scan.emit(builder, d_list, n_list, padded, positions=len(masks))
    finish.emit_closing(builder, d_list, n_list, fin)
    outer.emit_closing(builder, d_list, n_list, (), out)
    if seeded:
        _seeded_backward(builder, words, carry, rec, state)
        import raw_query_extractor as rq  # type: ignore[import-not-found]

        rq.emit_closing(builder, words, carry, rec)
    else:
        synth.backward(builder, flag, words, records, one)
        extract.backward(builder, words, carry, rec)
    builder.x(carry[0])
    builder.free(km.array(carry))
    apply_matrix_inplace(builder, flat, inv)
    return dict(info)


def build_circuit(m: int, n: int, degree: int) -> Any:
    if (n, degree) != (70, 12):
        raise ValueError("the decoder is built for n = 70 syndromes over GF(2^12)")
    builder = km.CircuitBuilder()
    syndromes = [builder.create_quantum_register(degree, name=f"S{i}") for i in range(n)]
    masks = [builder.create_classical_register(degree, name=f"E{j}") for j in range(m)]
    build_decoder(builder, syndromes, masks)
    return builder.finish_circuit()
