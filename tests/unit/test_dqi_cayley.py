import random

from dqi_gen.cayley import Cayley, cayley_failure, plain_failure


def test_moments_are_conjugate_symmetric() -> None:
    cy = Cayley(4, 8)
    rng = random.Random(1)
    word = cy.random_word(3, rng)
    t = cy.moments(cy.syndromes(word))
    assert cy.conj_symmetric(t)


def test_cayley_decodes_and_degenerates_about_q_times_less_often() -> None:
    rng = random.Random(3)
    plain = plain_failure(5, 10, 5, 400, rng)
    fail, wrong = cayley_failure(5, 10, 5, 400, rng)
    assert plain > 0.1  # about (w - 1) / q = 0.125
    assert fail < 0.04  # about (w - 1) / q^2
    assert wrong < 0.03
