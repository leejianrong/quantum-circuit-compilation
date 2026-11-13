"""The own thiele decoder (vendored kernels) verifies on the narrow instance (n = 70, GF(2^12), 71 positions)."""

import os
import pathlib

import pytest

from dqi_gen import instances

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (pathlib.Path(os.environ.get("QCC_DATA", "data")) / "verifiers" / "dqi").exists(),
        reason="needs the competition data",
    ),
]


def test_thiele_decoder_verifies_on_narrow() -> None:
    inst = instances.INSTANCES["narrow"]
    out = instances.verify(instances.build("thiele", inst), inst, shots=2048)
    assert out["status"] == "PASS" and out["value_errors"] == 0 and out["phase_errors"] == 0
