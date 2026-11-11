"""State-preparation and Givens costs of the dfthcsos score, in pure Python.

Re-derived from the arithmetic the verifier documents (``SpinFreeData_V1`` in
``scoreinfra/costs_prepare.py``): same formulas, plain ``math``. Validated against the verifier's
reported numbers in ``tests/unit/test_dfthcsos_model.py``.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

KEEP_BITS = 10  # chi, fixed by the verifier
N_ORBITALS = 76


def clog2(x: float) -> int:
    """ceil(log2(x))."""
    return math.ceil(math.log2(x))


def _best_k(value: Callable[[float], float], k_real: float) -> tuple[int, int]:
    k_real = max(k_real, 0.0)
    cands = [math.floor(k_real), math.ceil(k_real)]
    k_opt = min(cands, key=lambda k: value(float(k)))  # ties pick the floor, like numpy argmin
    return int(k_opt), math.ceil(value(float(k_opt)))


def qrom_opt(length: int, width: int) -> tuple[int, int]:
    """Optimal block exponent k and Toffoli cost of a QROAM over ``length`` words of ``width`` bits."""
    return _best_k(lambda k: length / 2.0**k + width * (2.0**k - 1), 0.5 * math.log2(length / width))


def inv_qrom_opt(length: int) -> tuple[int, int]:
    """Optimal k and cost of the inverse (measurement-based) QROM over ``length`` values."""
    return _best_k(lambda k: length / 2.0**k + 2.0**k - 1, 0.5 * math.log2(length))


@dataclass(frozen=True)
class PrepareCosts:
    outer_toffoli: int
    inner_toffoli: int
    givens_toffoli: int
    outer_persistent: int
    outer_temp: int
    inner_persistent: int
    inner_temp: int
    inner_k: int  # QROAM block exponent chosen by the qubit-saving search

    @property
    def toffoli(self) -> int:
        return self.outer_toffoli + self.inner_toffoli + self.givens_toffoli

    @property
    def persistent(self) -> int:
        return self.outer_persistent + self.inner_persistent

    @property
    def temp(self) -> int:
        return max(self.outer_temp, self.inner_temp)


def inner_qroam_k(R: int, B: int, C: int, brot: int, n: int = N_ORBITALS, chi: int = KEEP_BITS) -> int:
    """Block exponent of the inner QROAM after the qubit-saving search.

    The search lowers k from the Toffoli-optimal value until the QROAM's temporary qubits fit under
    ``brot * (n - 1)``, the qubits the rotation registers already hold. k = 0 always fits, so the
    verifier's "no size fits" error is unreachable for brot >= 1.
    """
    b2 = clog2(B) + chi + 1
    rc = R * C
    k0 = qrom_opt(rc * B, b2)[0]
    for j in range(k0 + 1):
        k = k0 - j
        if clog2(rc * math.ceil(B / 2**k)) + (2**k - 1) * b2 < brot * (n - 1):
            return k
    raise AssertionError("unreachable: k = 0 always fits")


def prepare_costs(
    R: int, B: int, C: int, brot: int, n: int = N_ORBITALS, chi: int = KEEP_BITS
) -> PrepareCosts:
    rc = R * C
    # outer state preparation
    x_o = n + rc
    lg_xo = clog2(x_o)
    b1 = lg_xo + chi
    k1, qr_cost = qrom_opt(x_o, b1)
    outer = 2 * 4 * lg_xo + (qr_cost + b1) + (inv_qrom_opt(x_o)[1] + b1 + 1)
    outer_persistent = (b1 + chi) + (lg_xo + 2)
    outer_temp = clog2(x_o / 2**k1) + 2**k1 * b1 + max(0, lg_xo - 2)
    # inner state preparation
    b2 = clog2(B) + chi + 1
    k_search = inner_qroam_k(R, B, C, brot, n, chi)
    k2 = k_search
    while k2 > 0 and B < 2**k2:  # Toffoli count wants a block of at most B
        k2 -= 1
    for_qroam = rc * math.ceil((B + 1) / 2**k2) + 2**k2 * b2
    for_qroam_dag = qrom_opt(rc, B + 1)[1] + (B + 1) + n + b2
    inner = for_qroam + for_qroam_dag + 2 * 4 * clog2(B + 1)
    # the qubit count uses the searched k itself (not the decremented one), as the verifier does
    inner_persistent = (b2 + chi + clog2(R) + 2) + (clog2(B + 1) + 2)
    inner_temp = (
        max(0, clog2(B + 1) - 2) + clog2(rc * math.ceil((B + 1) / 2**k_search)) + (2**k_search - 1) * b2
    )
    return PrepareCosts(
        outer_toffoli=outer,
        inner_toffoli=inner,
        givens_toffoli=2 * (n - 1) * (2 * brot - 1),
        outer_persistent=outer_persistent,
        outer_temp=outer_temp,
        inner_persistent=inner_persistent,
        inner_temp=inner_temp,
        inner_k=k_search,
    )
