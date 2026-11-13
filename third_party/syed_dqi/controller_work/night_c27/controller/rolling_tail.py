# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Native rolling tail flags, phase repayment, and the inverse seed seam.

This module owns only the controller.  The caller supplies the actual queried
projective pair (n, d), a unit-preserving normalizer, and the physical seed seam.
It never receives a compiler-supplied terminal index or a list of tail flags.

At a possible tail position the admitted invariant is

    zero(normalized_head) == previous_flag XOR zero(queried_numerator).

Active zero heads and active zero queried numerators are outside that contract.
The circuit does not reject such inputs: their probability is an independent
obligation of the complete decoder's failure classifier.

All conjunction ladders below run unconditionally.  Only a Clifford phase is
classically masked.  Consequently their static and measured mean T counts agree.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import kickmix as km


def _array(bits):
    return km.array(list(bits))


def zero_xor(builder, source, target):
    """XOR [source == 0] into target, using n-1 T and n-2 clean work bits.

    The target may be dirty.  Source and every work bit are restored.  The final
    conjunction is an ordinary CCX, so no promise on the old target is needed.
    """
    assert len(source) >= 2 and target not in source
    builder.x(source)
    if len(source) == 2:
        builder.ccx(source[0], source[1], target)
    else:
        work = builder.alloc_qubits(len(source) - 2)
        builder.init_and(source[0], source[1], work[0])
        for k in range(1, len(work)):
            builder.init_and(work[k - 1], source[k + 1], work[k])
        builder.ccx(work[-1], source[-1], target)
        for k in reversed(range(1, len(work))):
            builder.del_and(work[k - 1], source[k + 1], work[k])
        builder.del_and(source[0], source[1], work[0])
        builder.free(work)
    builder.x(source)


def zero_phase(builder, source, classical_mask):
    """Apply (-1)^(classical_mask * [source == 0]), using n-2 T.

    The AND ladder is unconditional.  This deliberately does not take a mean-T
    credit for skipping a fair-mask branch; only the last CZ is conditional.
    """
    assert len(source) >= 2
    builder.x(source)
    work = builder.alloc_qubits(len(source) - 2) if len(source) > 2 else None
    if work is not None:
        builder.init_and(source[0], source[1], work[0])
        for k in range(1, len(work)):
            builder.init_and(work[k - 1], source[k + 1], work[k])
        left, right = work[-1], source[-1]
    else:
        left, right = source
    builder.push_condition(classical_mask)
    builder.cz(left, right)
    builder.pop_condition()
    if work is not None:
        for k in reversed(range(1, len(work))):
            builder.del_and(work[k - 1], source[k + 1], work[k])
        builder.del_and(source[0], source[1], work[0])
        builder.free(work)
    builder.x(source)


def erase_zero_flag(builder, source, flag):
    """HMR-reset flag, promised equal to [source == 0], and repay its phase."""
    measured = builder.alloc_bits(1)
    builder.hmr(_array([flag]), measured)
    zero_phase(builder, source, measured[0])
    builder.free(measured)


@dataclass(frozen=True)
class SlotToken:
    index: int
    previous: Any
    current: Any
    first_boundary: bool


