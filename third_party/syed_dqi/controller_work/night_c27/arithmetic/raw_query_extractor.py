# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""One fixed raw-query extractor with a reciprocal carry and actual tail flags.

Input: 35 common-K residue words Y_i, untouched until their own pivot, and a
24-bit carry known to be one.  Output: coefficient-basis P_i words, a unit
reciprocal carry, and the rolling tail controller's two physical wires.
No compiler-provided degree, quotient profile, gaps, contacts or tail flags
are accepted.  j_min is a public circuit policy, not an input profile.

The optional stop_index is a component-test boundary.  Production is35.
Closing requires that every intermediate word be restored to the prefix
boundary and, if a tail controller is present, resume_return() was called.
The caller owns the gauge/seed/synthesis/scan lifecycle between the calls.
"""
from dataclasses import dataclass
import c27_paths  # noqa: F401
import kickmix as km
import gf24_arithmetic as A
import rolling_tail as Tail
from monic_forney import add_scaled
from projective_carry import linear_scale

FIELD = km.GF2Field(12)
DELTA = 2048


def node(index):
    t = 2*index
    return t, DELTA ^ FIELD.mul(t, t) ^ t


def node_view(builder, word, index):
    """Involutory common-K value <-> linear-polynomial coefficient view."""
    assert len(word) == 24
    add_scaled(builder, word[12:], word[:12], 2*index)


def public_scale(builder, word, coefficient):
    assert coefficient and len(word) == 24
    linear_scale(builder, word[:12], coefficient)
    linear_scale(builder, word[12:], coefficient)


def query_step(builder, head, numerator, denominator, old_index, new_index,
               reverse=False):
    """(n,d) -> ((d+P_l(alpha_i)*n)/q_l(alpha_i),n), exactly99T."""
    assert 0 <= old_index < new_index < 35
    coefficient = node(old_index)[1] ^ node(new_index)[1]
    assert coefficient
    node_view(builder, head, new_index)
    if reverse:
        builder.swap(numerator, denominator)
        public_scale(builder, denominator, coefficient)
        A.product(builder, head, numerator, denominator)
    else:
        A.product(builder, head, numerator, denominator)
        public_scale(builder, denominator, FIELD.invert(coefficient))
        builder.swap(numerator, denominator)
    node_view(builder, head, new_index)


@dataclass
class Record:
    builder_id: int
    words: tuple
    carry: tuple
    j_min: int
    stop_index: int
    tail: object
    input_scales: list
    inverse_masks: list
    normalizer_products: list
    closed: bool = False


def emit_prefix(builder, raw_words, carry, *, j_min=15, stop_index=35,
                stage=lambda _: None):
    words = list(raw_words)
    assert len(words) == 35 and all(len(word) == 24 for word in words)
    assert len(carry) == 24 and 1 <= stop_index <= 35 and 0 <= j_min < 35
    assert len(set([*carry, *(q for word in words for q in word)])) == 864
    tail = Tail.RollingTail(builder, j_min, stop_index) if stop_index > j_min else None
    inputs, inverses, normalizers = [None]*stop_index, [], []
    for i in range(stop_index):
        current = words[i]
        if i:
            inputs[i] = A.emit_prefix(builder, carry, current)
        for old in range(i):
            query_step(builder, words[old], current, carry, old, i)
        token = tail.begin_slot(current, carry, i) if i >= j_min else None
        inverses.append(A.inverse_deferred(builder, current))
        normalizers.append(A.emit_prefix(builder, current, carry))
        builder.swap(current, carry)
        # A zero predicate is basis independent.  Finish the controller while
        # the head is still in common K; then store its coefficient coordinates.
        if token is not None:
            tail.finish_slot(current, token)
        node_view(builder, current, i)
        stage(f'raw_query_prefix_{i:02d}')
    return Record(id(builder), tuple(tuple(w) for w in words), tuple(carry),
                  j_min, stop_index, tail, inputs, inverses, normalizers)


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
        inverse_return = A.inverse_deferred(builder, current)
        product_return = A.emit_prefix(builder, current, carry)
        targets = [(carry, product_return.old_target_mask)]
        next_return = None
        if i+1 < stop:
            # The preceding return left this word as c_(i+1)*rawY_(i+1).
            # c_(i+1)=1/u_i.  Restore it while u_i is already live.
            next_return = A.emit_prefix(builder, current, words[i+1])
            targets.append((words[i+1], next_return.old_target_mask))
        # Exact seam: current=u_i, carry=v_i, next=rawY_(i+1).  All three
        # return debts are one affine numerator over the same divisor u_i.
        A.phase_affine_quotient(builder, current, targets,
                               A.source_mask(inverse_return))
        A.free_source_masks(builder, inverse_return)
        A.free_product_mask(builder, product_return)
        if next_return is not None:
            A.free_product_mask(builder, next_return)
            A.repay_product_input(builder, words[i+1], record.input_scales[i+1])
        A.repay_source_masks(builder, current, record.inverse_masks[i])
        A.repay_product_input(builder, carry, record.normalizer_products[i])
        if token is not None:
            tail.finish_return(current, carry, token)
        for old in reversed(range(i)):
            query_step(builder, words[old], current, carry, old, i, True)
        # current remains c_i*rawY_i for the preceding return; i=0 has c0=1.
        stage(f'raw_query_return_{i:02d}')
    if tail is not None:
        tail.close()
    assert all(rec is None or rec.closed for rec in record.input_scales)
    assert all(rec.closed for rec in record.inverse_masks+record.normalizer_products)
    record.closed = True


def source_ledger(stop_index=35, j_min=15, *, full_seed_seam=False):
    n = stop_index
    possible = max(0, n-j_min)
    queries = 99*n*(n-1)
    scales = 99*(4*n-2)
    inverses = 390*n
    phases = 264*n
    controller = 138*possible-45 if possible else 0
    arithmetic = queries+scales+inverses+phases
    assert arithmetic == 99*n*n+951*n-198
    out = dict(status='SOURCE_MODEL_UNTIL_NATIVE_PANEL_PASSES', slots=n,
               query_pair_T=queries, consuming_scales_pair_T=scales,
               deferred_inverses_pair_T=inverses, affine_phases_pair_T=phases,
               arithmetic_pair_T=arithmetic, rolling_without_seed_T=controller,
               arithmetic_prefix_T=99*n*(n-1)//2+99*(n-1)+294*n,
               base_data_qubits=864, peak_Q=890 if possible else 888)
    if full_seed_seam:
        assert n == 35 and possible
        out.update(seed_controller_pair_T=35, gauge_pair_T=45, scalar_seed_pair_T=260,
                   total_pair_T=arithmetic+controller+35+45+260)
    else:
        out['total_pair_T'] = arithmetic+controller
    return out
