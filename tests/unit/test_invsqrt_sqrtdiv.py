"""The square-root-and-division model: identities and error level (subsampled for speed)."""

import numpy as np

from invsqrt_gen.sqrtdiv import MAX_X, fit_d, reachable_n, relative_error, root, worst_error_bits


def test_reachable_n_is_normalised() -> None:
    n = reachable_n()
    assert n.min() >= 2**20 and n.max() < 2**22
    assert len(n) == 2_350_089  # the verifier's reachable set, also used by invsqrt_gen.model
    assert MAX_X == 3_133_452


def test_root_identities() -> None:
    n = reachable_n()[::997]
    r, t = root(n)
    assert (4096 <= r).all() and (r < 8192).all()
    assert (t >= -r - 1).all() and (t < r).all()  # h = t >> 4 fits 10 signed bits
    # n is recovered from (R, h): the low four bits of t are a function of R
    lam = t & 15
    lam_of_r = np.zeros(16, dtype=np.int64)
    for res in range(16):
        sel = r % 16 == res
        if sel.any():
            assert len(set(lam[sel].tolist())) == 1
            lam_of_r[res] = lam[sel][0]
    assert ((16 * n - r * r - r - 1) == (t >> 4 << 4) + lam_of_r[r % 16]).all()


def test_first_order_model_error() -> None:
    n = reachable_n()[::499]
    table = fit_d(7, 38, 44)
    assert worst_error_bits(n, table) < -25.2
    assert np.abs(relative_error(n, table)).max() < 2.0**-24.8
