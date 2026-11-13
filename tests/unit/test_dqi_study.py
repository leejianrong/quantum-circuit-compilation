from dqi_gen.study import scan

LINES = [
    'INFO_TAG "@enter:a"\n',
    "CX q0 q1\n",
    "CCX q0 q1 q2\n",
    "CSWAP q3 q13 q14 if b0\n",
    "R q2\n",
    'REGISTER r0 "S0"\n',
]


def test_scan_counts_toffolis_and_blocks() -> None:
    r = scan(LINES, window=3, block=12)
    assert r["instructions"] == 6
    assert r["mix"]["CCX"] == 1
    assert r["qubit_ids"] == 6
    assert r["max_id"] == 14
    assert sum(w["toffoli"] for w in r["windows"]) == 2
    assert r["blocks"]["0"]["toffoli_touches"] == 4  # q0 q1 q2 (CCX) and q3 (CSWAP)
    assert r["tags"] == [(0, "@enter:a")]
