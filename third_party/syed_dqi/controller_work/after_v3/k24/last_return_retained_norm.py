# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Only the final direct-carry return retains its reciprocal child norm.

Source model:352 static T rather than360 for the nested final return;
24 helpers, unit K24 source, arbitrary K24 target, unchanged mask ABI.
The32 returns with next_word delegate to the unchanged provider: retaining
the child there would need30 helpers during their consuming half-scales.
No production source is modified. Native checks are separate.
"""
from pathlib import Path
import sys
import k24_paths
path = k24_paths.WORK/'after_c5/extractor_width'
if str(path) not in sys.path:
    sys.path.insert(0, str(path))
import direct_carry_arithmetic as Original
import gf24_nested_norm as A
import nested_norm_inverse as Nested
import narrow_field130 as Narrow
import kickmix as km
from tower_inverse import (quadratic_basis, apply_inplace_linear, init_norm,
                           erase_norm, xor_product, phase_product, kernel)

divide_deferred = Original.divide_deferred


def inverse_twelve_keep_child(builder, source):
    """66 T: inv0(source), exact entry masks, live reciprocal child6."""
    assert len(source) == 12
    info = quadratic_basis(12)
    apply_inplace_linear(builder, source, info['to_tower'])
    left, right = source[:6], source[6:]
    child = init_norm(builder, left, right, info['delta'])
    child_masks = Nested.inverse_six_deferred(builder, child)
    Nested.repay_norm_entry(builder, left, right, info['delta'], child_masks)
    temporary = builder.alloc_qubits(6)
    masks = []
    for half in (left, right):
        xor_product(builder, half, child, temporary)
        builder.swap(half, temporary)
        mask = builder.alloc_bits(6)
        builder.hmr(temporary, mask)
        masks.append(mask)
    builder.free(temporary)
    builder.cx(right, left)
    # The omitted erase_norm/free were zero-T. child is still inv0(N(entry)).
    apply_inplace_linear(builder, source, info['from_tower'])
    return tuple(masks), child


def _repay_inverse_and_child(builder, source, inverse_norm, child, delta):
    """Close inverse norm and saved child at42+19 static T/24 helpers."""
    info = quadratic_basis(12)
    apply_inplace_linear(builder, inverse_norm, info['to_tower'])
    mask = builder.alloc_bits(12)
    builder.hmr(inverse_norm, mask)
    builder.free(inverse_norm)
    original_norm = init_norm(builder, source[:12], source[12:], delta)
    apply_inplace_linear(builder, original_norm, info['to_tower'])
    left, right = original_norm[:6], original_norm[6:]
    # inv0(N) has tower halves((left+right)*child,right*child).
    builder.cx(right, left)
    phase_product(builder, left, child, mask[:6], kernel(6))
    builder.cx(right, left)
    phase_product(builder, right, child, mask[6:], kernel(6))
    builder.free(mask)
    apply_inplace_linear(builder, child, quadratic_basis(6)['to_tower'])
    child_mask = builder.alloc_bits(6)
    builder.hmr(child, child_mask)
    builder.free(child)
    active = builder.alloc_bits(1)
    builder.bit_store(active, False)
    builder.bit_store(active[0], True, control=child_mask)
    builder.push_condition(active[0])
    original_child = init_norm(builder, left, right, info['delta'])
    Narrow.phase_inverse_six(builder, original_child, child_mask)
    erase_norm(builder, left, right, original_child, info['delta'])
    builder.free(original_child)
    builder.pop_condition()
    builder.bit_store(active, False)
    builder.free(active)
    builder.free(child_mask)
    # Existing phase_inverse_six accounts for4/64. This is only the extra15.
    Narrow.record_uniform_hmr_event('last_return_child_norm_guard', 15, 6)
    apply_inplace_linear(builder, original_norm, info['from_tower'])
    erase_norm(builder, source[:12], source[12:], original_norm, delta)
    builder.free(original_norm)


def restore_with_shared_norm(builder, source, target, record, *,
                             next_word=None, next_input_record=None):
    """Use the new lifecycle only when the public last-return shape has no next."""
    assert Original.A is A and Original.Prior is Nested, 'Requires the selected nested provider'
    if next_word is not None:
        return Original.restore_with_shared_norm(builder, source, target, record,
                    next_word=next_word, next_input_record=next_input_record)
    assert next_input_record is None
    assert record.builder_id == id(builder) and not record.closed
    assert tuple(source) == record.source and tuple(target) == record.target
    delta = record.delta
    head_return = A.emit_prefix(builder, source, target, delta)
    inverse_norm = init_norm(builder, source[:12], source[12:], delta)
    norm_masks, child = inverse_twelve_keep_child(builder, inverse_norm)
    A._repay_norm_source_masks(builder, source, norm_masks, delta)

    builder.cz(record.old_target_mask, target)
    builder.free(record.old_target_mask)
    builder.cx(source[12:], source[:12])
    phase_product(builder, source, target,
                  km.array([*record.adjoint_masks[0], *record.adjoint_masks[1]]),
                  A.tensor24(delta))
    builder.cx(source[12:], source[:12])
    for mask in record.adjoint_masks:
        builder.free(mask)
    builder.cz(record.inverse_norm_mask, inverse_norm)
    builder.free(record.inverse_norm_mask)
    Original._quotient_phase_with_norm(builder, source, inverse_norm, target,
                                      head_return.old_target_mask, delta)
    A.free_product_mask(builder, head_return)
    _repay_inverse_and_child(builder, source, inverse_norm, child, delta)
    record.closed = True


def source_ledger():
    return dict(status='SOURCE_MODEL_NATIVE_PENDING', eligible_production_calls=1,
                source_domain='unit K24 source, arbitrary target; no next word',
                return_static_T=352, prefix_static_T=291, pair_static_T=643,
                helpers=24, whole_decoder_peak_Q=889,
                return_uniform_HMR_mean_T=352-19/64-84/(1 << 24),
                pair_uniform_HMR_mean_T=643-19/64-84/(1 << 24),
                static_saving=8, mean_saving=8+19/64-27/4096,
                skipped_next_return_candidates=32, unretimed_next_return_helpers=30,
                new_population_event=False)
