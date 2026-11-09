"""`bench pack`: assemble the submission archive from the best-known-good store `best/`.

Layout of the store, one entry per benchmark (ADR-0003: a submission is never partial):

    best/invsqrt/invsqrt.kmb|kmx
    best/dqi/dqi.kmb|kmx
    best/dfthcsos/angle_k_0.kmb|kmx ... angle_k_<n-1>.kmb|kmx and submission.npz

The checks mirror `find_one` and `read` in the metric notebook (metric/google-quantum-ai-metric):
regular files only (no links, no special files), exactly one circuit per name, no angle index
given in both formats, indexes contiguous from 0. Whether a .kmb really is binary kickmix is the
verifier's job (a text file named .kmb is rejected by the metric without a useful message).
"""

import argparse
import os
import pathlib
import re
import stat
import zipfile
from collections.abc import Sequence

BENCHES = ("invsqrt", "dqi", "dfthcsos")
ANGLE = re.compile(r"angle_k_(\d+)\.km[xb]")
IGNORED = {".gitkeep"}
EPOCH = (1980, 1, 1, 0, 0, 0)  # fixed timestamps: the same store gives the same archive bytes


class PackError(Exception):
    pass


def _files(d: pathlib.Path) -> list[pathlib.Path]:
    if not d.is_dir() or d.is_symlink():
        raise PackError(f"missing benchmark directory {d}")
    out = []
    for p in sorted(d.iterdir()):
        if p.name in IGNORED:
            continue
        st = p.lstat()
        if not stat.S_ISREG(st.st_mode) or st.st_nlink > 1:
            raise PackError(f"{p} must be a regular file, not a link, directory or special file")
        out.append(p)
    return out


def _single(d: pathlib.Path, bench: str) -> pathlib.Path:
    files = _files(d)
    circuits = [p for p in files if p.name in (f"{bench}.kmb", f"{bench}.kmx")]
    if len(circuits) != 1:
        raise PackError(f"{d} must hold exactly one {bench}.kmx or {bench}.kmb, found {len(circuits)}")
    extra = [p.name for p in files if p not in circuits]
    if extra:
        raise PackError(f"{d} holds unexpected files {extra}")
    return circuits[0]


def _dfthcsos(d: pathlib.Path) -> list[tuple[str, pathlib.Path]]:
    files = _files(d)
    by_idx: dict[int, list[pathlib.Path]] = {}
    npz = [p for p in files if p.name == "submission.npz"]
    for p in files:
        m = ANGLE.fullmatch(p.name)
        if m:
            by_idx.setdefault(int(m.group(1)), []).append(p)
        elif p not in npz:
            raise PackError(f"{d} holds unexpected file {p.name}")
    if len(npz) != 1:
        raise PackError(f"{d} must hold submission.npz")
    if not by_idx:
        raise PackError(f"{d} holds no angle_k_<i> circuits")
    dup = sorted(i for i, ps in by_idx.items() if len(ps) > 1)
    if dup:
        raise PackError(f"angle_k_{dup} given in both .kmx and .kmb")
    missing = sorted(set(range(max(by_idx) + 1)) - set(by_idx))
    if missing:
        raise PackError(f"angle indexes must be contiguous from 0; missing {missing}")
    angles = [(f"dfthcsos/{ps[0].name}", ps[0]) for _, ps in sorted(by_idx.items())]
    return [*angles, ("dfthcsos/submission.npz", npz[0])]


def collect(best: pathlib.Path) -> list[tuple[str, pathlib.Path]]:
    """Archive name and source path of every file to pack; raises PackError if anything is off."""
    missing = [b for b in BENCHES if not (best / b).is_dir()]
    if missing:
        raise PackError(f"refusing to pack: best/ has no entry for {missing}")
    inv, dqi = _single(best / "invsqrt", "invsqrt"), _single(best / "dqi", "dqi")
    return [(inv.name, inv), (dqi.name, dqi), *_dfthcsos(best / "dfthcsos")]


def pack(best: pathlib.Path, out: pathlib.Path) -> list[str]:
    """Write the archive (atomically) and return its member names."""
    entries = collect(best)
    if out.resolve().is_relative_to(best.resolve()):
        raise PackError("the archive must not be written inside best/")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for name, src in entries:
            info = zipfile.ZipInfo(name, EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            with src.open("rb") as f, z.open(info, "w", force_zip64=True) as w:
                while chunk := f.read(1 << 20):
                    w.write(chunk)
    os.replace(tmp, out)
    return [n for n, _ in entries]


def add_parser(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    p = sub.add_parser("pack", help="assemble the submission archive from best/ (refuses if incomplete)")
    add_args(p)


def add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--best", type=pathlib.Path, default=pathlib.Path("best"))
    p.add_argument("--out", type=pathlib.Path, default=pathlib.Path("out/submission.zip"))


def run(best: pathlib.Path, out: pathlib.Path) -> int:
    try:
        names = pack(best, out)
    except PackError as err:
        print(f"PACK FAILED: {err}")
        return 1
    print(f"packed {len(names)} files into {out}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m bench.pack")
    add_args(p)
    a = p.parse_args(argv)
    return run(a.best, a.out)


if __name__ == "__main__":
    raise SystemExit(main())
