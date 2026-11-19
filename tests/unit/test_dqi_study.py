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


def test_tag_cum_counts_toffolis_between_tags() -> None:
    lines = [
        'INFO_TAG "stage:a"\n',
        "CCX q0 q1 q2\n",
        "CX q0 q1\n",
        'INFO_TAG "stage:b"\n',
        "CCZ q0 q1 q2\n",
        "CSWAP q0 q1 q2\n",
    ]
    r = scan(lines)
    assert [(n, c) for n, _, c in r["tag_cum"]] == [("stage:a", 0), ("stage:b", 1)]
    assert r["total_toffoli"] == 3


def test_condition_statistics_separate_hmr_and_derived_bits() -> None:
    lines = [
        "HMR q0 b0\n",
        "BIT_INVERT b1 if b0\n",
        "PUSH_CONDITION if b1\n",
        "SWAP q2 q3\n",
        "CCX q1 q2 q3\n",
        "POP_CONDITION\n",
        "CX q1 q2 if b0\n",
        "SWAP q2 q3\n",
        "CSWAP q4 q5 q6\n",
    ]
    r = scan(lines)
    assert r["cond_mix"]["SWAP"] == {"conditioned": 1, "plain": 1}
    assert r["cond_mix"]["CX"] == {"conditioned": 1}
    assert r["cond_origin"]["SWAP"] == {"derived": 1}  # b1 was written by BIT_INVERT
    assert r["cond_origin"]["CX"] == {"hmr": 1}  # b0 was written by HMR
    assert r["cond_depth_toffoli"] == {"0": 1, "1": 1}  # CSWAP unconditioned, CCX under one block
