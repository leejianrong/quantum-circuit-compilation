# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Optional fresh-mask skipping for the separately checked rolling controller.

The checked default in rolling_tail.py is unchanged.  This module changes only
the phase repayments of erased flag qubits: their complete AND ladders execute
only when the fresh classical HMR mask is one.  All predicates and controlled
swaps still execute unconditionally, and the native worst-case/static T count
and quantum peak are unchanged.

For twenty possible tail positions, there are 19 prefix and 20 return flag
erasures.  Their 22-T phase chains save exactly 39*11=429 expected T.  The gauge
chart's 10-T repayment saves another 5 expected T.  These expectations use the
fresh HMR-mask law, not a distribution of decoder inputs or terminal positions.
No saving is claimed until this variant's own native panels pass.
"""

import kickmix as km
import rolling_tail as Base

zero_xor = Base.zero_xor
validate_head_profile = Base.validate_head_profile
gauge_prefix = Base.gauge_prefix


def zero_phase(builder, source, classical_mask):
    assert len(source) >= 2
    builder.push_condition(classical_mask)
    builder.x(source)
    work = builder.alloc_qubits(len(source) - 2) if len(source) > 2 else None
    if work is not None:
        builder.init_and(source[0], source[1], work[0])
        for k in range(1, len(work)):
            builder.init_and(work[k - 1], source[k + 1], work[k])
        builder.cz(work[-1], source[-1])
        for k in reversed(range(1, len(work))):
            builder.del_and(work[k - 1], source[k + 1], work[k])
        builder.del_and(source[0], source[1], work[0])
        builder.free(work)
    else:
        builder.cz(source[0], source[1])
    builder.x(source)
    builder.pop_condition()


def erase_zero_flag(builder, source, flag):
    measured = builder.alloc_bits(1)
    builder.hmr(km.array([flag]), measured)
    zero_phase(builder, source, measured[0])
    builder.free(measured)


class RollingTail(Base.RollingTail):
    """Same public API and state transitions; only HMR phase chains can skip."""

    def finish_slot(self, head, token):
        assert token == self.pending and len(head) == 24
        if not token.first_boundary:
            self.builder.cx(token.current, token.previous)
            erase_zero_flag(self.builder, head, token.previous)
        self.current, self.spare = token.current, token.previous
        self.pending = None
        self.forward_next += 1

    def finish_return(self, numerator, denominator, token):
        assert token == self.pending
        assert len(numerator) == len(denominator) == 24
        self.builder.cswap(token.current, numerator, denominator)
        erase_zero_flag(self.builder, numerator, token.current)
        self.current, self.spare = token.previous, token.current
        self.pending = None
        self.return_next -= 1


def gauge_return(builder, carry, record):
    builder.cswap(record.flag, carry[:12], carry[12:])
    erase_zero_flag(builder, carry[:12], record.flag)
    builder.free(km.array([record.flag]))


def source_ledger(j_min=15):
    result = Base.source_ledger(j_min)
    count = 35 - j_min
    phases = 2 * count - 1
    result.update(
        status="OPTIONAL_SOURCE_MODEL_UNTIL_NATIVE_CHECK_PASSES",
        variant="classically skipped fresh-HMR phase ladders",
        conditional_flag_phases=phases,
        controller_uniform_HMR_mean_T=result["controller_pair_T"] - 11 * phases,
        controller_prefix_uniform_HMR_mean_T=result["controller_prefix_T"] - 11 * (count - 1),
        controller_return_uniform_HMR_mean_T=result["controller_return_T"] - 11 * count,
        gauge_uniform_HMR_mean_T=40,
        expected_saving_vs_default_T=11 * phases + 5,
        expectation_scope="Exact fresh-mask expectation; no terminal or input-distribution discount.")
    return result
