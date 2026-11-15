# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Zero-safe third public pivot with an explicitly matched predicate debt.

The two earlier heads are coefficient words. The current word enters as
the raw residue at public index2 and leaves as the head in residue view.
The caller supplies a zero24-bit norm bank and one owned zero predicate.
The prefix resets that predicate by HMR without freeing its physical wire.
Closing allocates and retires its own predicate after the ordinary tail
controller has closed. This is a component, not an admitted-domain test.
"""
from dataclasses import dataclass
from pathlib import Path
import sys

V5 = Path(__file__).resolve().parents[1]/'v5'
if str(V5) not in sys.path:
    sys.path.insert(0, str(V5))
import kickmix as km
import direct_carry_first2 as Base
import inverse_retained_norm_deferred as Norm

Tail = Base.Tail


@dataclass
class Record:
    builder_id: int
    source: tuple
    heads: tuple
    inverses: tuple
    zero_mask: object
    borrowed_zero_flag: object
    prefix_static_T: int = 620
    closed: bool = False


def _contract(heads, current, bank, flag=None):
    if len(heads) != 2 or any(len(word) != 24 for word in (*heads, current, bank)):
        raise ValueError('two heads, current and clean bank must each have24 bits')
    wires = [wire for word in (*heads, current, bank) for wire in word]
    if flag is not None:
        wires.append(flag)
    if any(not isinstance(wire, km.q) for wire in wires):
        raise TypeError('this component requires quantum operands')
    if len(wires) != len(set(wires)):
        raise ValueError('source, heads, clean bank and predicate must be disjoint')


def _constants():
    first = Base.node(0)[1] ^ Base.node(2)[1]
    second = Base.node(1)[1] ^ Base.node(2)[1]
    assert (first, second) == (20, 18)
    return first, second


def _add_head(builder, head, current, zero_flag=None):
    Base.node_view(builder, head, 2)
    builder.cx(head, current)
    if zero_flag is not None:
        # The unconditional term and this correction give add iff nonzero.
        builder.ccx(zero_flag, head, current)
    Base.node_view(builder, head, 2)


def emit_prefix(builder, heads, current, clean_bank, zero_flag):
    """620 fixed T; return three six-bit debts and the actual zero mask.

    The input domain is the existing active third-pivot domain: the ordinary
    two queried numerator/denominator coordinates are nonzero. Raw current
    may be zero. The owned flag and all24 bank bits must enter zero and
    return zero. Neither owned resource is freed by this function.
    """
    heads = tuple(heads)
    _contract(heads, current, clean_bank, zero_flag)
    assert Norm.Arithmetic is Base.A and Tail is Base.Tail
    first, second = _constants()
    Tail.zero_xor(builder, current, zero_flag)
    inner = Norm.inverse_prefix_with_bank(builder, current, clean_bank)
    _add_head(builder, heads[0], current, zero_flag)
    zero_mask = builder.alloc_bits(1)
    builder.hmr(km.array([zero_flag]), zero_mask)
    # HMR reset the caller-owned predicate; its allocation remains owned.
    middle = Norm.inverse_prefix_with_bank(builder, current, clean_bank)
    Base.public_scale(builder, current, first)
    _add_head(builder, heads[1], current)
    Base.public_scale(builder, current, Base.FIELD.invert(second))
    outer = Norm.inverse_prefix_with_bank(builder, current, clean_bank)
    return Record(id(builder), tuple(current), tuple(tuple(h) for h in heads),
                  (inner, middle, outer), zero_mask, zero_flag)


def emit_closing(builder, heads, current, clean_bank, record):
    """654 static T, 3 fresh six-bit phase masks and one fresh bit mask.

    The matching prefix head and both original earlier heads must be present.
    Closing restores raw current. The prefix zero-mask is paid at zero(u),
    where u=Y/(1+A*Y). The new flag's HMR phase is paid on restored Y.
    At most25 new quantum wires are live, including this new predicate;
    the production caller has864 retained wires at entry, hence Q889.
    """
    heads = tuple(heads)
    _contract(heads, current, clean_bank)
    if (not isinstance(record, Record) or record.closed or
            record.builder_id != id(builder) or record.source != tuple(current) or
            record.heads != tuple(tuple(h) for h in heads) or record.zero_mask is None):
        raise ValueError('closing requires this builder and the exact open prefix record')
    assert Norm.Arithmetic is Base.A and Tail is Base.Tail
    first, second = _constants()
    inner, middle, outer = record.inverses
    receipts = [Norm.inverse_return_with_bank(builder, current, clean_bank, outer)]
    Base.public_scale(builder, current, second)
    _add_head(builder, heads[1], current)
    Base.public_scale(builder, current, Base.FIELD.invert(first))
    flag = builder.alloc_qubits(1)
    Tail.zero_xor(builder, current, flag[0])
    builder.cz(record.zero_mask[0], flag[0])
    builder.free(record.zero_mask)
    record.zero_mask = None
    receipts.append(Norm.inverse_return_with_bank(builder, current, clean_bank, middle))
    _add_head(builder, heads[0], current, flag[0])
    receipts.append(Norm.inverse_return_with_bank(builder, current, clean_bank, inner))
    Tail.erase_zero_flag(builder, current, flag[0])
    builder.free(flag)
    assert all(item.closed for item in record.inverses)
    record.closed = True
    return dict(return_static_T=654, prefix_static_T=620,
                prefix_zero_mask_paid=True, return_zero_flag_retired=True,
                inverse_receipts=receipts, closed_inverse_calls=3,
                owned_clean_bank_bits=24, maximum_fresh_return_wires=25)
