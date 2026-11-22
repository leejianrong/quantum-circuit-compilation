import numpy as np

from invsqrt_gen.port import width

TEXT = """\
APPEND_TO_REGISTER q0 r0
REGISTER r0 "x"
CX q0 q22
CCX q0 q22 q23
HMR q23 b0
CX q22 q0
CX q22 q0
"""


def test_width_counts_inputs_plus_nonzero_ancillas() -> None:
    p = width.profile(TEXT, samples=64, seed=1)
    # 22 input qubits are always live; q22 joins after the CX, q23 only between the CCX and the HMR
    assert [int(v) for v in p.width[2:5]] == [23, 24, 23]


def test_segments() -> None:
    assert width.segments(np.array([1, 3, 3, 2, 3]), 3) == [(1, 2), (4, 4)]
