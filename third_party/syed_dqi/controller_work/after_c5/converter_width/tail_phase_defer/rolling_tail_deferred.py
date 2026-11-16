# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Defer each previous-tail-flag HMR phase to its existing return query.

This is an isolated post-C5 candidate.  The accepted source and both integration
branches are unchanged.  The public schedule, zero queries, swaps, normalizer
contract and accepted inputs are identical to rolling_tail_early.

After begin_slot selects the unit u, the other coordinate v obeys
    zero(v) = f_previous XOR f_current.
HMR of the XORed previous flag therefore creates exactly m_i*zero(v).  Retain
its classical mask through the forward arithmetic and diagonal oracle.  At
the matching finish_return the existing zero_xor(restored_v, previous) already
recreates this predicate.  Pay CZ(m_i, previous) BEFORE XORing f_current into
previous.  No new query or quantum wire is needed.

The open prefix is deliberately phase-debtful.  Each debt is owned by its
public slot index and retired exactly once; close rejects any outstanding one.
"""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
AFTER = HERE.parents[1]
if str(AFTER / 'extractor_width') not in sys.path:
    sys.path.insert(0, str(AFTER / 'extractor_width'))

import ew_paths  # noqa: E402,F401
import kickmix as km  # noqa: E402
import rolling_tail_early as Early  # noqa: E402

zero_xor = Early.zero_xor
zero_phase = Early.zero_phase
erase_zero_flag = Early.erase_zero_flag
gauge_prefix = Early.gauge_prefix
gauge_return = Early.gauge_return
validate_head_profile = Early.validate_head_profile
SlotToken = Early.SlotToken


class RollingTail(Early.RollingTail):
    """Same physical quantum state machine; explicit retained classical debts."""

    def __init__(self, builder, first_index=15, stop_index=35):
        super().__init__(builder, first_index, stop_index)
        self.previous_masks = {}
        self.created_indices = []
        self.retired_indices = []
        self.max_pending_masks = 0

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
            assert index not in self.previous_masks
            measured = self.builder.alloc_bits(1)
            self.builder.hmr(km.array([previous]), measured)
            self.previous_masks[index] = measured
            self.created_indices.append(index)
            self.max_pending_masks = max(self.max_pending_masks,
                                         len(self.previous_masks))
            self.builder.free(km.array([previous]))
        self.current = current
        token = SlotToken(index, current, first)
        self.pending = token
        return token

    def release_spare(self):
        super().release_spare()
        assert sorted(self.previous_masks) == list(
            range(self.first_index + 1, self.stop_index))

    def finish_return(self, numerator, denominator, token):
        assert token == self.pending
        assert len(numerator) == len(denominator) == 24
        previous = None
        if not token.first_boundary:
            previous = self.builder.alloc_qubits(1)[0]
            zero_xor(self.builder, denominator, previous)
            # At this exact seam previous is zero(restored selected v), not
            # the original previous flag.  It is the HMR source from prefix.
            measured = self.previous_masks.pop(token.index)
            self.builder.cz(measured[0], previous)
            self.builder.free(measured)
            self.retired_indices.append(token.index)
            self.builder.cx(token.current, previous)
        else:
            assert token.index == self.first_index
            assert token.index not in self.previous_masks
        self.builder.cswap(token.current, numerator, denominator)
        erase_zero_flag(self.builder, numerator, token.current)
        self.builder.free(km.array([token.current]))
        self.current = previous
        self.pending = None
        self.return_next -= 1

    def close(self):
        super().close()
        expected = list(range(self.first_index + 1, self.stop_index))
        assert self.created_indices == expected
        assert self.retired_indices == expected[::-1]
        assert not self.previous_masks
        assert self.max_pending_masks == len(expected)


def source_ledger(j_min=15):
    result = Early.source_ledger(j_min)
    count = 35 - j_min
    debts = count - 1
    result['controller_prefix_T'] -= 22 * debts
    result['controller_pair_T'] -= 22 * debts
    result['controller_prefix_uniform_HMR_mean_T'] -= 11 * debts
    result['controller_uniform_HMR_mean_T'] -= 11 * debts
    result.update(
        status='SOURCE_MODEL_UNTIL_NATIVE_COMPONENT_PASSES',
        variant='previous-flag HMR masks paid at matching return zero queries',
        conditional_flag_phases=count,
        pending_classical_masks_max=debts,
        delta_static_T_vs_early=-22 * debts,
        delta_uniform_HMR_mean_T_vs_early=-11 * debts,
        new_quantum_qubits=0,
        new_zero_queries=0,
        admitted_domain_change=False,
        prefix_phase_scope='Open arithmetic and indexed tail measurement debts remain.',
        expected_saving_vs_default_T=11 * (2 * count - 1) + 5 + 11 * debts,
    )
    return result
