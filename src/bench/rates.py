"""Marginal exchange rates of the three scores (spike S2).

All three scores are products of powers of the resources, so the relative score change of a small
move is a sum of logarithmic derivatives. Everything here is exact algebra on the verifier formulas
(docs/learn/costs-and-mbuc.md); the inputs are measured circuits.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    """A circuit's resources. `toffoli` is C for invsqrt, mean Toffolis for dqi, T_total for dfthcsos."""

    bench: str
    qubits: float
    toffoli: float

    @property
    def qubit_power(self) -> float:
        """Exponent of Q in the score."""
        return 2.0 if self.bench == "dqi" else 1.0

    def qubit_in_toffolis(self) -> float:
        """Toffolis (or Toffoli-equivalents) worth the same score as one qubit."""
        return self.qubit_power * self.toffoli / self.qubits

    def percent_per_qubit(self) -> float:
        return 100.0 * self.qubit_power / self.qubits

    def percent_per_toffoli(self) -> float:
        return 100.0 / self.toffoli


def rotation_cost(log2_inv_eps: float) -> float:
    """Toffoli-equivalents of one non-Clifford rotation (verifier: (0.56 log2(1/eps) + 5.3) / 4)."""
    return (0.56 * log2_inv_eps + 5.3) / 4.0


def rotation_precision_bits(cost_each: float) -> float:
    """Inverse of `rotation_cost`: the log2(1/eps) a rotation of that cost was synthesised at."""
    return (4.0 * cost_each - 5.3) / 0.56


def lambda_eff(lam: float, e_gap: float) -> float:
    return math.sqrt(e_gap * (2.0 * lam - e_gap))


def percent_per_lambda(lam: float, e_gap: float) -> float:
    """dfthcsos: percent of score per unit of Lambda (d ln lambda_eff / d Lambda = 1 / (2 Lambda - E_gap))."""
    return 100.0 / (2.0 * lam - e_gap)
