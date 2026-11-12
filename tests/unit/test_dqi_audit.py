"""The DQI stage audit counts Toffolis per `mark` block and agrees with kickmix's own total."""

import os
import pathlib

import pytest

from dqi_gen import audit

LINES = [
    "CCX q0 q1 q2",
    'INFO_TAG "@enter:stage_a"',
    "CCX q0 q1 q2",
    'INFO_TAG "@enter:inner"',
    "CSWAP q0 q1 q2",
    "CX q0 q1",
    'INFO_TAG "@exit:inner"',
    'INFO_TAG "@exit:stage_a"',
    'INFO_TAG "@enter:stage_b"',
    "CCZ q0 q1 q2 if b0",
    'INFO_TAG "@exit:stage_b"',
]


def test_tally_nested_marks() -> None:
    excl, total = audit.tally(LINES)
    assert total == 4
    assert excl == {(): 1, ("stage_a",): 1, ("stage_a", "inner"): 1, ("stage_b",): 1}
    out = audit.breakdown(excl, total)
    assert out["stages"]["stage_a"]["toffolis"] == 2  # its own plus the nested block
    assert out["marks"]["inner"]["toffolis"] == 1


def test_unbalanced_marks_raise() -> None:
    with pytest.raises(ValueError):
        audit.tally(['INFO_TAG "@enter:a"', 'INFO_TAG "@exit:b"'])


@pytest.mark.integration
@pytest.mark.skipif(
    not (pathlib.Path(os.environ.get("QCC_DATA", "data")) / "verifiers" / "dqi").exists(),
    reason="needs the competition data",
)
def test_small_reference_audit_matches_statistics() -> None:
    result = audit.audit_reference(63, 10, 6)
    assert result["total"] == 93623
    assert set(result["stages"]) == {
        "initial_shift",
        "forward_eea",
        "chien_forney_mbuc",
        "reverse_eea",
        "uncompute_initial_shift",
    }
