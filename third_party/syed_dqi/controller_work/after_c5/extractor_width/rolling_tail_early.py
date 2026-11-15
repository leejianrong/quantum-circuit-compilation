# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""One live rolling flag across normalization, with the exact C5 domain.

After the selected pair is (u,v), u is a unit and
zero(v)=zero(v/u)=f_previous XOR f_current.  Erase the previous flag on v
BEFORE normalization.  On return reconstruct it on the restored v AFTER
normalization has been undone.  The former clean spare is allocated only
around the two-flag predicate/swap boundary, never across arithmetic.

The 23-T zero queries, 24-T swaps and classically skipped 22-T HMR phases
are unchanged.  Every phase mask is paid on the same Boolean function as
the C5 emitter.  This class changes no accepted-domain condition.
"""
from dataclasses import dataclass
import ew_paths  # noqa: F401
import kickmix as km
import rolling_tail as Base
import rolling_tail_conditional as Conditional

zero_xor = Base.zero_xor
zero_phase = Conditional.zero_phase
erase_zero_flag = Conditional.erase_zero_flag
gauge_prefix = Conditional.gauge_prefix
gauge_return = Conditional.gauge_return
validate_head_profile = Base.validate_head_profile


@dataclass(frozen=True)
class SlotToken:
    index: int
    current: object
    first_boundary: bool


class RollingTail:
    def __init__(self, builder, first_index=15, stop_index=35):
        assert 0 <= first_index < stop_index <= 35
        self.builder = builder
        self.first_index, self.stop_index = first_index, stop_index
        self.current = builder.alloc_qubits(1)[0]  # known f_(first-1)=0
        self.spare = None
        self.forward_next, self.return_next = first_index, None
        self.pending, self.seed_mask = None, None
        self.released = False

    def begin_slot(self, numerator, denominator, index):
        assert self.pending is None and index == self.forward_next
        assert self.first_index <= index < self.stop_index
        assert len(numerator) == len(denominator) == 24
        first = index == self.first_index
        previous = None if first else self.current
        current = self.current if first else self.builder.alloc_qubits(1)[0]
        assert current not in numerator and current not in denominator
        zero_xor(self.builder, numerator, current)
        self.builder.cswap(current, numerator, denominator)
        if previous is not None:
            self.builder.cx(current, previous)
            # Selected v, not the not-yet-produced normalized head.
            erase_zero_flag(self.builder, denominator, previous)
            self.builder.free(km.array([previous]))
        self.current = current
        token = SlotToken(index, current, first)
        self.pending = token
        return token

    def finish_slot(self, head, token):
        assert token == self.pending and len(head) == 24
        self.pending = None
        self.forward_next += 1

    def release_spare(self):
        assert self.forward_next == self.stop_index and self.pending is None
        assert not self.released and self.spare is None
        self.released = True  # no physical spare survives a slot

    def seed_prefix(self, numerator_constant, denominator_x):
        assert self.released and self.seed_mask is None
        assert self.current is not None
        self.builder.cswap(self.current, numerator_constant, denominator_x)
        self.seed_mask = self.builder.alloc_bits(1)
        self.builder.hmr(km.array([self.current]), self.seed_mask)
        self.builder.free(km.array([self.current]))
        self.current = None

    def seed_return(self, numerator_constant, denominator_x):
        assert self.current is None and self.seed_mask is not None
        self.current = self.builder.alloc_qubits(1)[0]
        zero_xor(self.builder, numerator_constant, self.current)
        self.builder.cz(self.seed_mask[0], self.current)
        self.builder.free(self.seed_mask)
        self.seed_mask = None
        self.builder.cswap(self.current, numerator_constant, denominator_x)

    def resume_return(self):
        assert self.released and self.current is not None and self.spare is None
        self.return_next = self.stop_index - 1

    def begin_return(self, head, index):
        assert self.pending is None and index == self.return_next
        assert len(head) == 24 and self.current is not None
        token = SlotToken(index, self.current, index == self.first_index)
        self.pending = token
        return token

    def finish_return(self, numerator, denominator, token):
        assert token == self.pending
        # u and v have now been restored.  Both flags exist only here.
        previous = None
        if not token.first_boundary:
            previous = self.builder.alloc_qubits(1)[0]
            zero_xor(self.builder, denominator, previous)
            self.builder.cx(token.current, previous)
        self.builder.cswap(token.current, numerator, denominator)
        erase_zero_flag(self.builder, numerator, token.current)
        self.builder.free(km.array([token.current]))
        self.current = previous
        self.pending = None
        self.return_next -= 1

    def close(self):
        assert self.return_next == self.first_index - 1
        assert self.pending is None and self.seed_mask is None
        assert self.current is None and self.spare is None


def source_ledger(j_min=15):
    out = Conditional.source_ledger(j_min)
    out.update(status='SOURCE_MODEL_NOT_YET_NATIVE_CHECKED',
               variant='early previous-flag erase; delayed return query',
               arithmetic_flag_wires=1, flag_wires_max=2,
               modeled_raw_peak_Q_for_864_data=889,
               raw_controller_T_delta=0,
               seed_closure_caveat='Use scalar_seed_padded for a full Q889 seam.')
    return out
