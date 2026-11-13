"""Why a consuming signed-digit multiplier cannot repay its dropped low columns locally (QCC-13).

LSB-first Horner with an odd `D`: `acc <- (acc + e D) >> 1`, the dropped bit is `(acc + e D) & 1`. The final
accumulator determines the digits (injective), but one backward step never does: both values of the dropped
bit give an in-range predecessor, so a mirror that has measured the dropped bits cannot recompute them.
"""


def _run(d: int, es: list[int]) -> tuple[int, list[int]]:
    acc, drops = 0, []
    for e in es:
        s = acc + e * d
        drops.append(s & 1)
        acc = s >> 1
    return acc, drops


def test_final_accumulator_is_injective_but_backward_steps_are_ambiguous() -> None:
    n, d = 8, 5001
    finals = set()
    ambiguous = total = 0
    for m in range(1 << n):
        es = [2 * ((m >> i) & 1) - 1 for i in range(n)]
        acc, _ = _run(d, es)
        finals.add(acc)
        a = 0
        for e in es:
            s = a + e * d
            nxt = s >> 1
            ok = [c for c in (2 * nxt + dd - e * d for dd in (0, 1)) if abs(c) < d]
            total += 1
            ambiguous += len(ok) == 2
            a = nxt
    assert len(finals) == 1 << n  # injective: t is determined by the final accumulator
    assert ambiguous == total  # but every single backward step has two candidates
