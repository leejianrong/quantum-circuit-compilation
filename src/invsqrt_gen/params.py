"""Generator parameters."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

WIDTH = 22  # x register: 2 n_p + 2 with n_p = 10
FRAC = WIDTH - 1  # fractional bits of the normalised mantissa M = x_norm / 2^FRAC, M in [1, 2)
MAX_PAIRS = 10  # x >= 1 has at most 21 leading zeros, so s = z // 2 <= 10


@dataclass(frozen=True)
class Params:
    """Piecewise polynomial `y = c0 - r (c1 - r (c2 - ...))` of `1 / sqrt(M)`.

    `a`      segment bits below the leading one of `x_norm`; the table has 2 * 2^a entries (the parity of
             the leading zero count picks the half, so M in [2, 4) gets segments twice as wide).
    `frac`   fractional bits of the Horner registers V_0..V_d; `len(frac) - 1` is the degree.
             V_0 is the result `y`; its lowest `guard` bits are not phased.
    `guard`  low bits of V_0 below the phased word (they absorb truncation noise).
    """

    a: int = 7
    frac: tuple[int, ...] = (30, 21, 14)
    guard: int = 4
    ceil: bool = False
    centered: bool = False
    pm1: bool = False  # remainder as signed digits +-1 (centered generator): every row is one plain add
    rnd: bool = (
        False  # pm1 rows round their slice (the bit below it is the adder's carry-in) instead of flooring
    )

    @property
    def degree(self) -> int:
        return len(self.frac) - 1

    @property
    def wy(self) -> int:
        """Phased bits of the result."""
        return self.frac[0] - self.guard

    @property
    def rwidth(self) -> int:
        """Bits of the remainder r = x_norm mod 2^(FRAC - a)."""
        return FRAC - self.a

    @property
    def entries(self) -> range:
        return range(2 << self.a)

    def phased(self, v: NDArray[np.int64]) -> NDArray[np.int64]:
        """`V_0` reduced to the phased word: `V_0 >> guard` (or its ceiling when `ceil`)."""
        return (v + ((1 << self.guard) - 1) >> self.guard) if self.ceil else (v >> self.guard)
