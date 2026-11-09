import os
import pathlib
import zipfile

import pytest

from bench import cli, pack


def make_store(best: pathlib.Path, n_angles: int = 3) -> None:
    (best / "invsqrt").mkdir(parents=True)
    (best / "dqi").mkdir()
    (best / "dfthcsos").mkdir()
    (best / "invsqrt" / "invsqrt.kmb").write_bytes(b"inv")
    (best / "dqi" / "dqi.kmx").write_bytes(b"dqi")
    for k in range(n_angles):
        (best / "dfthcsos" / f"angle_k_{k}.kmb").write_bytes(f"a{k}".encode())
    (best / "dfthcsos" / "submission.npz").write_bytes(b"npz")


def metric_find_one(root: pathlib.Path, name: str, is_dir: bool = False) -> int:
    """The metric's find_one count: matches anywhere under the unpacked archive."""
    return len([p for p in root.rglob(name) if p.is_dir() == is_dir])


def test_pack_matches_metric_rules(tmp_path: pathlib.Path) -> None:
    best, out = tmp_path / "best", tmp_path / "out" / "s.zip"
    make_store(best)
    names = pack.pack(best, out)
    with zipfile.ZipFile(out) as z:
        assert sorted(z.namelist()) == sorted(names)
        z.extractall(tmp_path / "x")
    x = tmp_path / "x"
    assert metric_find_one(x, "invsqrt.km[xb]") == 1
    assert metric_find_one(x, "dqi.km[xb]") == 1
    assert metric_find_one(x, "dfthcsos", is_dir=True) == 1
    assert sorted(p.stem for p in (x / "dfthcsos").glob("angle_k_*.km[xb]")) == [
        f"angle_k_{k}" for k in range(3)
    ]
    assert (x / "dfthcsos" / "submission.npz").read_bytes() == b"npz"


def test_pack_is_deterministic(tmp_path: pathlib.Path) -> None:
    make_store(tmp_path / "best")
    pack.pack(tmp_path / "best", tmp_path / "a.zip")
    pack.pack(tmp_path / "best", tmp_path / "b.zip")
    assert (tmp_path / "a.zip").read_bytes() == (tmp_path / "b.zip").read_bytes()


@pytest.mark.parametrize("bench", pack.BENCHES)
def test_refuses_when_a_benchmark_is_missing(tmp_path: pathlib.Path, bench: str) -> None:
    best = tmp_path / "best"
    make_store(best)
    for p in sorted((best / bench).iterdir()):
        p.unlink()
    (best / bench).rmdir()
    out = tmp_path / "s.zip"
    with pytest.raises(pack.PackError, match="no entry"):
        pack.pack(best, out)
    assert not out.exists()


def test_refuses_empty_benchmark_dir(tmp_path: pathlib.Path) -> None:
    best = tmp_path / "best"
    make_store(best)
    (best / "dqi" / "dqi.kmx").unlink()
    with pytest.raises(pack.PackError, match="exactly one dqi"):
        pack.pack(best, tmp_path / "s.zip")


def test_refuses_same_circuit_in_both_formats(tmp_path: pathlib.Path) -> None:
    best = tmp_path / "best"
    make_store(best)
    (best / "invsqrt" / "invsqrt.kmx").write_bytes(b"x")
    with pytest.raises(pack.PackError, match="exactly one invsqrt"):
        pack.pack(best, tmp_path / "s.zip")


def test_refuses_angle_duplicate_across_formats(tmp_path: pathlib.Path) -> None:
    best = tmp_path / "best"
    make_store(best)
    (best / "dfthcsos" / "angle_k_1.kmx").write_bytes(b"x")
    with pytest.raises(pack.PackError, match="both"):
        pack.pack(best, tmp_path / "s.zip")


def test_refuses_gap_in_angle_indexes(tmp_path: pathlib.Path) -> None:
    best = tmp_path / "best"
    make_store(best)
    (best / "dfthcsos" / "angle_k_1.kmb").unlink()
    with pytest.raises(pack.PackError, match=r"missing \[1\]"):
        pack.pack(best, tmp_path / "s.zip")


def test_refuses_missing_npz_and_unexpected_files(tmp_path: pathlib.Path) -> None:
    best = tmp_path / "best"
    make_store(best)
    (best / "dfthcsos" / "notes.txt").write_bytes(b"x")
    with pytest.raises(pack.PackError, match="unexpected"):
        pack.pack(best, tmp_path / "s.zip")
    (best / "dfthcsos" / "notes.txt").unlink()
    (best / "dfthcsos" / "submission.npz").unlink()
    with pytest.raises(pack.PackError, match="submission.npz"):
        pack.pack(best, tmp_path / "s.zip")


def test_refuses_links_and_directories(tmp_path: pathlib.Path) -> None:
    best = tmp_path / "best"
    make_store(best)
    real = tmp_path / "real.kmb"
    real.write_bytes(b"x")
    (best / "invsqrt" / "invsqrt.kmb").unlink()
    (best / "invsqrt" / "invsqrt.kmb").symlink_to(real)
    with pytest.raises(pack.PackError, match="regular file"):
        pack.pack(best, tmp_path / "s.zip")
    (best / "invsqrt" / "invsqrt.kmb").unlink()
    os.link(real, best / "invsqrt" / "invsqrt.kmb")  # a second link to the inode
    with pytest.raises(pack.PackError, match="regular file"):
        pack.pack(best, tmp_path / "s.zip")
    (best / "invsqrt" / "invsqrt.kmb").unlink()
    real.unlink()
    (best / "invsqrt" / "invsqrt.kmb").mkdir()
    with pytest.raises(pack.PackError, match="regular file"):
        pack.pack(best, tmp_path / "s.zip")


def test_refuses_to_write_inside_best(tmp_path: pathlib.Path) -> None:
    make_store(tmp_path / "best")
    with pytest.raises(pack.PackError, match="inside best"):
        pack.pack(tmp_path / "best", tmp_path / "best" / "s.zip")


def test_cli_exit_codes(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    best, out = tmp_path / "best", tmp_path / "s.zip"
    best.mkdir()
    assert cli.main(["pack", "--best", str(best), "--out", str(out)]) == 1
    assert "PACK FAILED" in capsys.readouterr().out and not out.exists()
    make_store(tmp_path / "full")
    assert cli.main(["pack", "--best", str(tmp_path / "full"), "--out", str(out)]) == 0
    assert out.exists()
    assert pack.main(["--best", str(tmp_path / "full"), "--out", str(tmp_path / "t.zip")]) == 0
