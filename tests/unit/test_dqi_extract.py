"""Both wired extractors match `thiele.extract` and round-trip (weights 19 to 35)."""

import random
from typing import Any

import kickmix as km  # type: ignore[import-not-found,unused-ignore]
import numpy as np
import pytest

from dqi_gen import extract, extract_v3
from dqi_gen import thiele as T


def _cases(weights: list[int]) -> list[tuple[list[int], list[tuple[int, int]], int]]:
    gf = T.field()
    rng = random.Random(2)
    out = []
    for wt in weights:
        pos = rng.sample(range(4095), wt)
        word = {j: rng.randint(1, 4095) for j in pos}
        res = T.residues(gf, T.residue_polynomial(gf, T.syndromes_of(gf, word)))
        ys = [(r0 ^ int(gf.mul(2 * i, r1))) | (r1 << 12) for i, (r0, r1) in enumerate(res)]
        heads, w = T.extract(gf, res)
        out.append((ys, heads, w))
    return out


# per extractor, the extractor alone: static Toffolis forward, forward + return, qubits
COUNTS = {"v2": (73919, 157077, 890), "v3": (73540, 151929, 889)}
MODULES = {"v2": extract, "v3": extract_v3}


def _run(
    which: str, round_trip: bool, cases: list[tuple[list[int], list[tuple[int, int]], int]]
) -> tuple[Any, Any, Any, Any]:
    b = km.CircuitBuilder()
    words = [list(b.create_quantum_register(24, name=f"W{i}")) for i in range(35)]
    carry = list(b.alloc_qubits(24))
    b.x(carry[0])
    rec = MODULES[which].forward(b, words, carry)
    if round_trip:
        MODULES[which].backward(b, words, carry, rec)
    circ = b.finish_circuit()
    shots = len(cases)
    sim = km.Simulator(batch_size=shots)
    for i, wd in enumerate(words):
        bits = np.array([[(cases[s][0][i] >> k) & 1 for s in range(shots)] for k in range(24)], dtype=bool)
        sim.write_across_shots(wd, bits)
    sim.do(circ)

    def val(reg: list[km.q], s: int) -> int:
        o = sim.read_across_shots(km.array(reg))
        return sum(int(o[k][s]) << k for k in range(24))

    return (
        circ,
        [[val(w, s) for w in words] for s in range(shots)],
        [val(carry, s) for s in range(shots)],
        sim,
    )


@pytest.mark.parametrize("which", ["v2", "v3"])
def test_forward_matches_thiele_heads(which: str) -> None:
    cases = _cases([35, 28, 19])
    circ, got, _, _ = _run(which, False, cases)
    assert circ.operation_statistics().num_toffoli_like == COUNTS[which][0]
    for s, (_, heads, w) in enumerate(cases):
        assert all(got[s][i] == (heads[i][0] | (heads[i][1] << 12)) for i in range(w))
        assert all(v == 0 for v in got[s][w:])


@pytest.mark.parametrize("which", ["v2", "v3"])
def test_round_trip_restores_words_and_carry_without_phase_errors(which: str) -> None:
    cases = _cases([35, 30, 22, 19])
    circ, got, carries, sim = _run(which, True, cases)
    assert circ.operation_statistics().num_toffoli_like == COUNTS[which][1]
    assert circ.num_qubits == COUNTS[which][2]
    for s, (ys, _, _) in enumerate(cases):
        assert got[s] == ys and carries[s] == 1
    assert not sim.read_phase_flipped_across_shots().any()
