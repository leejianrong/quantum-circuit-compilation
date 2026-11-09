"""Hash everything under public/ into public/MANIFEST.tsv (path, size, sha256).

Reads files as bytes only; zip members and .xz contents are hashed in a stream and never written
to disk. Run with `python3 -I` (see scripts/fetch_public.sh). Files over the size cap are not hashed.
"""

import hashlib
import lzma
import sys
import zipfile
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rows(root: Path, cap: int) -> list[tuple[str, int, str]]:
    out: list[tuple[str, int, str]] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.is_symlink() or p.name == "MANIFEST.tsv":
            continue
        rel = p.relative_to(root).as_posix()
        size = p.stat().st_size
        out.append((rel, size, sha256_file(p) if size <= cap else "SKIPPED_OVER_CAP"))
        if p.suffix == ".zip" and size <= cap:
            try:
                with zipfile.ZipFile(p) as z:
                    for i in z.infolist():
                        if i.is_dir() or i.file_size > cap:
                            continue
                        h = hashlib.sha256()
                        with z.open(i) as f:
                            for chunk in iter(lambda: f.read(1 << 20), b""):
                                h.update(chunk)
                        out.append((f"{rel}!{i.filename}", i.file_size, h.hexdigest()))
            except zipfile.BadZipFile:
                pass
        if p.suffix == ".xz" and size <= cap:
            # streamed decompression only (a data transform); the plain file's hash is what verifiers see
            try:
                h = hashlib.sha256()
                n = 0
                with lzma.open(p) as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        h.update(chunk)
                        n += len(chunk)
                out.append((f"{rel}!decompressed", n, h.hexdigest()))
            except lzma.LZMAError:
                pass
    return out


def main(argv: list[str]) -> None:
    root = Path(argv[1])
    cap = int(argv[2]) if len(argv) > 2 else 1 << 30
    table = rows(root, cap)
    (root / "MANIFEST.tsv").write_text("".join(f"{r}\t{s}\t{h}\n" for r, s, h in table))
    print(f"wrote {root / 'MANIFEST.tsv'} ({len(table)} entries)")


if __name__ == "__main__":
    main(sys.argv)
