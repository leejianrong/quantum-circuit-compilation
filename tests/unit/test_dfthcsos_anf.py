import numpy as np
import pytest

from dfthcsos_gen.anf import anf_toffolis, build_anf_loader, convert_set, mobius, work_qubits


def test_mobius_inverts_the_subset_sum() -> None:
    rng = np.random.default_rng(0)
    for n in (5, 16, 77):
        v = rng.integers(0, 2, n).astype(np.uint8)
        c = mobius(v)
        back = np.array([sum(int(c[s]) for s in range(n) if s & h == s) & 1 for h in range(n)])
        assert (back == v).all()


def test_convert_set_keeps_the_value_of_the_form() -> None:
    h, ll = 13, 8
    s = frozenset({1, 4, 9, h + 2, h + 5})
    m = convert_set(s, h, ll)
    for hv in range(h):
        for lv in range(ll):
            want = sum(1 for q in s if (q == hv if q < h else q - h == lv)) & 1
            got = 0
            for q in m:
                if q == 0:
                    got ^= 1
                elif q < h:
                    got ^= int(q & hv == q)
                else:
                    t = q - h + 1
                    got ^= int(t & lv == t)
            assert got == want


@pytest.mark.parametrize("a,brot,j,lb", [(100, 4, 3, 3), (150, 3, 2, 4), (77, 5, 2, 2)])
def test_anf_loader_loads_and_counts(a: int, brot: int, j: int, lb: int) -> None:
    km = pytest.importorskip("kickmix")
    rng = np.random.default_rng(a)
    delta = rng.integers(0, 1 << brot, size=(a, j)).astype(np.int64)
    circ = build_anf_loader(delta, brot, lb)
    assert circ.operation_statistics().num_toffoli_like == anf_toffolis(delta, brot, lb)
    n = (a - 1).bit_length()
    assert circ.num_qubits == n + j * brot + work_qubits(a, lb)
    shots = 4
    sim = km.Simulator(batch_size=a * shots, debug_print=False, seed=1)
    sim.use_same_registers_as(circ)
    addr = np.tile(np.arange(a), shots)
    sel = km.array([km.q(i) for i in range(n)])
    sim.write_across_shots(sel, ((addr[None, :] >> np.arange(n)[:, None]) & 1).astype(bool))
    sim.do(circ)
    assert not sim.read_phase_flipped_across_shots().any()
    for w in range(j):
        reg = km.array([km.q(n + w * brot + i) for i in range(brot)])
        got = (sim.read_across_shots(reg).astype(np.int64) * (1 << np.arange(brot))[:, None]).sum(axis=0)
        assert (got == np.tile(delta[:, w], shots)).all()
    assert (sim.read_across_shots(sel) == ((addr[None, :] >> np.arange(n)[:, None]) & 1)).all()
    work = km.array([km.q(i) for i in range(n + j * brot, circ.num_qubits)])
    assert not sim.read_across_shots(work).any()
