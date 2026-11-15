# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Fixed raw-query extractor retaining the selected unit u as its carry.

Production starts with carry1 and35 raw residues, exactly as in C5.  For
component testing, the same map also accepts any unit initial carry c when
the first stored residue is already c*Y0.  It restores that exact entry.
Quotient heads and zero flags are unchanged.  Final carry is generally K,
not a base-field scalar; gauge/seed ownership is NOT omitted.
"""
from dataclasses import dataclass
import ew_paths  # noqa: F401
import gf24_arithmetic as A
import direct_carry_arithmetic as Arithmetic
import rolling_tail_early as Tail
from raw_query_extractor import node, node_view, public_scale, query_step


@dataclass
class Record:
    builder_id: int
    words: tuple
    carry: tuple
    j_min: int
    stop_index: int
    tail: object
    input_scales: list
    divisions: list
    closed: bool = False


def emit_prefix(builder, raw_words, carry, *, j_min=15, stop_index=35,
                stage=lambda _: None):
    words = list(raw_words)
    assert len(words) == 35 and all(len(word) == 24 for word in words)
    assert len(carry) == 24 and 1 <= stop_index <= 35 and 0 <= j_min < 35
    assert len(set([*carry, *(q for word in words for q in word)])) == 864
    tail = Tail.RollingTail(builder, j_min, stop_index) if stop_index > j_min else None
    inputs, divisions = [None]*stop_index, []
    for i in range(stop_index):
        current = words[i]
        if i:
            inputs[i] = A.emit_prefix(builder, carry, current)
        for old in range(i):
            query_step(builder, words[old], current, carry, old, i)
        token = tail.begin_slot(current, carry, i) if i >= j_min else None
        divisions.append(Arithmetic.divide_deferred(builder, current, carry))
        # Current is still selected u; carry is now the head v/u.
        builder.swap(current, carry)
        if token is not None:
            tail.finish_slot(current, token)
        node_view(builder, current, i)
        stage(f'raw_query_prefix_{i:02d}')
    return Record(id(builder), tuple(tuple(w) for w in words), tuple(carry),
                  j_min, stop_index, tail, inputs, divisions)


def emit_closing(builder, raw_words, carry, record, *, stage=lambda _: None):
    words = list(raw_words)
    assert record.builder_id == id(builder) and not record.closed
    assert tuple(tuple(w) for w in words) == record.words and tuple(carry) == record.carry
    tail, stop = record.tail, record.stop_index
    if tail is not None:
        assert tail.return_next == stop-1 and tail.pending is None
    for i in reversed(range(stop)):
        current = words[i]
        node_view(builder, current, i)
        token = tail.begin_return(current, i) if i >= record.j_min else None
        builder.swap(current, carry)
        Arithmetic.restore_with_shared_norm(builder, current, carry, record.divisions[i],
            next_word=words[i+1] if i+1 < stop else None,
            next_input_record=record.input_scales[i+1] if i+1 < stop else None)
        if token is not None:
            tail.finish_return(current, carry, token)
        for old in reversed(range(i)):
            query_step(builder, words[old], current, carry, old, i, True)
        stage(f'raw_query_return_{i:02d}')
    if tail is not None:
        tail.close()
    assert all(rec is None or rec.closed for rec in record.input_scales)
    assert all(rec.closed for rec in record.divisions)
    record.closed = True


def source_ledger(stop_index=35, j_min=15, *, full_seed_seam=False):
    n = stop_index
    possible = max(0, n-j_min)
    queries = 99*n*(n-1)
    prefix_scales = 99*(n-1)
    prefix_divisions = 294*n
    returns = 546*(n-1)+363
    arithmetic = queries+prefix_scales+prefix_divisions+returns
    controller = 138*possible-45 if possible else 0
    out = dict(status='SOURCE_MODEL_NOT_YET_NATIVE_CHECKED', slots=n,
               query_pair_T=queries, forward_input_scales_T=prefix_scales,
               forward_divisions_T=prefix_divisions, shared_returns_T=returns,
               arithmetic_pair_T=arithmetic,
               arithmetic_prefix_T=queries//2+prefix_scales+prefix_divisions,
               rolling_without_seed_T=controller, base_data_qubits=864,
               peak_Q=889 if possible else 888,
               C5_arithmetic_delta_T=-(111*(n-1)+195),
               total_pair_T=arithmetic+controller)
    if full_seed_seam:
        assert n == 35 and possible
        out.update(seed_controller_pair_T=35, gauge_pair_T=45,
                   scalar_seed_pair_T=261)
        out['total_pair_T'] += 35+45+261
    return out
