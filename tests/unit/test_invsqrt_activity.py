import numpy as np

from invsqrt_gen.port.activity import activity
from invsqrt_gen.port.ccx_rank import in_span, scan

TEXT = """APPEND_TO_REGISTER q0 r0
X q21
X q21
CCX q0 q1 q2
HMR q2 b0
PUSH_CONDITION if b1
CCX q0 q1 q3
POP_CONDITION
"""


def test_in_span() -> None:
    assert in_span(0b110, [0b100, 0b010])
    assert not in_span(0b001, [0b100, 0b010])


def test_activity_counts_branch_that_never_runs() -> None:
    xs = np.arange(1, 9, dtype=np.int64)
    got = activity(TEXT, xs)
    gate_lines = sorted(got)
    assert got[gate_lines[0]] == 8  # unconditioned
    assert got[gate_lines[1]] == 0  # b1 is never set


def test_scan_separates_affine_from_real_products() -> None:
    real = scan(TEXT, samples=64, seed=0)
    assert real and not real[0][2]  # q0 & q1 is a genuine product
    affine = scan(TEXT.replace("CCX q0 q1 q2", "CX q0 q5\nCCX q0 q0 q2", 1), samples=64, seed=0)
    assert affine[0][2]  # q0 & q0 = q0