class RollingTail:
    """Two physical flag wires, alternating roles at every public tail slot.

    Forward order: begin_slot(n,d,i), caller normalizes the selected unit pair,
    finish_slot(head,token).  The normalizer must preserve the two logical flags.

    Return order: begin_return(head,i), caller unnormalizes, finish_return(n,d,t).
    Here n,d must again be the SELECTED unit/other pair, before undoing our swap.
    finish_return restores the actual original queried pair and pays its mask.

    The known first previous flag is zero.  The first boundary omits a forward
    22-T phase query and a return 23-T predicate query, saving exactly 45 T.
    """

    def __init__(self, builder, first_index=15, stop_index=35):
        assert 0 <= first_index < stop_index <= 35
        self.builder = builder
        self.first_index = first_index
        self.stop_index = stop_index
        flags = builder.alloc_qubits(2)
        self.current, self.spare = flags[0], flags[1]
        self.forward_next = first_index
        self.return_next = None
        self.pending = None
        self.seed_mask = None

    def begin_slot(self, numerator, denominator, index):
        assert self.pending is None and index == self.forward_next
        assert self.first_index <= index < self.stop_index
        assert len(numerator) == len(denominator) == 24
        assert len(set([*numerator, *denominator, self.current, self.spare])) == 50
        token = SlotToken(index, self.current, self.spare,
                          index == self.first_index)
        zero_xor(self.builder, numerator, token.current)
        self.builder.cswap(token.current, numerator, denominator)
        self.pending = token
        return token

    def finish_slot(self, head, token):
        assert token == self.pending and len(head) == 24
        if not token.first_boundary:
            self.builder.cx(token.current, token.previous)
            erase_zero_flag(self.builder, head, token.previous)
        self.current, self.spare = token.current, token.previous
        self.pending = None
        self.forward_next += 1

    def release_spare(self):
        """Free the clean second wire before the gauge allocates its chart bit."""
        assert self.forward_next == self.stop_index and self.pending is None
        assert self.spare is not None
        self.builder.free(_array([self.spare]))
        self.spare = None

    def seed_prefix(self, numerator_constant, denominator_x):
        """Do the physical 12-bit seed swap, then HMR and free final flag.

        Inputs are AFTER the public r=1 unfold.  N0 is a unit lambda.  If the
        final flag is one, Dx is zero.  It follows that the post-swap zero(N0)
        is exactly that flag.  Its classical phase debt remains open.
        """
        assert self.spare is None and self.seed_mask is None
        assert len(numerator_constant) == len(denominator_x) == 12
        self.builder.cswap(self.current, numerator_constant, denominator_x)
        self.seed_mask = self.builder.alloc_bits(1)
        self.builder.hmr(_array([self.current]), self.seed_mask)
        self.builder.free(_array([self.current]))
        self.current = None

    def seed_return(self, numerator_constant, denominator_x):
        """11-T seam query repays the open mask and controls the inverse swap."""
        assert self.current is None and self.seed_mask is not None
        flag = self.builder.alloc_qubits(1)
        self.current = flag[0]
        zero_xor(self.builder, numerator_constant, self.current)
        self.builder.cz(self.seed_mask[0], self.current)
        self.builder.free(self.seed_mask)
        self.seed_mask = None
        self.builder.cswap(self.current, numerator_constant, denominator_x)

    def resume_return(self):
        """Call after the gauge chart has returned and freed its chart bit."""
        assert self.current is not None and self.spare is None
        self.spare = self.builder.alloc_qubits(1)[0]
        self.return_next = self.stop_index - 1

    def begin_return(self, head, index):
        assert self.pending is None and index == self.return_next
        assert len(head) == 24
        token = SlotToken(index, self.spare, self.current,
                          index == self.first_index)
        if not token.first_boundary:
            zero_xor(self.builder, head, token.previous)
            self.builder.cx(token.current, token.previous)
        self.pending = token
        return token

    def finish_return(self, numerator, denominator, token):
        assert token == self.pending
        assert len(numerator) == len(denominator) == 24
        self.builder.cswap(token.current, numerator, denominator)
        erase_zero_flag(self.builder, numerator, token.current)
        self.current, self.spare = token.previous, token.current
        self.pending = None
        self.return_next -= 1

    def close(self):
        assert self.return_next == self.first_index - 1
        assert self.pending is None and self.seed_mask is None
        self.builder.free(_array([self.current, self.spare]))
        self.current = self.spare = None


@dataclass(frozen=True)
class GaugeRecord:
    flag: Any


def gauge_prefix(builder, carry):
    """Select a nonzero 12-bit half without dividing the other half.

    The 24-bit carry must be nonzero.  Output low half is lambda, output high
    half is the unscaled other coordinate.  The retained chart bit costs one
    qubit.  This implementation has a 23-T prefix and 22-T return, total 45 T.
    """
    assert len(carry) == 24
    flag = builder.alloc_qubits(1)
    zero_xor(builder, carry[:12], flag[0])
    builder.cswap(flag[0], carry[:12], carry[12:])
    return GaugeRecord(flag[0])


def gauge_return(builder, carry, record):
    builder.cswap(record.flag, carry[:12], carry[12:])
    erase_zero_flag(builder, carry[:12], record.flag)
    builder.free(_array([record.flag]))


def validate_head_profile(heads, support, j_min=15):
    """Classical admitted-domain check; it is NOT a circuit rejection gadget."""
    if len(heads) != 35 or not j_min <= support <= 35:
        return False
    return all(heads[i] != 0 for i in range(support)) and all(
        heads[i] == 0 for i in range(support, 35))


def source_ledger(j_min=15):
    count = 35 - j_min
    return {
        "status": "SOURCE_MODEL_UNTIL_NATIVE_CHECK_PASSES",
        "possible_tail_slots": count,
        "slot_prefix_T": 69,
        "slot_return_T": 69,
        "first_boundary_saving_T": 45,
        "seed_pair_T": 24,
        "reverse_seed_query_T": 11,
        "controller_prefix_T": 69 * count - 10,
        "controller_return_T": 69 * count,
        "controller_pair_T": 138 * count - 10,
        "gauge_prefix_T": 23,
        "gauge_return_T": 22,
        "gauge_pair_T": 45,
        "flag_wires_max": 2,
        "query_work_max": 22,
        "normalizer_work_contract": 24,
        "modeled_peak_Q_for_864_data": 890,
        "unpaid_by_this_module": [
            "the actual raw-query projective producer and its phase interface",
            "native normalizer and its deferred source/target debts",
            "the physical r=1 polynomial unfold that establishes the seed seam",
            "the complete new failure classifier and its statistical reservation",
        ],
    }
