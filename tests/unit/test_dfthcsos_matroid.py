import numpy as np
import pytest

from dfthcsos_gen import matroid as mt


def test_paired_plan_loads_exactly_on_reachable_words() -> None:
    km = pytest.importorskip("kickmix")
    rng = np.random.default_rng(0)
    a, brot, j = 70, 3, 2
    low = rng.integers(0, 1 << (brot - 1), size=(a, j))
    delta = low | ((low >> (brot - 2)) << (brot - 1))  # bit brot-1 == bit brot-2 (initial words are zero)
    planes, h = mt.planes_for(delta, brot, 4, True)
    no = planes.shape[0]
    parts = mt.make_parts(0)
    cuts: list[list[int]] = [[] for _ in parts]
    prods = mt.plan_products(planes, h, parts, cuts)
    assert prods is not None
    assert len(prods) <= (15 * no + 1) // 2  # no cuts: half of the 15 x NO unit columns
    circ = mt.build_pair_loader(delta, brot, 4, prods)
    n = (a - 1).bit_length()
    sim = km.Simulator(batch_size=a, debug_print=False, seed=1)
    sim.use_same_registers_as(circ)
    addr = np.arange(a)
    sim.write_across_shots(
        km.array([km.q(i) for i in range(n)]), ((addr[None, :] >> np.arange(n)[:, None]) & 1).astype(bool)
    )
    sim.do(circ)
    assert not sim.read_phase_flipped_across_shots().any()
    for w in range(j):
        reg = km.array([km.q(n + w * brot + i) for i in range(brot)])
        got = (sim.read_across_shots(reg).astype(np.int64) * (1 << np.arange(brot))[:, None]).sum(axis=0)
        assert (got == delta[:, w]).all()
    assert not sim.read_across_shots(km.array([km.q(i) for i in range(n + j * brot, circ.num_qubits)])).any()
