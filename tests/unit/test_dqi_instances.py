"""Small DQI instances verify with the official verifier, and a broken decoder is caught."""

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


def test_min_shots_is_a_batch_multiple_above_the_bound() -> None:
    n = instances.min_shots()
    assert n % instances.BATCH == 0 and 1375 < n <= 1536


@pytest.mark.parametrize("name", ["tiny", "small"])
def test_reference_passes_small_instances(name: str) -> None:
    inst = instances.INSTANCES[name]
    out = instances.verify(instances.build("reference", inst), inst)
    assert out["status"] == "PASS" and out["value_errors"] == 0 and out["phase_errors"] == 0


def test_a_decoder_that_does_nothing_fails() -> None:
    import kickmix as km  # type: ignore[import-not-found,unused-ignore]

    inst = instances.INSTANCES["tiny"]
    b = km.CircuitBuilder()
    for i in range(inst.n):
        b.create_quantum_register(inst.degree, name=f"S{i}")
    for j in range(inst.m):
        b.create_classical_register(inst.degree, name=f"E{j}")
    with pytest.raises(AssertionError):
        instances.verify(b.finish_circuit(), inst)


def test_shot_floor_is_enforced() -> None:
    inst = instances.INSTANCES["tiny"]
    with pytest.raises(ValueError):
        instances.verify(instances.build("reference", inst), inst, shots=256)
