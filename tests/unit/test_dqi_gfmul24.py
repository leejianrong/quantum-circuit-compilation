"""The rank-99 GF(2^24) multiplier is exact, and its circuit costs 99 Toffolis and clears its ancillas."""

import random

import kickmix as km  # type: ignore[import-not-found,unused-ignore]
import numpy as np

from dqi_gen import gfmul24


def test_rank_99_and_exact() -> None:
    forms, _ = gfmul24.bilinear24()
    assert len(forms) == 99
    for i in range(24):
        for j in range(24):
            assert gfmul24.classical_mul24(1 << i, 1 << j) == gfmul24.mul24(1 << i, 1 << j)
    rng = random.Random(1)
    for _ in range(3000):
        a, b = rng.randrange(1 << 24), rng.randrange(1 << 24)
        assert gfmul24.classical_mul24(a, b) == gfmul24.mul24(a, b)


def test_circuit_multiplies_with_99_toffolis() -> None:
    b = km.CircuitBuilder()
    x = b.create_quantum_register(24, name="X")
    y = b.create_quantum_register(24, name="Y")
    z = b.create_quantum_register(24, name="Z")
    gfmul24.FastMul24(b).ixor_mul(x, y, z)
    circ = b.finish_circuit()
    assert circ.operation_statistics().num_toffoli_like == 99
    shots = 64
    sim = km.Simulator(batch_size=shots)
    rng = np.random.default_rng(3)
    xs, ys, zs = (rng.integers(0, 1 << 24, shots) for _ in range(3))

    def write(reg: km.array, vals: np.ndarray) -> None:
        bits = [[(int(v) >> i) & 1 for v in vals] for i in range(24)]
        sim.write_across_shots(reg, np.array(bits, dtype=bool))

    write(x, xs)
    write(y, ys)
    write(z, zs)
    sim.do(circ)
    out = sim.read_across_shots(z)
    for s in range(shots):
        got = sum(int(out[i][s]) << i for i in range(24))
        assert got == int(zs[s]) ^ gfmul24.mul24(int(xs[s]), int(ys[s]))
    assert not sim.read_phase_flipped_across_shots().any()
