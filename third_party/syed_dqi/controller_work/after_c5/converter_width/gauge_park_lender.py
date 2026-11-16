# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""One-wire loan and sparse gauge-chart sentinel for a fixed top frame.

The external gauge contract is f=1 => mu=0. A chosen source word u must be
a unit and must not be read while parked. CSWAP(f,u,mu) makes u=0 exactly
when f=1. HMR releases f for temporary work. A later zero query of u both
restores f and repays that HMR mask before the swap is undone.

No arbitrary dirty wire is declared clean. The original gauge wire stays
allocated in the underlying builder and is loaned only after its HMR.
Persistent reciprocal outputs and one-bit predicates cannot borrow it.
"""
from contextlib import contextmanager
import cw_paths  # noqa: F401
import kickmix as km
from coherent_border import toggle_zero
from compact_inverse22 import compact_inverse_twelve as _inverse22
from tower_inverse import xor_product, phase_product, kernel


class GaugeLender:
    def __init__(self, builder, wire):
        self.builder = builder
        self.wire = wire
        self.enabled = False
        self.leased = False

    @property
    def idle(self):
        return not self.leased

    def __getattr__(self, name):
        return getattr(self.builder, name)

    def alloc_qubits(self, count):
        # Every one-bit local predicate can survive across a source seam.
        # It must never receive the gauge wire needed at that seam.
        if count < 2 or not self.enabled or self.leased:
            return self.builder.alloc_qubits(count)
        self.leased = True
        rest = list(self.builder.alloc_qubits(count - 1))
        return km.array([self.wire, *rest])

    def free(self, values):
        try:
            entries = list(values)
        except TypeError:
            entries = [values]
        loan = [q for q in entries if isinstance(q, km.q) and q == self.wire]
        if loan:
            assert len(loan) == 1 and self.leased
            self.leased = False
        rest = [q for q in entries if not (isinstance(q, km.q) and q == self.wire)]
        if rest:
            self.builder.free(km.array(rest))

    @contextmanager
    def no_loan(self):
        assert self.idle, 'A closed temporary must end before a persistent reciprocal'
        prior = self.enabled
        self.enabled = False
        try:
            yield
        finally:
            assert self.idle
            self.enabled = prior


def compact_inverse_twelve(builder, source, zero_flag=None):
    """65 T/22 helpers, with an ordinary-owned persistent output word."""
    assert isinstance(builder, GaugeLender)
    with builder.no_loan():
        return _inverse22(builder, source, zero_flag)


class GaugeCarrier:
    def __init__(self, builder, flag, other):
        assert isinstance(builder, GaugeLender) and flag == builder.wire
        assert len(other) == 12 and flag not in set(other)
        self.b = builder
        self.flag = flag
        self.other = other
        self.anchor = None
        self.mask = None
        self.parks = 0
        self.unparks = 0
        self.events = []

    def assert_anchor(self, unit):
        assert self.anchor is not None and tuple(unit) == tuple(self.anchor)

    def park(self, unit, label=''):
        b = self.b
        assert self.anchor is None and self.mask is None and b.idle and not b.enabled
        assert len(unit) == 12 and not set(unit) & set(self.other)
        assert self.flag not in set(unit)
        b.cswap(self.flag, unit, self.other)
        self.mask = b.alloc_bits(1)
        b.hmr(km.array([self.flag]), self.mask)
        self.anchor = unit
        self.parks += 1
        self.events.append(('park', label))
        b.enabled = True

    def unpark(self, label=''):
        b = self.b
        assert self.anchor is not None and self.mask is not None and b.idle and b.enabled
        b.enabled = False
        toggle_zero(b, self.anchor, self.flag)
        b.cz(self.mask[0], self.flag)
        b.free(self.mask)
        self.mask = None
        b.cswap(self.flag, self.anchor, self.other)
        self.anchor = None
        self.unparks += 1
        self.events.append(('unpark', label))

    def move(self, unit, label='', between=lambda: None):
        self.unpark(label)
        between()
        self.park(unit, label)

    def clean_boundary(self):
        assert self.anchor is None and self.mask is None and self.b.idle and not self.b.enabled


def deferred_scale(builder, target, multiplier):
    """42 T consuming scale; return the exact old-target HMR mask.

The unit multiplier is live. The inverse multiplier may currently be the
parked gauge sentinel, so this helper deliberately does not read it.
"""
    temporary = builder.alloc_qubits(12)
    xor_product(builder, target, multiplier, temporary)
    builder.swap(target, temporary)
    mask = builder.alloc_bits(12)
    builder.hmr(temporary, mask)
    builder.free(temporary)
    return mask


def repay_scale(builder, target, inverse_multiplier, mask):
    phase_product(builder, target, inverse_multiplier, mask, kernel(12))
    builder.free(mask)

