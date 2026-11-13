"""Dialog-free BM decoder: classical reference and the official verifier on a degree-12 instance."""

import os
import pathlib
import random

import kickmix as km  # type: ignore[import-not-found,unused-ignore]
import pytest

from dqi_gen import bmref, instances, jacobi


def test_reference_recovers_locator_and_quotient_formula() -> None:
    gf = km.GF2Field(12)
    rng = random.Random(4)
    for weight in (0, 1, 7, 20, 35):
        pos = rng.sample(range(4095), weight)
        vals = {x: rng.randint(1, 4095) for x in pos}
        res = bmref.solve(gf, jacobi.syndromes(gf, vals, 70), 35)
        assert res.ok  # c = 1 / (f[0] b) at every swap step, f[0] = 0 otherwise, stack depth at most one
        alpha = gf.primitive_element
        roots = [j for j in vals if jacobi.poly_eval(gf, res.g, gf.pow(alpha, (-j) % 4095)) == 0]
        assert len(roots) == weight


@pytest.mark.integration
@pytest.mark.skipif(
    not (pathlib.Path(os.environ.get("QCC_DATA", "data")) / "verifiers" / "dqi").exists(),
    reason="needs the competition data",
)
def test_bm_decoder_verifies_on_mid12() -> None:
    inst = instances.INSTANCES["mid12"]
    out = instances.verify(instances.build("bm", inst), inst, shots=4096)
    assert out["status"] == "PASS" and out["value_errors"] == 0 and out["phase_errors"] == 0
