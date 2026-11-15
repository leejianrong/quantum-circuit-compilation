"""The widget maths (docs/javascripts/widgets-core.mjs) must equal its Python twins.

Python computes golden values from the real cost model and from numpy; Node evaluates the same inputs in the
widget core (tests/js/parity.mjs). Skipped when `node` is not installed.
"""

import itertools
import json
import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from dfthcsos_model import lambda_eff, passes_gates

ROOT = Path(__file__).resolve().parents[2]
BASELINE = 3_355_599_588.3155365
R_EPS = 1.2

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def mbuc_reference(a: int, b: int, m: int, repair: bool) -> tuple[int, int]:
    """Bit-plus-sign simulation of the page: Toffoli, HMR with outcome m, optional CZ(a, b) if m."""
    anc, sign = a & b, 1  # after the Toffoli
    sign *= -1 if (m and anc) else 1  # H then measuring m on |anc>: amplitude (-1)^(m*anc)
    after_hmr = sign
    anc = 0  # the ancilla is reset
    if repair and m:
        sign *= -1 if (a and b) else 1  # CZ
    assert anc == 0
    return after_hmr, sign


def golden() -> dict:  # type: ignore[type-arg]
    rng = np.random.default_rng(7)
    lam_eff_in = [
        [float(x), float(y)] for x, y in zip(rng.uniform(50, 600, 12), rng.uniform(3.8, 4.6, 12), strict=True)
    ]
    gate_in = [
        {"lam": lam, "eGap": e, "err1": float(e1), "err2": float(e2)}
        for (lam, e), e1, e2 in zip(
            lam_eff_in, rng.uniform(0.015, 0.025, 12), rng.uniform(0.015, 0.025, 12), strict=True
        )
    ]
    gate_in += [
        {
            "lam": 282.974,
            "eGap": 3.9148982,
            "err1": 0.019610,
            "err2": 0.0199988,
        },  # a verified circuit: passes
        {"lam": 282.974, "eGap": 3.914898, "err1": 0.01, "err2": 0.01},  # E_gap exactly at the floor: fails
        {"lam": 49.0, "eGap": 4.0, "err1": 0.01, "err2": 0.01},  # Lambda exactly at the floor: fails
        {"lam": 50.0, "eGap": 100.0, "err1": 0.01, "err2": 0.01},  # E_gap outside (0, 2 Lambda): fails
    ]
    return {
        "baseline": BASELINE,
        "rEps": R_EPS,
        "lambdaEff": lam_eff_in,
        "gates": gate_in,
        "score": [
            {**p, "t": float(t), "q": float(q)}
            for p, t, q in zip(
                gate_in[:12], rng.uniform(5e3, 1e5, 12), rng.uniform(100, 900, 12), strict=True
            )
        ],
        "interference": [float(t) for t in np.linspace(0, 2 * math.pi, 25)],
        "benchCost": [["invsqrt", 93.0, 1809.0], ["dqi", 890.0, 391326.0], ["dqi", 1855.0, 740602.0]],
        "equivalent": [["invsqrt", 0.1], ["dqi", 0.1], ["dqi", -0.05], ["invsqrt", 0.0]],
        "mbuc": [[a, b, m, r] for a, b, m in itertools.product((0, 1), repeat=3) for r in (True, False)],
    }


def run_node(tmp_path: Path, g: dict) -> dict:  # type: ignore[type-arg]
    path = tmp_path / "golden.json"
    path.write_text(json.dumps(g))
    out = subprocess.run(
        ["node", str(ROOT / "tests" / "js" / "parity.mjs"), str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)  # type: ignore[no-any-return]


def test_widget_core_matches_python(tmp_path: Path) -> None:
    g = golden()
    js = run_node(tmp_path, g)
    for (lam, e), got in zip(g["lambdaEff"], js["lambdaEff"], strict=True):
        assert got == pytest.approx(lambda_eff(lam, e), rel=1e-12)
    for p, got in zip(g["gates"], js["gates"], strict=True):
        assert got == passes_gates(p["err1"], p["err2"], p["lam"], p["eGap"])
    assert any(js["gates"]) and not all(js["gates"])  # the golden set exercises both outcomes
    for p, got in zip(g["score"], js["score"], strict=True):
        assert got == pytest.approx(lambda_eff(p["lam"], p["eGap"]) * p["t"] * p["q"], rel=1e-12)
    h = np.array([[1, 1], [1, -1]]) / math.sqrt(2)
    for theta, (a0, a1, p0, p1) in zip(g["interference"], js["interference"], strict=True):
        v = h @ np.diag([1, np.exp(1j * theta)]) @ h @ np.array([1, 0])
        assert complex(*a0) == pytest.approx(v[0], abs=1e-12)
        assert complex(*a1) == pytest.approx(v[1], abs=1e-12)
        assert (p0, p1) == pytest.approx((abs(v[0]) ** 2, abs(v[1]) ** 2), abs=1e-12)
    for (bench, q, y), got in zip(g["benchCost"], js["benchCost"], strict=True):
        want = q * y if bench == "invsqrt" else R_EPS * q * q * y
        assert got == pytest.approx(want, rel=1e-12)
    for (bench, dq), got in zip(g["equivalent"], js["equivalent"], strict=True):
        q, y = 100.0, 1000.0
        cost = q * y if bench == "invsqrt" else R_EPS * q * q * y
        q2 = q * (1 + dq)
        y2 = cost / q2 if bench == "invsqrt" else cost / (R_EPS * q2 * q2)
        assert got == pytest.approx(y2 / y - 1, rel=1e-9, abs=1e-12)
    for (a, b, m, r), got in zip(g["mbuc"], js["mbuc"], strict=True):
        assert tuple(got) == mbuc_reference(a, b, m, r)


def test_mbuc_repair_always_restores_the_sign() -> None:
    assert all(mbuc_reference(a, b, m, True)[1] == 1 for a, b, m in itertools.product((0, 1), repeat=3))
    assert mbuc_reference(1, 1, 1, False)[1] == -1  # without the repair the sign is wrong
