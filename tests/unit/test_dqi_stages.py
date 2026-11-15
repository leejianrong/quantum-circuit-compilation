"""`dqi_gen.stages` turns a study's tag counts into stage groups and per-node lists."""

from dqi_gen import stages


def _tags() -> list[list[object]]:
    names = [
        "extract_fwd",
        "synthesis_fwd",
        "outer_fwd",
        "finish_fwd",
        "scan",
        "outer_return",
        "synthesis_return",
        "extract_return",
    ]
    out: list[list[object]] = [["stage:start", 0, 0]]
    cum = 0
    for i in (0, 1):
        cum += 10 + i
        out.append([f"stage:raw_query_prefix_{i:02d}", 0, cum])
    cum += 1
    out.append(["stage:extract_fwd", 0, cum])
    for k, n in enumerate(names[1:7]):
        cum += 100 * (k + 1)
        out.append([f"stage:{n}", 0, cum])
    out.append(["other tag", 0, cum + 5])
    cum += 5
    for i in (1, 0):
        cum += 7 + i
        out.append([f"stage:raw_query_return_{i:02d}", 0, cum])
    out.append(["stage:extract_return", 0, cum])
    return out


def test_groups_and_nodes() -> None:
    d = stages.stage_ledger({"tag_cum": _tags()})
    assert d["groups"]["extract fwd"] == 22
    assert d["groups"]["synthesis fwd"] == 100
    assert d["groups"]["extract return"] == 5 + 8 + 7
    assert d["extract_fwd_nodes"] == [10, 11]
    assert d["extract_ret_nodes"] == [7, 13]
    assert d["total"] == sum(d["groups"].values())
