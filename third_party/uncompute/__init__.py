"""uncompute - Python library for the reversible circuits of the uncompute tasks.

Vendored from the Apache-2.0 repository andigu/uncompute at commit 64b5a13aa249f1360846657392e6c66817b26d0f
(Gu, Kemeny, Yelin, Lukin; see LICENSE and NOTICE.md in this directory).

Change from upstream: the Simulator import was removed (the simulator and evaluator are not vendored; circuits
are checked with the official kickmix verifier instead).
"""

from .builder import Builder
from .ops import NO_OUT, NO_QUBIT, NO_REG, OpKind

__all__ = ["NO_OUT", "NO_QUBIT", "NO_REG", "Builder", "OpKind"]
