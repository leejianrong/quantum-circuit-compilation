"""Predict the verifier's cost of a generated circuit before running it.

Cost is `Q * C` with `C = Toffolis + T / 4` (see docs/experiments/invsqrt-cost-drivers.md). The only Toffolis
under a measurement condition are the flag clears of the un-normalisation (half of them run, see
`build.conditional_toffolis`); every other static Toffoli is executed. The rotation
cost depends on the margin the arithmetic error leaves: `eps = pi * margin / n_rot` and each rotation costs
`0.56 log2(1/eps) + 5.3` T, where `margin` is the smallest `tol(x) - |error(x)|` in turns, here
`min f(x) (2^-24 - rel(x))` over every `x` with `f = 2^(s-10) Y`.
"""

import math

import kickmix as km  # type: ignore[import-not-found,unused-ignore]
import numpy as np

from invsqrt_gen.build import conditional_toffolis
from invsqrt_gen.model import MAX_X, Tables, normalised_inputs, reachable_mask, rel_error
from invsqrt_gen.params import FRAC, Params


def predict(p: Params, t: Tables, circuit: km.Circuit) -> dict[str, float]:
    """Predicted `cost`, `qubits`, `toffolis`, rotations and model error for the circuit of `(p, t)`."""
    err, per = rel_error(p, t)
    xn, par = normalised_inputs()
    y = 1.0 / np.sqrt(xn / 2.0**FRAC * 2.0 ** (1 - par))
    reach = reachable_mask()
    margin = math.inf
    for s in range(11):  # x = xn >> (par + 2 s) when that is exact: phase 2^(s-10) Y, tolerance 2^-24 of it
        z = par + 2 * s
        x = xn >> z
        valid = (
            ((xn & (np.left_shift(1, z) - 1)) == 0) & (x >= 1) & (x <= MAX_X)
        )  # the verifier runs x <= MAX_X
        if valid.any():
            margin = min(margin, float((2.0 ** (s - 10) * y[valid] * (2.0**-24 - per[valid])).min()))
    stats = circuit.operation_statistics()
    n_rot = int(stats.num_z_pow(min_clifford_hierarchy_level=4))
    t_base = int(stats.num_t_like)
    eps = math.pi * margin / n_rot
    t_count = t_base + n_rot * (0.56 * math.log2(1 / eps) + 5.3) if margin > 0 else math.inf
    executed = int(stats.num_toffoli_like) - conditional_toffolis() / 2
    toff = executed + t_count / 4
    return {
        "cost": circuit.num_qubits * toff,
        "qubits": circuit.num_qubits,
        "toffolis": executed,
        "rotations": n_rot,
        "model_error_log2": math.log2(err),
        "reachable_error_log2": math.log2(float(per[reach].max())),
        "margin_log2": math.log2(margin) if margin > 0 else -math.inf,
    }
