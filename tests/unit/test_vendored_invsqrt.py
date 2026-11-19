import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "third_party" / "syed_invsqrt"


def test_vendored_invsqrt_files_are_byte_identical_to_the_manifest() -> None:
    manifest = [line.split("  ", 1) for line in (ROOT / "MANIFEST.sha256").read_text().splitlines()]
    assert len(manifest) == 78
    for digest, rel in manifest:
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == digest, rel
    on_disk = {p.relative_to(ROOT).as_posix() for p in (ROOT / "src").rglob("*") if p.is_file()}
    assert on_disk == {rel for _, rel in manifest}, "file added or removed without updating the manifest"
