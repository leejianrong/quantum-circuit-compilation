from bench import publicdiff

ROWS = [
    ("a__x/files/s.zip!invsqrt/invsqrt.kmb", 10, "aa"),
    ("a__x/files/s.zip!dqi/dqi.kmb", 10, "bb"),
    ("a__x-20261121/files/s.zip!invsqrt/invsqrt.kmb", 10, "aa"),  # unchanged
    ("a__x-20261121/files/s.zip!dqi/dqi.kmb", 10, "cc"),  # new
    ("b__y-20261121/files/dfthcsos/angle_k_0.kmb", 5, "dd"),  # new, known to the ledger below
    ("b__y-20261121/files/dfthcsos/angle_k_1.kmb", 5, "ee"),  # new
    ("b__y-20261121/files/notes.md", 5, "ff"),  # not a circuit
    ("b__y-20261121/files/big.kmb", 5, "SKIPPED_OVER_CAP"),
    ("b__y-20261121/files/open/dqi.kmb.xz!decompressed", 5, "gg"),  # new, decompressed member
]


def test_only_unseen_circuit_files_are_new() -> None:
    new = publicdiff.diff(ROWS, "-20261121", known={"dd"})
    assert [(n.bench, n.sha256) for n in new] == [("dfthcsos", "ee"), ("dqi", "cc"), ("dqi", "gg")]


def test_duplicate_hash_in_fresh_dirs_is_listed_once() -> None:
    rows = [*ROWS, ("c__z-20261121/dqi.kmb", 10, "cc")]
    assert sum(n.sha256 == "cc" for n in publicdiff.diff(rows, "-20261121", known=set())) == 1
