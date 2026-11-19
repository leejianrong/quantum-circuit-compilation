# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Agent width: replay a donor kmx block plan (scripts/make_block_plan.py) through the builder.

wire_map: donor wire -> our qubit for every donor wire live at block entry that the block may touch (by owner role).
ext_bits: donor bit name -> our classical bit for bits created before the block. Scratch qubits are allocated at first
touch and freed when the donor wire is identically zero; donor HMR bits are fresh builder bits (freed when the donor
name is re-measured or at block end). Returns the final donor-wire -> qubit map.
"""


def replay(builder, plan, wire_map, ext_bits=None):
    h = dict(wire_map)
    bits = dict(ext_bits or {})
    own_bits = {}
    ccx = 0

    def q(w):
        if w not in h:
            h[w] = builder.alloc_qubits(1)[0]
        return h[w]

    def bit(name):
        return bits[name]
    for item in plan['plan']:
        kind = item[0]
        if kind == 'ZERO':
            w = item[1]
            if w in h:
                builder.free(h.pop(w))
            continue
        _, qs, bs, cond = item
        if kind == 'PUSH_CONDITION':
            builder.push_condition(bit(cond)); continue
        if kind == 'POP_CONDITION':
            builder.pop_condition(); continue
        if kind == 'HMR':
            name = bs[0]
            if name in own_bits:
                builder.free(own_bits.pop(name))
            b = builder.alloc_bits(1)[0]
            own_bits[name] = b
            bits[name] = b
            assert cond is None
            builder.hmr(q(qs[0]), b)
            continue
        if cond is not None:
            builder.push_condition(bit(cond))
        args = [q(w) for w in qs]
        if kind == 'X':
            builder.x(args[0])
        elif kind == 'Z':
            builder.z(args[0])
        elif kind == 'CX':
            builder.cx(args[0], args[1])
        elif kind == 'CZ':
            builder.cz(args[0], args[1])
        elif kind == 'CCX':
            builder.ccx(args[0], args[1], args[2]); ccx += 1
        elif kind == 'SWAP':
            builder.swap(args[0], args[1])
        else:
            raise AssertionError(('unsupported donor op', kind))
        if cond is not None:
            builder.pop_condition()
    for name, b in own_bits.items():
        builder.free(b)
    assert ccx == plan['ccx']
    return h
