# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""The physical r=0 scalar seed: 84-T prefix, 176-T closing, 260-T pair.

The source lambda is a preserved unit GF4096 word.  The two head coefficient
words P0,P1 are arbitrary, including both zero.  Prefix consumes them into
lambda*P0,lambda*P1 and retains the two old-head HMR masks.  Thus the three words
are exactly Nconstant=lambda, Dconstant=lambda*P0, Dx=lambda*P1.

The separate rolling-tail seed swap may temporarily move lambda into Dx.  It
MUST be undone before emit_closing, which requires the same preserved source.
No controlled swap, gauge chart, tail predicate, or GF24 node-basis conversion
is included in the 260-T arithmetic count.
"""

from dataclasses import dataclass
from pathlib import Path
import sys

WORK = Path(__file__).resolve().parents[2]
for directory in (WORK / "work/round2/milestone152/source", WORK / "night_schedule"):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import kickmix as km
from compact_inverse22 import compact_inverse_twelve
from projective_carry import erase_inverse_word
from tower_inverse import xor_product, phase_product, kernel
from quantum_reciprocal import xor_linear

FIELD = km.GF2Field(12)


@dataclass
class SeedRecord:
    builder_id: int
    source: tuple
    targets: tuple
    old_masks: tuple
    closed: bool = False


def node_coefficients_inplace(builder, head, index):
    """Common-K value a+b*theta <-> coefficients (a+(2i)b,b), zero T."""
    assert len(head) == 24 and 0 <= index < 35
    columns = tuple(FIELD.mul(2 * index, 1 << k) for k in range(12))
    xor_linear(builder, head[12:], head[:12], columns)


def emit_prefix(builder, scale, head):
    assert len(scale) == 12 and len(head) == 24
    assert len(set([*scale, *head])) == 36
    temporary = builder.alloc_qubits(12)
    masks = []
    for target in (head[:12], head[12:]):
        xor_product(builder, scale, target, temporary)
        builder.swap(target, temporary)
        mask = builder.alloc_bits(12)
        builder.hmr(temporary, mask)
        masks.append(mask)
    builder.free(temporary)
    return SeedRecord(id(builder), tuple(scale), tuple(head), tuple(masks))


def emit_closing(builder, scale, head, record):
    assert not record.closed and record.builder_id == id(builder)
    assert tuple(scale) == record.source and tuple(head) == record.targets
    inverse = compact_inverse_twelve(builder, scale)
    temporary = builder.alloc_qubits(12)
    for target, original_mask in zip((head[:12], head[12:]), record.old_masks):
        xor_product(builder, inverse, target, temporary)
        builder.swap(target, temporary)
        product_mask = builder.alloc_bits(12)
        builder.hmr(temporary, product_mask)
        phase_product(builder, scale, target, product_mask, kernel(12))
        builder.free(product_mask)
        builder.cz(original_mask, target)
        builder.free(original_mask)
    builder.free(temporary)
    erase_inverse_word(builder, scale, inverse)
    record.closed = True


def source_ledger():
    return {"status": "SOURCE_MODEL_UNTIL_NATIVE_CHECK_PASSES",
            "prefix_T": 84,
            "closing_T": 176,
            "pair_T": 260,
            "closing_details": {"preserved_reciprocal": 65,
                                "two_consuming_products": 84,
                                "reciprocal_erasure_phase": 27},
            "peak_helpers": 24,
            "prefix_helpers": 12,
            "requires": "The exact original unit scale is restored before closing.",
            "excludes": ["35-T paired rolling seed control", "45-T gauge chart",
                         "zero-source admission", "the remaining polynomial synthesis"]}
