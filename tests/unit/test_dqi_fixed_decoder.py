"""The fixed decoders (extractor v2 and v3) verify on the narrow instance (n = 70)."""

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


@pytest.mark.parametrize("gen", ["fixed", "fixed3", "fixed3s", "fixed4"])
def test_fixed_decoder_verifies_on_narrow(gen: str) -> None:
    inst = instances.INSTANCES["narrow"]
    out = instances.verify(instances.build(gen, inst), inst, shots=2048)
    assert out["status"] == "PASS" and out["value_errors"] == 0 and out["phase_errors"] == 0
