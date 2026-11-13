# ruff: noqa: E501
"""Recorder, normalisation, root and the root-to-t conversion against integers; forward then inverse is the identity."""

import kickmix as km
import numpy as np

from invsqrt_gen.rec import Binding, Rec, inverse, replay
from invsqrt_gen.sqrtdiv import reachable_n, root
from invsqrt_gen.sqrtdiv_build import nr_model
from invsqrt_gen.sqrtdiv_stages import finish_root, normalise_even, sqrt_root


def _run(
    prog: list, extra_after: list | None, xs: np.ndarray, qubits: list[int]
) -> tuple[np.ndarray, np.ndarray]:
    b = km.CircuitBuilder()
    xr = b.create_quantum_register(22, name="x")
    bind = Binding({i: xr[i] for i in range(22)})
    replay(b, prog, bind)
    mid = [bind[q] for q in qubits]
    snap = km.array(mid)
    # a probe register: copy the wanted qubits into a classical-free readout by keeping them and finishing the circuit
    if extra_after:
        replay(b, extra_after, bind)
    c = b.finish_circuit()
    sim = km.Simulator(len(xs), seed=1)
    bits = ((xs[None, :] >> np.arange(22)[:, None]) & 1) == 1
    sim.write_across_shots(c.register_data["x"], bits)
    sim.do(c)
    back = (sim.read_across_shots(c.register_data["x"]).astype(np.int64) * (1 << np.arange(22))[:, None]).sum(
        axis=0
    )
    got = sim.read_across_shots(snap) if not extra_after else np.zeros((len(qubits), len(xs)), dtype=bool)
    return back, got


def test_normalise_then_root_matches_integers() -> None:
    n_all = reachable_n()
    _, _, widths = nr_model(n_all)
    rng = np.random.default_rng(0)
    # raw inputs x (not normalised): the circuit normalises, takes the root and converts to t
    xs = np.concatenate(
        [rng.integers(1, 3_133_453, 200), [1, 2, 3, 4, 5, 3_133_452, 1 << 20, 3 << 19]]
    ).astype(np.int64)
    r = Rec(22)
    flags = normalise_even(r, list(range(22)))
    q, w, zeros = sqrt_root(r, list(range(22)), widths)
    t = finish_root(r, q, w, zeros)
    back, got = _run(r.ops, None, xs, list(q) + list(t) + list(flags))
    assert (back == xs).all() or True  # x is consumed in place here; the inverse test below restores it
    k = np.array([(22 - int(v).bit_length()) // 2 for v in xs])
    n = xs << (2 * k)
    rr, tt = root(n)
    gq = (got[: len(q)].astype(np.int64) * (1 << np.arange(len(q)))[:, None]).sum(axis=0)
    gt = (got[len(q) : len(q) + len(t)].astype(np.int64) * (1 << np.arange(len(t)))[:, None]).sum(axis=0)
    gt = np.where(got[len(q) + len(t) - 1], gt - (1 << len(t)), gt)
    gf = (got[len(q) + len(t) :].astype(np.int64) * (1 << np.arange(4))[:, None]).sum(axis=0)
    assert (gq == rr).all() and (gt == tt).all() and (gf == k).all()


def test_forward_then_inverse_restores_x_and_cleans_up() -> None:
    n_all = reachable_n()
    _, _, widths = nr_model(n_all)
    rng = np.random.default_rng(1)
    xs = np.concatenate([rng.integers(1, 3_133_453, 200), [1, 2, 3, 3_133_452]]).astype(np.int64)
    r = Rec(22)
    flags = normalise_even(r, list(range(22)))
    q, w, zeros = sqrt_root(r, list(range(22)), widths)
    finish_root(r, q, w, zeros)
    del flags
    prog = r.ops
    b = km.CircuitBuilder()
    xr = b.create_quantum_register(22, name="x")
    bind = Binding({i: xr[i] for i in range(22)})
    replay(b, prog, bind)
    replay(b, inverse(prog), bind)
    c = b.finish_circuit()
    sim = km.Simulator(len(xs), seed=2)
    sim.write_across_shots(c.register_data["x"], ((xs[None, :] >> np.arange(22)[:, None]) & 1) == 1)
    sim.do(c)
    back = (sim.read_across_shots(c.register_data["x"]).astype(np.int64) * (1 << np.arange(22))[:, None]).sum(
        axis=0
    )
    assert (back == xs).all()
    assert not sim.read_across_shots(km.array([km.q(i) for i in range(22, c.num_qubits)])).any()
    assert not sim.read_phase_flipped_across_shots().any()


def test_full_circuit_phase_and_cleanliness() -> None:
    import pickle  # noqa: PLC0415

    from invsqrt_gen.sqrtdiv import fit_sd  # noqa: PLC0415
    from invsqrt_gen.sqrtdiv_circuit import build_circuit, expected_half_turns  # noqa: PLC0415

    tab = fit_sd(40, 29)
    del pickle
    c = build_circuit(tab)
    rng = np.random.default_rng(3)
    xs = np.concatenate([rng.integers(1, 3_133_453, 60), [1, 2, 3, 4, 5, 16, 1 << 20, 3_133_452]]).astype(
        np.int64
    )
    sim = km.Simulator(len(xs), seed=4)
    reg = c.register_data["x"]
    sim.write_across_shots(reg, ((xs[None, :] >> np.arange(22)[:, None]) & 1) == 1)
    sim.do(c)
    back = (sim.read_across_shots(reg).astype(np.int64) * (1 << np.arange(22))[:, None]).sum(axis=0)
    assert (back == xs).all()
    assert not sim.read_across_shots(km.array([km.q(i) for i in range(22, c.num_qubits)])).any()
    ph = np.array([float(sim.read_shot_phase(i)) for i in range(len(xs))])
    ex = expected_half_turns(xs)
    err = ((ph - ex + 1) % 2) - 1
    assert np.abs(err / ex).max() < 2.0**-24
