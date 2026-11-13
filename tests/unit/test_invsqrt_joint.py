"""`joint.refine` never makes a segment worse (8 segments; slow, so marked integration)."""

import numpy as np
import pytest

from invsqrt_gen.joint import refine, segment_errors
from invsqrt_gen.model import fit_tables
from invsqrt_gen.params import Params


@pytest.mark.integration  # minutes: the reachable-input tables are full size
def test_refine_is_monotone_per_segment() -> None:
    p = Params(a=2, frac=(28, 14, 6), guard=2, centered=True, pm1=True, rnd=True)
    t = fit_tables(p, passes=1, stride=61, reachable=True)
    before = segment_errors(p, t)
    t2 = refine(p, t, target=0.0, box=(3, 1), rounds=2, worst=8)
    after = segment_errors(p, t2)
    assert (after <= before + 1e-18).all()
    assert (after < before).any() or np.allclose(after, before)
