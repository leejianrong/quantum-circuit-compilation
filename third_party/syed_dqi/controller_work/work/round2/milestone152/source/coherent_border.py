# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""Paired coherent normal/simple-zero dual border, with an explicit live flag."""
from dataclasses import dataclass
import kickmix as km
from tower_inverse import xor_product,phase_product,kernel
from low_cached_arithmetic import scale_words,repay
from norm_cached_field import invert_twelve

@dataclass(frozen=True)
class BorderRecord:
    zero_flag:object
    masks:tuple
    builder_id:int

def toggle_zero(builder,word,flag):
    assert len(word)>=3
    builder.x(word);chain=builder.alloc_qubits(len(word)-2)
    builder.init_and(word[0],word[1],chain[0])
    for i in range(1,len(chain)):builder.init_and(chain[i-1],word[i+1],chain[i])
    builder.ccx(chain[-1],word[-1],flag)
    for i in reversed(range(1,len(chain))):builder.del_and(chain[i-1],word[i+1],chain[i])
    builder.del_and(word[0],word[1],chain[0]);builder.free(chain);builder.x(word)

def normal_cross(builder,a,d,b,zero):
    masked=builder.alloc_qubits(12);builder.x(zero)
    builder.init_and(zero,d,masked)
    xor_product(builder,a,masked,b)
    builder.del_and(zero,d,masked);builder.x(zero);builder.free(masked)

def forward(builder,a,b,c,d):
    """Promise c!=0 or d!=0; the zero flag stays live until paired reverse.

    Forward measurement phases are deferred. Restore all four output words and
    the flag after any diagonal interlude before invoking reverse.
    """
    flag=builder.alloc_qubits(1);toggle_zero(builder,c,flag[0])
    builder.cswap(flag[0],c,d);builder.cswap(flag[0],b,d)
    bmask=scale_words(builder,[b],c,defer=True)
    normal_cross(builder,a,d,b,flag[0])
    amask=scale_words(builder,[a],c,defer=True)
    return BorderRecord(flag,tuple(bmask+amask),id(builder))

def reverse(builder,a,b,c,d,record):
    assert id(builder)==record.builder_id
    flag=record.zero_flag
    invert_twelve(builder,c)
    amask=scale_words(builder,[a],c,defer=True)
    normal_cross(builder,a,d,b,flag[0])
    bmask=scale_words(builder,[b],c,defer=True)
    invert_twelve(builder,c)
    for word,mask in zip([a,b],amask+bmask):
        phase_product(builder,word,c,mask,kernel(12));builder.free(mask)
    repay(builder,[b,a],record.masks)
    builder.cswap(flag[0],b,d);builder.cswap(flag[0],c,d)
    toggle_zero(builder,c,flag[0]);builder.free(flag)

def model():return dict(forward_T=173,reverse_T=317,roundtrip_T=490,
                       expected_roundtrip_T=489.8125,arithmetic_scratch=18,
                       retained_flag=1,Q_with852_data_and6_caller_bits=877)
