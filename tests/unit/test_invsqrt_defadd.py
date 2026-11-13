"""The deferred-phase adder pair against integers, with a clean global phase on every shot."""

import itertools

import kickmix as km
import numpy as np
import pytest

from invsqrt_gen.defadd import fd_add, md_add


def _pair(w: int, m: int, use_cin: bool, split: int | None, mid: str) -> km.Circuit:
    b = km.CircuitBuilder()
    a = b.create_quantum_register(w, name="a")
    t = b.create_quantum_register(m, name="t")
    cin = b.create_quantum_register(1, name="c")[0] if use_cin else None
    ms = fd_add(b, a, t, cin)
    if mid == "x":  # something in between that does not touch the registers
        pass
    md_add(b, a, t, ms, cin, split)
    return b.finish_circuit()


@pytest.mark.parametrize(
    "w,m,use_cin", [(4, 6, False), (5, 5, True), (3, 7, True), (6, 9, False), (8, 12, True)]
)
def test_forward_adds(w: int, m: int, use_cin: bool) -> None:
    b = km.CircuitBuilder()
    a = b.create_quantum_register(w, name="a")
    t = b.create_quantum_register(m, name="t")
    cin = b.create_quantum_register(1, name="c")[0] if use_cin else None
    fd_add(b, a, t, cin)
    c = b.finish_circuit()
    rng = np.random.default_rng(1)
    n = 256
    av, tv = rng.integers(0, 1 << w, n), rng.integers(0, 1 << m, n)
    cv = rng.integers(0, 2, n) if use_cin else np.zeros(n, dtype=np.int64)
    sim = km.Simulator(batch_size=n, seed=0)
    sim.use_same_registers_as(c)
    for i in range(n):
        sim.write_within_shot("a", i, int(av[i]))
        sim.write_within_shot("t", i, int(tv[i]))
        if use_cin:
            sim.write_within_shot("c", i, int(cv[i]))
    sim.do(c)
    assert [sim.read_within_shot("t", i, out=int) for i in range(n)] == ((tv + av + cv) % (1 << m)).tolist()
    assert c.operation_statistics().num_toffoli_like == m - 1


@pytest.mark.parametrize(
    "w,m,use_cin,split",
    list(itertools.product([4, 8], [6, 9, 12], [False, True], [None, 1, 3, 5])),
)
def test_pair_restores_and_pays_every_debt(w: int, m: int, use_cin: bool, split: int | None) -> None:
    if split is not None and split > m - 2:
        pytest.skip("split beyond the carry chain")
    c = _pair(w, m, use_cin, split, "")
    rng = np.random.default_rng(2)
    n = 512
    av, tv = rng.integers(0, 1 << w, n), rng.integers(0, 1 << m, n)
    cv = rng.integers(0, 2, n) if use_cin else np.zeros(n, dtype=np.int64)
    sim = km.Simulator(batch_size=n, seed=5)
    sim.use_same_registers_as(c)
    for i in range(n):
        sim.write_within_shot("a", i, int(av[i]))
        sim.write_within_shot("t", i, int(tv[i]))
        if use_cin:
            sim.write_within_shot("c", i, int(cv[i]))
    sim.do(c)
    assert [sim.read_within_shot("t", i, out=int) for i in range(n)] == tv.tolist()
    assert [sim.read_within_shot("a", i, out=int) for i in range(n)] == av.tolist()
    assert not sim.read_phase_flipped_across_shots().any()
