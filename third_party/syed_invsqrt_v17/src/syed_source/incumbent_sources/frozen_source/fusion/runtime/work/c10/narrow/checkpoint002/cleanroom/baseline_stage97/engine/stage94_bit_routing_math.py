# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""Exact binary butterfly for zero-supported normalization payloads.

After removing the leading one, a twenty-two-bit positive word has a
twenty-one-bit payload.  If ell is its original leading-zero count, every
live payload symbol at position i satisfies i+ell <= 20.  A low-bit-first
binary butterfly adds ell to each physical position label.

At stage j the lower position bits have already been added.  Their carry
is therefore [position mod 2**j < ell mod 2**j].  XORing this carry with
bit j of ell gives the exact selector for the pair differing in bit j.
Virtual pairs outside the payload contain zero throughout every valid
case, so they need no physical wires or gates.  All controls are freshly
derived functions of ell, available as parities of its prefix thresholds.
"""
from __future__ import annotations

from functools import lru_cache


def selector_value(leading_zeros, position, stage):
    """Return the bit-j addition selector at a current butterfly position."""
    modulus = 1 << stage
    return ((leading_zeros >> stage) & 1) ^ int(
        (position % modulus) < (leading_zeros % modulus))


def prefix_expression(truth, maximum):
    """Express a finite function in P_j=[ell>=j], including P_0=1."""
    if not isinstance(truth, int) or truth < 0 or truth >> (maximum+1):
        raise ValueError('A leading-zero truth mask has the wrong finite domain.')
    terms = tuple(index for index in range(maximum+1)
                  if ((truth >> index) & 1) ^ ((truth >> (index-1)) & 1 if index else 0))
    for leading_zeros in range(maximum+1):
        actual = sum(leading_zeros >= term for term in terms) & 1
        if actual != ((truth >> leading_zeros) & 1):
            raise AssertionError('A prefix expansion failed its exact finite-domain identity.')
    return terms


def operations(payload_width=21):
    """Generate every physical pair and its exact mathematical selector."""
    if not isinstance(payload_width, int) or payload_width < 2:
        raise ValueError('The zero-supported payload width must be at least two.')
    result = []
    for stage in range(payload_width.bit_length()):
        distance = 1 << stage
        for first in range(payload_width):
            second = first+distance
            if first & distance or second >= payload_width:
                continue
            truth = sum(selector_value(leading_zeros, first, stage) << leading_zeros
                        for leading_zeros in range(payload_width+1))
            result.append(dict(stage=stage, first=first, second=second,
                               selector_truth=truth,
                               prefix_terms=prefix_expression(truth, payload_width)))
    return tuple(result)


@lru_cache(maxsize=8)
def certificate(payload_width=21):
    """Certify all payload symbols, all controls, and both route directions."""
    route = operations(payload_width)
    virtual_width = 1 << payload_width.bit_length()
    contexts = payload_width+1
    virtual_nonzero_uses = 0
    virtual_pairs_checked = 0
    counts = [0]*payload_width.bit_length()
    for operation in route:
        counts[operation['stage']] += 1
    # Verify the complete position permutation independently of payload
    # simulation.  The current position supplies the already-added low bits.
    for leading_zeros in range(contexts):
        for initial_position in range(virtual_width):
            position = initial_position
            for stage in range(payload_width.bit_length()):
                position ^= selector_value(leading_zeros, position, stage) << stage
            if position != (initial_position+leading_zeros) % virtual_width:
                raise AssertionError('The full butterfly does not add its mathematical displacement.')
        live = payload_width-leading_zeros
        initial = list(range(1, live+1))+[0]*(virtual_width-live)
        expected = [0]*leading_zeros+list(range(1, live+1))+[0]*(virtual_width-payload_width)
        state = list(initial)
        for stage in range(payload_width.bit_length()):
            distance = 1 << stage
            for first in range(virtual_width):
                if first & distance:
                    continue
                second = first+distance
                if not selector_value(leading_zeros, first, stage):
                    continue
                if second >= payload_width:
                    virtual_pairs_checked += 1
                    virtual_nonzero_uses += int(bool(state[first] or state[second]))
                state[first], state[second] = state[second], state[first]
        if state != expected:
            raise AssertionError('The padded butterfly did not align its independent payload symbols.')
        physical = list(initial[:payload_width])
        for operation in route:
            if operation['selector_truth'] >> leading_zeros & 1:
                first, second = operation['first'], operation['second']
                physical[first], physical[second] = physical[second], physical[first]
        if physical != expected[:payload_width]:
            raise AssertionError('Omitting virtual pairs changed a valid physical payload.')
        for operation in reversed(route):
            if operation['selector_truth'] >> leading_zeros & 1:
                first, second = operation['first'], operation['second']
                physical[first], physical[second] = physical[second], physical[first]
        if physical != initial[:payload_width]:
            raise AssertionError('The reversed physical butterfly did not restore its payload.')
    if virtual_nonzero_uses:
        raise AssertionError('A discarded virtual pair contains live payload information.')
    if payload_width == 21 and (counts != [10, 10, 9, 8, 5] or len(route) != 42):
        raise AssertionError('The selected twenty-one-bit route changed its exact 42-swap budget.')
    return dict(status='EXACT_ZERO_SUPPORTED_BINARY_BUTTERFLY',
                payload_width=payload_width, leading_zero_contexts=contexts,
                virtual_width=virtual_width,
                controlled_swaps=len(route), swaps_per_stage=counts,
                virtual_pairs_checked=virtual_pairs_checked,
                virtual_nonzero_uses=virtual_nonzero_uses,
                full_position_addition_proved=True,
                independent_payload_symbols_proved=True,
                forward_and_inverse_proved=True,
                selectors_from_prefix_thresholds=True,
                source_search_or_saved_plan_inputs=False)


def leading_indicator_terms(position, input_width=22):
    """Return the prefix parity selecting a word's original leading one.

P_0 is the constant one, and P_input_width is zero for a positive input.
The caller treats the returned zero index as an unconditional X.
"""
    if not 0 <= position < input_width:
        raise ValueError('A leading-one position must belong to its input word.')
    first = input_width-1-position
    return tuple(index for index in (first, first+1) if index < input_width)
