# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""HMR-first erasure of a known zero predicate, with a fair-mask branch."""


def phase_zero(builder,word,mask,clean=None,quantum_control=None):
    """Apply (-1)^(mask*[word=0]); mask is a preserved classical bit.

    A supplied clean qubit may provide the first of the ten conjunctions.
    It is zero again on return. No quantum predicate controls the branch.
    """
    assert len(word)>=3
    builder.push_condition(mask)
    builder.x(word)
    owned=builder.alloc_qubits(len(word)-2-int(clean is not None))
    chain=([clean] if clean is not None else [])+list(owned)
    builder.init_and(word[0],word[1],chain[0])
    for i in range(1,len(chain)):builder.init_and(chain[i-1],word[i+1],chain[i])
    if quantum_control is None:builder.cz(chain[-1],word[-1])
    else:builder.ccz(quantum_control,chain[-1],word[-1])
    for i in reversed(range(1,len(chain))):builder.del_and(chain[i-1],word[i+1],chain[i])
    builder.del_and(word[0],word[1],chain[0]);builder.free(owned)
    builder.x(word);builder.pop_condition()


def erase(builder,word,flag):
    """Promise flag==[word=0]. Reset it with10 static/5 expected T.

    The caller retains ownership of the now-zero flag qubit. Its reset
    wire is reused as phase workspace; no mask survives this call.
    """
    assert len(flag)==1
    mask=builder.alloc_bits(1);builder.hmr(flag,mask)
    phase_zero(builder,word,mask[0],flag[0]);builder.free(mask)

