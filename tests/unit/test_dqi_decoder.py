"""Our divstep decoder passes the official verifier on small fields (QCC-19)."""

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


@pytest.mark.parametrize("name", ["tiny", "small", "medium"])
def test_divstep_decoder_verifies(name: str) -> None:
    inst = instances.INSTANCES[name]
    out = instances.verify(instances.build("divstep", inst), inst)
    assert out["status"] == "PASS" and out["value_errors"] == 0 and out["phase_errors"] == 0


def test_divstep_circuit_registers_are_restored_for_weight_zero_and_max() -> None:
    """The verifier's weight distribution includes 0 and l; a larger run exercises both."""
    inst = instances.INSTANCES["small"]
    out = instances.verify(instances.build("divstep", inst), inst, shots=4096, salt="weights")
    assert out["value_errors"] == 0 and out["phase_errors"] == 0
