"""The Lanczos decoder passes the official verifier on a small degree-12 instance and uses few qubits."""

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


def test_mid12_passes_and_beats_divstep_on_qubits() -> None:
    inst = instances.INSTANCES["mid12"]
    out = instances.verify(instances.build("lanczos", inst), inst, shots=3072)
    base = instances.verify(instances.build("divstep", inst), inst, shots=3072)
    assert out["status"] == "PASS"
    assert out["value_errors"] + out["phase_errors"] < 40  # degenerate steps fail about 1 in 2^12 each
    assert out["num_qubits"] < base["num_qubits"]
