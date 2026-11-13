import numpy as np
import pytest

from dfthcsos_gen.bilinear import geometry
from dfthcsos_gen.shared import build_shared_loader, random_plan, shared_toffolis, table_of


def test_shared_loader_loads_a_table_of_its_form() -> None:
    km = pytest.importorskip("kickmix")
    rng = np.random.default_rng(5)
    a, brot, j, lb, terms = 100, 4, 3, 3, 9
    h, ll = geometry(a, lb)
    plan = random_plan(brot * j, h, ll, terms, rng)
    circ = build_shared_loader(plan, a, brot, lb)
    assert circ.operation_statistics().num_toffoli_like == shared_toffolis(plan, a, lb)
    tab = table_of(plan).reshape(brot * j, h * ll)[:, :a]  # (nout, A)

    n = (a - 1).bit_length()
    shots = 4
    sim = km.Simulator(batch_size=a * shots, debug_print=False, seed=1)
    sim.use_same_registers_as(circ)
    addr = np.tile(np.arange(a), shots)
    sim.write_across_shots(
        km.array([km.q(i) for i in range(n)]), ((addr[None, :] >> np.arange(n)[:, None]) & 1).astype(bool)
    )
    sim.do(circ)
    assert not sim.read_phase_flipped_across_shots().any()
    for o in range(brot * j):
        got = sim.read_across_shots(km.array([km.q(n + o)]))[0]
        assert (got == np.tile(tab[o], shots)).all()
    work = km.array([km.q(i) for i in range(n + brot * j, circ.num_qubits)])
    assert not sim.read_across_shots(work).any()


def test_terms_cost_one_toffoli_each() -> None:
    rng = np.random.default_rng(1)
    h, ll = geometry(100, 3)
    base = random_plan(12, h, ll, 0, rng)
    big = random_plan(12, h, ll, 20, rng)
    assert shared_toffolis(big, 100, 3) - shared_toffolis(base, 100, 3) == big.terms
