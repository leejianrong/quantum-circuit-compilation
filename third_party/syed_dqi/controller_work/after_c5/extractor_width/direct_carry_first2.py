# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Direct carry with exact one-word charts at only the first two pivots.

Production carry is1.  P0=1/Y0 and
P1=q01/(1/Y1+P0(alpha1)), with q01=6.  Their three inverse arguments are
units under the existing active N0,D1,N1 conditions.  No later pivot uses
this chart: intermediate poles there need not be excluded by the C5 event.

The generic direct-carry schedule starts at public index2 with carry1 and
raw Y2.  Its input scale is omitted.  Return index2 restores that same raw
Y2/carry1 boundary; no pending division is assigned to the first two charts.

Larger component ABI only: initial carry c may be any unit if word2 already
contains c*Y2 while words0,1 are raw.  Production always c=1.
"""
from dataclasses import dataclass
import ew_paths  # noqa: F401
import gf24_arithmetic as A
import direct_carry_arithmetic as Arithmetic
import direct_carry_extractor as Direct
import rolling_tail_early as Tail
from raw_query_extractor import node, node_view, public_scale, query_step, FIELD


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
    first_inverses: tuple
    closed: bool = False


def _add_first_head_at_second_node(builder, words):
    node_view(builder, words[0], 1)
    builder.cx(words[0], words[1])
    node_view(builder, words[0], 1)


def emit_prefix(builder, raw_words, carry, *, j_min=15, stop_index=35,
                stage=lambda _: None):
    words = list(raw_words)
    assert len(words) == 35 and all(len(word) == 24 for word in words)
    assert len(carry) == 24 and 3 <= stop_index <= 35 and 2 <= j_min < 35
    assert len(set([*carry, *(q for word in words for q in word)])) == 864
    tail = Tail.RollingTail(builder, j_min, stop_index) if stop_index > j_min else None
    inputs, divisions = [None]*stop_index, [None]*stop_index
    first = A.inverse_deferred(builder, words[0])
    node_view(builder, words[0], 0)
    stage('raw_query_prefix_00')
    second_inner = A.inverse_deferred(builder, words[1])
    _add_first_head_at_second_node(builder, words)
    difference = node(0)[1] ^ node(1)[1]
    assert difference == 6
    public_scale(builder, words[1], FIELD.invert(difference))
    second_outer = A.inverse_deferred(builder, words[1])
    node_view(builder, words[1], 1)
    stage('raw_query_prefix_01')
    for i in range(2, stop_index):
        current = words[i]
        if i > 2:
            inputs[i] = A.emit_prefix(builder, carry, current)
        for old in range(i):
            query_step(builder, words[old], current, carry, old, i)
        token = tail.begin_slot(current, carry, i) if i >= j_min else None
        divisions[i] = Arithmetic.divide_deferred(builder, current, carry)
        builder.swap(current, carry)
        if token is not None:
            tail.finish_slot(current, token)
        node_view(builder, current, i)
        stage(f'raw_query_prefix_{i:02d}')
    return Record(id(builder), tuple(tuple(w) for w in words), tuple(carry),
                  j_min, stop_index, tail, inputs, divisions,
                  (first, second_inner, second_outer))


def emit_closing(builder, raw_words, carry, record, *, stage=lambda _: None):
    words = list(raw_words)
    assert record.builder_id == id(builder) and not record.closed
    assert tuple(tuple(w) for w in words) == record.words and tuple(carry) == record.carry
    tail, stop = record.tail, record.stop_index
    if tail is not None:
        assert tail.return_next == stop-1 and tail.pending is None
    for i in reversed(range(2, stop)):
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
    first, second_inner, second_outer = record.first_inverses
    node_view(builder, words[1], 1)
    A.inverse_closed(builder, words[1])
    A.repay_source_masks(builder, words[1], second_outer)
    public_scale(builder, words[1], node(0)[1] ^ node(1)[1])
    _add_first_head_at_second_node(builder, words)
    A.inverse_closed(builder, words[1])
    A.repay_source_masks(builder, words[1], second_inner)
    stage('raw_query_return_01')
    node_view(builder, words[0], 0)
    A.inverse_closed(builder, words[0])
    A.repay_source_masks(builder, words[0], first)
    stage('raw_query_return_00')
    assert all(rec is None or rec.closed for rec in record.input_scales)
    assert all(rec is None or rec.closed for rec in record.divisions)
    assert all(rec.closed for rec in record.first_inverses)
    record.closed = True


def source_ledger(stop_index=35, j_min=15, *, full_seed_seam=False):
    assert stop_index >= 3 and j_min >= 2
    out = Direct.source_ledger(stop_index, j_min, full_seed_seam=full_seed_seam)
    out['query_pair_T'] -= 198
    out['forward_input_scales_T'] -= 198
    out['forward_divisions_T'] -= 588
    out['shared_returns_T'] -= 1092
    out['arithmetic_pair_T'] -= 642
    out['arithmetic_prefix_T'] -= 300
    out['total_pair_T'] -= 642
    out['first_two_specialization_delta_T'] = -642
    out['C5_arithmetic_delta_T'] -= 642
    out['first_two_chart_pair_T'] = 1434
    out['first_two_chart_prefix_T'] = 585
    out['first_two_chart_return_T'] = 849
    out['prior_direct_first_two_T'] = 2076
    out['admission_change'] = False
    return out
