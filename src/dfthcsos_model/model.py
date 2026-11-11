"""Pure-Python reproduction of the dfthcsos score ``lambda_eff * T_total * Q_total``.

Inputs are the factorization shape ``(R, B, C)``, the angle-loader family (``J`` words of ``brot``
bits per circuit, its Toffolis and qubits) and the accuracy metrics ``(Lambda, E_gap)`` of the
loaded words. No simulator and no integrals are needed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .prepare import N_ORBITALS, PrepareCosts, clog2, prepare_costs

QUBIT_CAP = 128
LAMBDA_FLOOR = 49.0
E_GAP_FLOOR = 3.914898
ERR_LIMIT = 0.02


def lambda_eff(lam: float, e_gap: float) -> float:
    """Spectrum-amplified normalization ``sqrt(E_gap * (2 Lambda - E_gap))``."""
    return math.sqrt(e_gap * (2 * lam - e_gap))


def addresses(R: int, B: int, n: int = N_ORBITALS) -> int:
    return n + R * B


def n_loaders(J: int, n: int = N_ORBITALS) -> int:
    """K = ceil((N-1) / J) ANGLE_k circuits."""
    return math.ceil((n - 1) / J)


def plain_qrom_angles(R: int, B: int, J: int, n: int = N_ORBITALS) -> tuple[int, int]:
    """Reference ordinary QROM family: (Toffolis over both passes, scratch qubits per circuit).

    ``A - 2`` Toffolis per circuit and ``ceil(log2 A) - 1`` scratch qubits, for ``K`` circuits.
    """
    a = addresses(R, B, n)
    return 2 * n_loaders(J, n) * (a - 2), clog2(a) - 1


@dataclass(frozen=True)
class Angles:
    """What the verifier reads off the ANGLE_k family."""

    toffoli: float  # mean Toffoli-like gates per shot, forward + reverse (2 * sum of static counts)
    qubits: int  # max over k of num_qubits (workspace included)
    J: int  # word registers per circuit
    brot: int  # bits per word register


@dataclass(frozen=True)
class Breakdown:
    lambda_eff: float
    t_angles: float
    t_prep: int  # outer + inner state preparation
    t_givens: int
    t_total: float
    q_persistent_prep: int
    q_words: int
    q_temp: int
    q_total: int
    q_temp_source: str  # which stage sets the shared workspace: outer, inner or angles
    angles_temp: int
    prep: PrepareCosts
    score: float


def score(
    shape: tuple[int, int, int], angles: Angles, lam: float, e_gap: float, n: int = N_ORBITALS
) -> Breakdown:
    R, B, C = shape
    prep = prepare_costs(R, B, C, angles.brot, n)
    sel = clog2(addresses(R, B, n))
    q_words = angles.J * angles.brot
    angles_temp = angles.qubits - sel - q_words
    temps = {"outer": prep.outer_temp, "inner": prep.inner_temp, "angles": angles_temp}
    src = max(temps, key=lambda k: temps[k])
    q_temp = temps[src]
    q_total = prep.persistent + q_words + q_temp
    t_prep = prep.outer_toffoli + prep.inner_toffoli
    t_total = angles.toffoli + t_prep + prep.givens_toffoli
    le = lambda_eff(lam, e_gap)
    return Breakdown(
        lambda_eff=le,
        t_angles=angles.toffoli,
        t_prep=t_prep,
        t_givens=prep.givens_toffoli,
        t_total=t_total,
        q_persistent_prep=prep.persistent,
        q_words=q_words,
        q_temp=q_temp,
        q_total=q_total,
        q_temp_source=src,
        angles_temp=angles_temp,
        prep=prep,
        score=le * t_total * q_total,
    )


def passes_gates(error_1: float, error_2: float, lam: float, e_gap: float) -> bool:
    """The verifier's accuracy gates (strict on the Lambda and E_gap floors)."""
    return (
        error_1 <= ERR_LIMIT
        and error_2 <= ERR_LIMIT
        and 0 < e_gap < 2 * lam
        and lam > LAMBDA_FLOOR
        and e_gap > E_GAP_FLOOR
    )
