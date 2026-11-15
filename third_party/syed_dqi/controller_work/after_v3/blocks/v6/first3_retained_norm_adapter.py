# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Production-only three-pivot chart with a paid zero-residue correction.

The first two public charts and all six matched inverse calls borrow the
otherwise unused constant-one carry. Generic extraction begins at index3,
with carry1 and its raw residue. The existing initial tail predicate is
borrowed only before its first use and is HMR-reset without being freed.
All accepted v4/v5 sources and their records remain unchanged.
"""
from dataclasses import dataclass
import third_pivot_chart as Third

Base = Third.Base
Phase = Third.Norm
A = Base.A
Arithmetic = Base.Arithmetic
Tail = Base.Tail
node_view = Base.node_view
node = Base.node
public_scale = Base.public_scale


@dataclass
class ProductionRecord:
    inner: object
    third: object
    builder_id: int
    carry: tuple
    declared_initial_carry: int = 1
    closed_inverse_calls: int = 0
    borrow_receipts: object = None
    clean_carry_seam_reached: bool = False
    third_receipt: object = None

    def __getattr__(self, name):
        return getattr(self.inner, name)


def emit_prefix(builder, raw_words, carry, *, j_min=15, stop_index=35,
                stage=lambda _: None, production_carry_value=1):
    if production_carry_value != 1:
        raise ValueError('this adapter requires the production constant-one carry')
    words = list(raw_words)
    assert len(words) == 35 and all(len(word) == 24 for word in words)
    assert len(carry) == 24 and 4 <= stop_index <= 35 and 3 <= j_min < 35
    assert len(set([*carry, *(wire for word in words for wire in word)])) == 864
    assert A is Phase.Arithmetic and Arithmetic is Base.Arithmetic and Tail is Third.Tail
    tail = Tail.RollingTail(builder, j_min, stop_index) if stop_index > j_min else None
    inputs, divisions = [None]*stop_index, [None]*stop_index
    builder.x(carry[0])
    first = Phase.inverse_prefix_with_bank(builder, words[0], carry)
    node_view(builder, words[0], 0)
    stage('raw_query_prefix_00')
    second_inner = Phase.inverse_prefix_with_bank(builder, words[1], carry)
    Base._add_first_head_at_second_node(builder, words)
    difference = node(0)[1] ^ node(1)[1]
    assert difference == 6
    public_scale(builder, words[1], Base.FIELD.invert(difference))
    second_outer = Phase.inverse_prefix_with_bank(builder, words[1], carry)
    node_view(builder, words[1], 1)
    stage('raw_query_prefix_01')
    if tail is not None:
        assert tail.pending is None and tail.forward_next == j_min
        assert tail.current is not None and tail.spare is None
        borrowed_flag = tail.current
        temporary_flag = None
    else:
        # Only a short component boundary can omit the production tail owner.
        temporary_flag = builder.alloc_qubits(1)
        borrowed_flag = temporary_flag[0]
    third = Third.emit_prefix(builder, words[:2], words[2], carry, borrowed_flag)
    if temporary_flag is not None:
        builder.free(temporary_flag)
    else:
        assert tail.current == borrowed_flag and tail.forward_next == j_min
    node_view(builder, words[2], 2)
    stage('raw_query_prefix_02')
    builder.x(carry[0])
    stage('first_three_prefix_carry_restored')
    for i in range(3, stop_index):
        current = words[i]
        if i > 3:
            inputs[i] = A.emit_prefix(builder, carry, current)
        for old in range(i):
            Base.query_step(builder, words[old], current, carry, old, i)
        token = tail.begin_slot(current, carry, i) if i >= j_min else None
        divisions[i] = Arithmetic.divide_deferred(builder, current, carry)
        builder.swap(current, carry)
        if token is not None:
            tail.finish_slot(current, token)
        node_view(builder, current, i)
        stage(f'raw_query_prefix_{i:02d}')
    inner = Base.Record(id(builder), tuple(tuple(word) for word in words), tuple(carry),
        j_min, stop_index, tail, inputs, divisions, (first, second_inner, second_outer))
    return ProductionRecord(inner, third, id(builder), tuple(carry), borrow_receipts=[])


def emit_closing(builder, raw_words, carry, production, *, stage=lambda _: None):
    assert isinstance(production, ProductionRecord)
    assert production.builder_id == id(builder) and production.declared_initial_carry == 1
    assert production.carry == tuple(carry) and production.closed_inverse_calls == 0
    record, words = production.inner, list(raw_words)
    assert record.builder_id == id(builder) and not record.closed
    assert tuple(tuple(word) for word in words) == record.words and tuple(carry) == record.carry
    tail, stop = record.tail, record.stop_index
    if tail is not None:
        assert tail.return_next == stop-1 and tail.pending is None
    for i in reversed(range(3, stop)):
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
            Base.query_step(builder, words[old], current, carry, old, i, True)
        stage(f'raw_query_return_{i:02d}')
    if tail is not None:
        tail.close()
    assert not production.clean_carry_seam_reached
    production.clean_carry_seam_reached = True
    stage('first_three_clean_carry_seam')
    builder.x(carry[0])
    node_view(builder, words[2], 2)
    production.third_receipt = Third.emit_closing(
        builder, words[:2], words[2], carry, production.third)
    production.borrow_receipts.extend(production.third_receipt['inverse_receipts'])
    production.closed_inverse_calls += production.third_receipt['closed_inverse_calls']
    assert production.third.closed and production.third.zero_mask is None
    stage('raw_query_return_02')

    def matched_inverse(word, prefix_record):
        receipt = Phase.inverse_return_with_bank(builder, word, carry, prefix_record)
        production.borrow_receipts.append(receipt)
        production.closed_inverse_calls += 1
        assert receipt['all_owned_storage_bits_reset'] and receipt['deferred_prefix_mask_paid']

    first, second_inner, second_outer = record.first_inverses
    node_view(builder, words[1], 1)
    matched_inverse(words[1], second_outer)
    public_scale(builder, words[1], difference := node(0)[1] ^ node(1)[1])
    assert difference == 6
    Base._add_first_head_at_second_node(builder, words)
    matched_inverse(words[1], second_inner)
    stage('raw_query_return_01')
    node_view(builder, words[0], 0)
    matched_inverse(words[0], first)
    stage('raw_query_return_00')
    assert production.closed_inverse_calls == len(production.borrow_receipts) == 6
    builder.x(carry[0])
    assert all(item is None or item.closed for item in record.input_scales)
    assert all(item is None or item.closed for item in record.divisions)
    assert all(item.closed for item in record.first_inverses)
    record.closed = True


def source_ledger(*args, **kwargs):
    result = dict(Base.source_ledger(*args, **kwargs))
    result.update(status='THREE_PUBLIC_CHARTS_WITH_EXPLICIT_ZERO_RESIDUE_DEBT_MODEL',
                  source_ledger_reference='Immutable first-two ledger before later v4 deltas',
                  incremental_static_delta_from_selected_v4=-301,
                  incremental_mean_delta_from_selected_v4='-1310167980/4194304',
                  incremental_static_delta_from_matched_first2=-55,
                  incremental_mean_delta_from_matched_first2='-277582827/4194304',
                  prefix_static_delta_from_selected_v4=29,
                  production_initial_carry=1, borrowed_physical_indices=list(range(24)),
                  pending_special_classical_debt_bits=37,
                  additional_domain_exclusion=False, arbitrary_initial_carry_supported=False)
    return result
