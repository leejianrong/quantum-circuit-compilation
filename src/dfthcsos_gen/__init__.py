"""Our own generators for the dfthcsos ``ANGLE_k`` loader circuits (ADR-0009)."""

from .bilinear import (
    best_lb,
    bilinear_toffolis,
    build_bilinear_family,
    build_bilinear_loader,
    centered_rank,
    plane_toffolis,
)
from .loader import (
    angle_deltas,
    build_family,
    build_unary_loader,
    family_stats,
    max_words_per_circuit,
    unary_toffolis,
    write_family,
)

__all__ = [
    "best_lb",
    "bilinear_toffolis",
    "build_bilinear_family",
    "build_bilinear_loader",
    "centered_rank",
    "plane_toffolis",
    "angle_deltas",
    "build_family",
    "build_unary_loader",
    "family_stats",
    "max_words_per_circuit",
    "unary_toffolis",
    "write_family",
]
