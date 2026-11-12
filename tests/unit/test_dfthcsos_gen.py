"""The dfthcsos loader generator: tables, counts and the qubit cap (no kickmix needed)."""

import numpy as np
import pytest

from dfthcsos_gen import angle_deltas, max_words_per_circuit, unary_toffolis


def test_deltas_stream_the_words() -> None:
    rng = np.random.default_rng(0)
    words = rng.integers(0, 256, size=(40, 75))
    d = angle_deltas(words, 13)
    assert d.shape == (6, 40, 13)
    acc = np.bitwise_xor.accumulate(d, axis=0)  # words registers after circuit k
    assert (acc.transpose(1, 0, 2).reshape(40, 78)[:, :75] == words).all()
    assert not acc.transpose(1, 0, 2).reshape(40, 78)[:, 75:].any()  # padding stays zero


@pytest.mark.parametrize("rows", [5, 64, 100, 1220])
def test_random_table_costs_rows_minus_two(rows: int) -> None:
    rng = np.random.default_rng(rows)
    assert unary_toffolis(rng.integers(0, 256, size=(rows, 4))) == rows - 2


def test_pruning_of_uniform_and_zero_subtrees() -> None:
    delta = np.zeros((64, 2), dtype=np.int64)
    assert unary_toffolis(delta) == 0
    delta[:, 0] = 7  # one value everywhere: a single load at the root
    assert unary_toffolis(delta) == 0
    delta[37, 1] = 1  # a single odd row needs a path to its leaf
    assert 0 < unary_toffolis(delta) < 62


def test_word_cap_for_public_shape() -> None:
    assert max_words_per_circuit(1220, 8) == 13  # 11 + 104 + 10 = 125 qubits
    assert max_words_per_circuit(3976, 12) == 8  # the baseline's 8 words, 119 qubits
