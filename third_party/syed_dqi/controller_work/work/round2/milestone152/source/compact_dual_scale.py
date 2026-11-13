# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""228-T nonzero dual scaling using24 scratch, including inverse cleanup."""
from compact_inverse import compact_inverse_twelve
from projective_carry import erase_inverse_word
from dual_scale import scale_word,FIELD
from tower_inverse import xor_product

def emit(builder,a,b,c,d,reverse=False,trim=False):
    inverse=compact_inverse_twelve(builder,c)
    temporary=builder.alloc_qubits(12)
    if reverse:
        scale_word(builder,a,inverse,c,temporary)
        xor_product(builder,a,d,b)
        scale_word(builder,b,inverse,c,temporary)
    else:
        scale_word(builder,b,c,inverse,temporary)
        xor_product(builder,a,d,b)
        scale_word(builder,a,c,inverse,temporary)
    builder.free(temporary)
    erase_inverse_word(builder,c,inverse)
